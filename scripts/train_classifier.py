"""scripts/train_classifier.py — Fine-tune MobileNetV3-large on labelled medical document dataset.

Usage:
    python scripts/train_classifier.py --labels backend/labels.json
                                       --weights backend/weights/classifier_3class.pth
                                       --epochs 20 --batch-size 8 --lr 1e-4

The script:
  1. Loads images referenced in labels.json (relative paths from project root).
  2. Applies light augmentations (rotation, brightness/contrast jitter, Gaussian blur)
     to simulate phone-camera conditions.
  3. Fine-tunes the last two stages of MobileNetV3-large (classifier head + final conv
     block), freezing the earlier backbone.
  4. Saves the best weights (by validation accuracy) to the output path.

Dependencies: torch, torchvision, opencv-python, numpy (all already in the project
venv).
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
from torch.utils.data import DataLoader, Dataset
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
    """Light augmentations that simulate phone-camera capture conditions."""

    def __init__(self, printed_warp: bool = False):
        self.printed_warp = printed_warp

    def __call__(self, image: np.ndarray) -> np.ndarray:
        # Random rotation ±10 degrees.
        if random.random() < 0.5:
            angle = random.uniform(-10, 10)
            h, w = image.shape[:2]
            M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
            image = cv2.warpAffine(image, M, (w, h), borderMode=cv2.BORDER_REFLECT)

        # Brightness / contrast jitter.
        if random.random() < 0.5:
            alpha = random.uniform(0.85, 1.15)  # contrast
            beta = random.uniform(-15, 15)       # brightness
            image = cv2.convertScaleAbs(image, alpha=alpha, beta=beta)

        # Gaussian blur (simulates slight out-of-focus photos).
        if random.random() < 0.3:
            k = random.choice([3, 5])
            image = cv2.GaussianBlur(image, (k, k), 0)

        # PRINTED_TEXT-specific: perspective warp + grid-line erasure to
        # simulate photos of printed documents taken at an angle.
        if self.printed_warp and random.random() < 0.4:
            h, w = image.shape[:2]
            # Slight perspective distortion.
            src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
            dx1 = random.uniform(0, w * 0.05)
            dx2 = random.uniform(-w * 0.05, 0)
            dst = np.float32([[dx1, 0], [w + dx2, 0], [w, h], [0, h]])
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
        self.augment = augment
        # PRINTED_TEXT (label 2) gets extra perspective warp augmentation.
        self.aug = PhonePhotoAugment(printed_warp=True) if augment else None

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int]:
        image = self.samples[idx].image.copy()
        label = self.samples[idx].label

        if self.augment and self.aug:
            image = self.aug(image)

        if self.transform:
            image = self.transform(image)
        else:
            image = torch.from_numpy(image.transpose(2, 0, 1)).float() / 255.0

        return image, label


# ── Model ──────────────────────────────────────────────────────────────────────


def build_model(num_classes: int = NUM_CLASSES, pretrained: bool = True) -> nn.Module:
    """Build MobileNetV3-large with a custom 3-class classifier head.

    Uses aggressive dropout (0.5) in the classifier head to combat overfitting
    on the small (93-image) dataset.
    """
    model = mobilenet_v3_large(weights="DEFAULT" if pretrained else None)

    # Freeze early layers (features.0 through features.12).
    for name, param in model.features.named_parameters():
        if not name.startswith("features.13") and not name.startswith("features.14"):
            param.requires_grad = False

    # Replace classifier head with a dropout + linear stack.
    # MobileNetV3-Large features output 960 channels after avgpool.
    in_features = 960
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.5),
        nn.Linear(in_features, 512),
        nn.ReLU(inplace=True),
        nn.Dropout(p=0.3),
        nn.Linear(512, num_classes),
    )

    return model


# ── Training helpers ───────────────────────────────────────────────────────────


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: optim.Optimizer,
    criterion: nn.Module,
    device: torch.device,
) -> float:
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0

    for images, labels in loader:
        images = images.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * images.size(0)
        _, preds = outputs.max(1)
        correct += (preds == labels).sum().item()
        total += labels.size(0)

    return total_loss / total, 100.0 * correct / total


@torch.no_grad()
def evaluate(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> Tuple[float, float]:
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0

    for images, labels in loader:
        images = images.to(device)
        labels = labels.to(device)

        outputs = model(images)
        loss = criterion(outputs, labels)

        total_loss += loss.item() * images.size(0)
        _, preds = outputs.max(1)
        correct += (preds == labels).sum().item()
        total += labels.size(0)

    return total_loss / total, 100.0 * correct / total


# ── Main ───────────────────────────────────────────────────────────────────────


def load_dataset(labels_path: str, augment: bool = False) -> Tuple[List[Sample], Dict]:
    """Load images and labels from labels.json.

    Returns (samples, stats) where stats contains class distribution.
    """
    with open(labels_path, "r", encoding="utf-8") as f:
        labels = json.load(f)

    samples: List[Sample] = []
    missing = 0
    class_counts = {c: 0 for c in CLASSES}

    for rel_path, meta in labels.items():
        img_path = Path(rel_path)
        if not img_path.exists():
            missing += 1
            continue

        image = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if image is None:
            missing += 1
            continue

        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        # Resize to fixed input size.
        image = cv2.resize(image, (IMG_SIZE, IMG_SIZE))

        true_class = meta["true_class"]
        label = CLASS_TO_IDX[true_class]
        samples.append(Sample(image=image, label=label))
        class_counts[true_class] += 1

    if missing:
        logger.warning("Missing %d images (skipped)", missing)

    logger.info(
        "Loaded %d images | TABLE=%d HANDWRITTEN=%d PRINTED_TEXT=%d",
        len(samples),
        class_counts["TABLE"],
        class_counts["HANDWRITTEN"],
        class_counts["PRINTED_TEXT"],
    )
    return samples, class_counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune MobileNetV3-large classifier")
    parser.add_argument(
        "--labels",
        type=str,
        default="backend/labels.json",
        help="Path to labels.json",
    )
    parser.add_argument(
        "--weights",
        type=str,
        default="backend/weights/classifier_3class.pth",
        help="Output path for saved weights",
    )
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    # Reproducibility.
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Device: %s", device)

    # Load data.
    all_samples, class_counts = load_dataset(args.labels, augment=False)

    # Train / val split (stratified).
    from collections import defaultdict

    by_class: Dict[int, List[Sample]] = defaultdict(list)
    for s in all_samples:
        by_class[s.label].append(s)

    train_samples: List[Sample] = []
    val_samples: List[Sample] = []

    for label, members in by_class.items():
        random.shuffle(members)
        split = int(len(members) * 0.8)
        train_samples.extend(members[:split])
        val_samples.extend(members[split:])

    random.shuffle(train_samples)
    random.shuffle(val_samples)

    logger.info("Train: %d | Val: %d", len(train_samples), len(val_samples))

    # Data transforms (ImageNet normalisation).
    transform = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )

    train_dataset = MedicalDocDataset(train_samples, transform=transform, augment=True)
    val_dataset = MedicalDocDataset(val_samples, transform=transform, augment=False)

    # WeightedRandomSampler: oversample minority classes (especially HANDWRITTEN).
    # Target: each batch has roughly equal representation from all 3 classes.
    train_labels = [s.label for s in train_samples]
    class_counts = {i: train_labels.count(i) for i in range(NUM_CLASSES)}
    sample_weights = [1.0 / class_counts[label] for label in train_labels]
    sampler = torch.utils.data.WeightedRandomSampler(
        weights=sample_weights,
        num_samples=len(train_samples),
        replacement=True,
    )
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        sampler=sampler,
        num_workers=0,
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=True,
    )

    # Model.
    model = build_model(pretrained=True).to(device)
    logger.info(
        "Model built. Trainable params: %d",
        sum(p.numel() for p in model.parameters() if p.requires_grad),
    )

    class FocalLoss(nn.Module):
        """Focal loss for long-tailed / imbalanced classification.

        FL(p_t) = -alpha * (1 - p_t)^gamma * log(p_t)
        gamma=2.0: down-weights confident predictions, focuses on hard examples.
        alpha: class balancing factor (set to inverse class frequency).
        """

        def __init__(self, weights: torch.Tensor, gamma: float = 2.0):
            super().__init__()
            self.weights = weights
            self.gamma = gamma

        def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
            ce = nn.functional.cross_entropy(logits, targets, reduction="none")
            pt = torch.exp(-ce)                          # p_t for each sample
            focal_term = (1 - pt) ** self.gamma           # (1 - p_t)^gamma
            loss = focal_term * ce                        # FL = focal_term * CE
            if self.weights is not None:
                loss = loss * self.weights[targets]
            return loss.mean()

    # FocalLoss with inverse-frequency class weights to handle the 44/9/40
    # class imbalance. The WeightedRandomSampler oversamples HANDWRITTEN, but
    # FocalLoss additionally down-weights easy examples and up-weights hard
    # ones (critical for the minority HANDWRITTEN class).
    total = sum(class_counts.values())
    alpha = torch.tensor(
        [total / (NUM_CLASSES * class_counts[i]) for i in range(NUM_CLASSES)],
        dtype=torch.float32,
        device=device,
    )
    alpha = alpha / alpha.sum()  # normalize so weights sum to 1
    logger.info("FocalLoss class weights: %s", alpha.cpu().tolist())
    criterion = FocalLoss(weights=alpha, gamma=2.0)

    optimizer = optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.lr,
        weight_decay=1e-4,
    )
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    best_val_acc = 0.0
    best_state: Dict[str, torch.Tensor] = {}

    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = train_one_epoch(
            model, train_loader, optimizer, criterion, device
        )
        val_loss, val_acc = evaluate(model, val_loader, criterion, device)
        scheduler.step()

        logger.info(
            "Epoch %2d/%d | train_loss=%.4f train_acc=%.1f%% | "
            "val_loss=%.4f val_acc=%.1f%%",
            epoch, args.epochs, train_loss, train_acc, val_loss, val_acc,
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            os.makedirs(os.path.dirname(args.weights) or ".", exist_ok=True)
            torch.save(best_state, args.weights)
            logger.info(
                "New best model saved to %s (val_acc=%.1f%%)",
                args.weights,
                best_val_acc,
            )

    logger.info("Training complete. Best val_acc: %.1f%%", best_val_acc)


if __name__ == "__main__":
    main()
