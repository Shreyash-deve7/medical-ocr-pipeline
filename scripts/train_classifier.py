"""scripts/train_classifier.py — Fine-tune MobileNetV3-large on labelled medical document dataset.

Usage:
    python scripts/train_classifier.py --labels backend/labels.json \
           --splits backend/dataset_splits.json \
           --weights backend/weights/classifier_3class.pth \
           --epochs 50 --batch-size 8 --lr 1e-4

Improvements over the original scaffold (per the SDLC plan):
  * Trains ONLY on the ``train`` split from dataset_splits.json; the ``test``
    split is never touched (held out for final evaluation).
  * Unfreezes the last conv blocks (features.10-14) in addition to the head,
    so the backbone adapts to medical-document texture instead of staying
    ImageNet-generic.
  * Stronger phone-camera augmentation (rotation, brightness/contrast,
    blur, perspective warp, slight zoom) to bridge the synthetic->real gap.
  * Class-balanced FocalLoss (gamma=2) + WeightedRandomSampler to fight the
    severe HANDWRITTEN minority (only ~9 images in the whole dataset).
  * Early stopping on validation accuracy (patience) and best-checkpoint save.
  * Logs per-epoch metrics + final confusion to
    backend/weights/training_metrics.json.

Dependencies: torch, torchvision, opencv-python, numpy (in the project venv).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision import transforms
from torchvision.models import mobilenet_v3_large

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("train_classifier")

# ── Constants ──────────────────────────────────────────────────────────────────

IMG_SIZE = 224
NUM_CLASSES = 3
CLASSES = ("TABLE", "HANDWRITTEN", "PRINTED_TEXT")
CLASS_TO_IDX = {cls: i for i, cls in enumerate(CLASSES)}
IDX_TO_CLASS = {i: cls for cls, i in CLASS_TO_IDX.items()}


# ── Augmentations ──────────────────────────────────────────────────────────────


class PhonePhotoAugment:
    """Augmentations that simulate phone-camera capture conditions.

    Real phone photos of documents suffer rotation, lighting variation, blur,
    perspective distortion and mild zoom. We mimic all of these so the CNN
    learns document *type* invariants rather than capture artefacts.
    """

    def __init__(self, printed_warp: bool = True, p: float = 0.7):
        self.printed_warp = printed_warp
        self.p = p

    def _maybe(self) -> bool:
        return random.random() < self.p

    def __call__(self, image: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]

        # Random rotation +/-12 deg.
        if self._maybe():
            angle = random.uniform(-12, 12)
            M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
            image = cv2.warpAffine(image, M, (w, h), borderMode=cv2.BORDER_REFLECT)

        # Brightness / contrast jitter.
        if self._maybe():
            alpha = random.uniform(0.8, 1.2)
            beta = random.uniform(-25, 25)
            image = cv2.convertScaleAbs(image, alpha=alpha, beta=beta)

        # Gaussian blur (slight out-of-focus).
        if random.random() < 0.3:
            k = random.choice([3, 5])
            image = cv2.GaussianBlur(image, (k, k), 0)

        # Mild zoom-in (phone close-ups) with reflect padding.
        if self._maybe():
            zoom = random.uniform(1.0, 1.12)
            nh, nw = int(h / zoom), int(w / zoom)
            y0, x0 = (h - nh) // 2, (w - nw) // 2
            crop = image[y0:y0 + nh, x0:x0 + nw]
            image = cv2.resize(crop, (w, h))

        # PRINTED_TEXT-specific: perspective warp to simulate angled photos.
        if self.printed_warp and random.random() < 0.45:
            dx1 = random.uniform(0, w * 0.06)
            dx2 = random.uniform(-w * 0.06, 0)
            dy = random.uniform(-h * 0.04, h * 0.04)
            src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
            dst = np.float32([[dx1, dy], [w + dx2, dy], [w, h], [0, h]])
            M = cv2.getPerspectiveTransform(src, dst)
            image = cv2.warpPerspective(image, M, (w, h), borderMode=cv2.BORDER_REFLECT)

        return image


# ── Dataset ────────────────────────────────────────────────────────────────────


@dataclass
class Sample:
    image: np.ndarray          # RGB uint8
    label: int                 # 0=TABLE, 1=HANDWRITTEN, 2=PRINTED_TEXT


class MedicalDocDataset(Dataset):
    def __init__(self, samples: List[Sample], transform=None, augment: bool = False):
        self.samples = samples
        self.transform = transform
        self.aug = PhonePhotoAugment(printed_warp=True) if augment else None

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int]:
        image = self.samples[idx].image.copy()
        label = self.samples[idx].label
        if self.aug is not None:
            image = self.aug(image)
        if self.transform:
            image = self.transform(image)
        else:
            image = torch.from_numpy(image.transpose(2, 0, 1)).float() / 255.0
        return image, label


# ── Model ──────────────────────────────────────────────────────────────────────


def build_model(num_classes: int = NUM_CLASSES, pretrained: bool = True) -> nn.Module:
    """MobileNetV3-large with a custom 3-class head.

    Unfreezes the final conv blocks (features.10-14) + head so the backbone
    adapts to medical-document texture, with aggressive dropout to resist
    overfitting on the tiny (~65 train) dataset.
    """
    model = mobilenet_v3_large(weights="DEFAULT" if pretrained else None)

    # Unfreeze the last two inverted-residual blocks (features.10-14) so the
    # late-stage semantic features adapt; freeze the early generic layers.
    for name, param in model.features.named_parameters():
        unfreeze = any(name.startswith(f"features.{b}") for b in range(10, 15))
        param.requires_grad = unfreeze

    in_features = 960
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.5),
        nn.Linear(in_features, 512),
        nn.ReLU(inplace=True),
        nn.Dropout(p=0.4),
        nn.Linear(512, num_classes),
    )

    return model


# ── Training helpers ───────────────────────────────────────────────────────────


def train_one_epoch(model, loader, optimizer, criterion, device) -> Tuple[float, float]:
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * images.size(0)
        correct += outputs.max(1).indices.eq(labels).sum().item()
        total += labels.size(0)
    return total_loss / total, 100.0 * correct / total


@torch.no_grad()
def evaluate(model, loader, criterion, device) -> Tuple[float, float, np.ndarray]:
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    cm = np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=int)
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        loss = criterion(outputs, labels)
        total_loss += loss.item() * images.size(0)
        preds = outputs.max(1).indices
        correct += preds.eq(labels).sum().item()
        total += labels.size(0)
        for t, p in zip(labels.cpu().numpy(), preds.cpu().numpy()):
            cm[t][p] += 1
    return total_loss / total, 100.0 * correct / total, cm


class FocalLoss(nn.Module):
    """Class-balanced focal loss.

    FL(p_t) = -alpha_t * (1-p_t)^gamma * log(p_t)
    alpha_t is the inverse-frequency class weight (renormalised).
    """

    def __init__(self, weights: torch.Tensor, gamma: float = 2.0):
        super().__init__()
        self.weights = weights
        self.gamma = gamma

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce = nn.functional.cross_entropy(logits, targets, reduction="none")
        pt = torch.exp(-ce)
        focal_term = (1 - pt) ** self.gamma
        loss = focal_term * ce
        if self.weights is not None:
            loss = loss * self.weights[targets]
        return loss.mean()


def load_dataset(labels_path, splits_path=None, split: str = "train") -> Tuple[List[Sample], Dict]:
    with open(labels_path, encoding="utf-8") as f:
        labels = json.load(f)

    if splits_path is not None and Path(splits_path).exists():
        with open(splits_path, encoding="utf-8") as f:
            splits = json.load(f)
        wanted = set(splits["splits"].get(split, []))
        logger.info("Restricting to '%s' split: %d paths", split, len(wanted))
    else:
        wanted = None

    samples: List[Sample] = []
    class_counts = {c: 0 for c in CLASSES}

    for rel_path, meta in labels.items():
        if wanted is not None and rel_path not in wanted:
            continue
        img_path = Path(rel_path)
        if not img_path.exists():
            continue
        image = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if image is None:
            continue
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = cv2.resize(image, (IMG_SIZE, IMG_SIZE))
        true_class = meta["true_class"]
        samples.append(Sample(image=image, label=CLASS_TO_IDX[true_class]))
        class_counts[true_class] += 1

    logger.info(
        "Loaded %d %s images | TABLE=%d HANDWRITTEN=%d PRINTED_TEXT=%d",
        len(samples), split,
        class_counts["TABLE"], class_counts["HANDWRITTEN"], class_counts["PRINTED_TEXT"],
    )
    return samples, class_counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune MobileNetV3-large classifier")
    parser.add_argument("--labels", default="backend/labels.json")
    parser.add_argument("--splits", default="backend/dataset_splits.json")
    parser.add_argument("--weights", default="backend/weights/classifier_3class.pth")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Device: %s", device)

    project_root = Path(__file__).resolve().parent.parent
    train_samples, train_counts = load_dataset(
        project_root / args.labels, project_root / args.splits, "train")
    val_samples, _ = load_dataset(
        project_root / args.labels, project_root / args.splits, "val")

    if not train_samples:
        logger.error("No training samples found; aborting.")
        sys.exit(1)

    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    train_dataset = MedicalDocDataset(train_samples, transform=transform, augment=True)
    val_dataset = MedicalDocDataset(val_samples, transform=transform, augment=False)

    # WeightedRandomSampler: oversample the HANDWRITTEN minority.
    train_labels = [s.label for s in train_samples]
    cls_counts = {i: train_labels.count(i) for i in range(NUM_CLASSES)}
    sample_weights = [1.0 / cls_counts[lab] for lab in train_labels]
    sampler = WeightedRandomSampler(sample_weights, len(train_samples), replacement=True)

    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, sampler=sampler, num_workers=0, pin_memory=True)
    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=0, pin_memory=True)

    model = build_model(pretrained=True).to(device)
    logger.info("Trainable params: %d",
                sum(p.numel() for p in model.parameters() if p.requires_grad))

    # Class-balanced FocalLoss.
    total = sum(cls_counts.values())
    alpha = torch.tensor(
        [total / (NUM_CLASSES * max(1, cls_counts[i])) for i in range(NUM_CLASSES)],
        dtype=torch.float32, device=device)
    alpha = alpha / alpha.sum()
    criterion = FocalLoss(weights=alpha, gamma=2.0)
    logger.info("FocalLoss class weights: %s", [round(x, 3) for x in alpha.cpu().tolist()])

    # Lower LR for unfrozen backbone, higher for the fresh head.
    head_params = list(model.classifier.parameters())
    backbone_params = [p for n, p in model.features.named_parameters() if p.requires_grad]
    optimizer = optim.AdamW([
        {"params": backbone_params, "lr": args.lr * 0.1},
        {"params": head_params, "lr": args.lr},
    ], weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    best_val_acc = 0.0
    best_state = {}
    patience = 0
    history = []

    for epoch in range(1, args.epochs + 1):
        tr_loss, tr_acc = train_one_epoch(model, train_loader, optimizer, criterion, device)
        val_loss, val_acc, val_cm = evaluate(model, val_loader, criterion, device)
        scheduler.step()

        logger.info(
            "Epoch %2d/%d | train_loss=%.4f train_acc=%.1f%% | val_loss=%.4f val_acc=%.1f%%",
            epoch, args.epochs, tr_loss, tr_acc, val_loss, val_acc)

        history.append({
            "epoch": epoch, "train_loss": tr_loss, "train_acc": tr_acc,
            "val_loss": val_loss, "val_acc": val_acc,
            "val_confusion": val_cm.tolist(),
        })

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience = 0
            os.makedirs(os.path.dirname(args.weights) or ".", exist_ok=True)
            torch.save(best_state, args.weights)
            logger.info("New best model saved (val_acc=%.1f%%)", best_val_acc)
        else:
            patience += 1
            if patience >= args.patience:
                logger.info("Early stopping at epoch %d (patience=%d)", epoch, args.patience)
                break

    # Persist training metrics.
    metrics_path = Path(args.weights).parent / "training_metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump({
        "best_val_acc": best_val_acc,
        "class_counts_train": train_counts,
        "history": history,
    }, open(metrics_path, "w"), indent=2)
    logger.info("Training complete. Best val_acc=%.1f%%. Metrics -> %s", best_val_acc, metrics_path)


if __name__ == "__main__":
    main()
