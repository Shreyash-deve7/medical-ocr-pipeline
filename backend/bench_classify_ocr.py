import sys, os, time, json, traceback
from pathlib import Path

# Compatibility shim: paddleocr 2.8.1 references np.sctypes, removed in NumPy 2.0.
import numpy as np
if not hasattr(np, "sctypes"):
    np.sctypes = {
        "int": [np.int8, np.int16, np.int32, np.int64],
        "uint": [np.uint8, np.uint16, np.uint32, np.uint64],
        "float": [np.float16, np.float32, np.float64],
        "complex": [np.complex64, np.complex128],
        "others": [bool, object, bytes, str, np.void],
    }

ROOT = r"C:\Users\oliad\Desktop\intern-ocr-paddleocr-aditya\pipeline_v1"
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
sys.path.append(ROOT)  # project root LAST so paddleocr's tools package is not shadowed by root tools.py

# Workaround: paddleocr 2.8.1 does `from tools.infer import predict_system` (absolute).
# Its `tools` package lives in site-packages/paddleocr/tools, so we prepend that
# directory to sys.path so the bare `tools` import resolves to paddleocr's tools.
import site
for _sp in site.getsitepackages():
    _po = os.path.join(_sp, "paddleocr")
    if os.path.isdir(os.path.join(_po, "tools")):
        sys.path.insert(0, _po)
        break

import cv2
import numpy as np
from document_classifier import DocumentClassifier, DEFAULT_WEIGHTS_PATH
from services.ocr_service import AutoOCRProvider

DATASETS = {"Patient_Kastoor": os.path.join(ROOT, "Patient_Kastoor")}
EXT = (".jpg", ".jpeg", ".png", ".pdf")

def collect():
    imgs = []
    for ds, base in DATASETS.items():
        for p in sorted(Path(base).rglob("*")):
            if p.is_file() and p.suffix.lower() in EXT and p.name != ".DS_Store":
                imgs.append((ds, str(p)))
    return imgs

def main():
    clf = DocumentClassifier(weights_path=DEFAULT_WEIGHTS_PATH)
    rows, imgs = [], collect()
    print(f"Collected {len(imgs)} images")
    for ds, path in imgs:
        rel = os.path.relpath(path, ROOT)
        rec = {"dataset": ds, "path": rel, "file": os.path.basename(path)}
        try:
            img = cv2.imread(path)
            if img is None:
                from PIL import Image
                img = cv2.cvtColor(np.array(Image.open(path).convert("RGB")), cv2.COLOR_RGB2BGR)
            t0 = time.time()
            cres = clf.predict_3class(img)
            cls, conf = cres.doc_class, round(getattr(cres, "confidence", 0.0), 4)
            rec.update(class_=cls, class_conf=conf, classify_s=round(time.time()-t0, 4))
            t1 = time.time()
            ocr = AutoOCRProvider()
            text = ocr.extract_text(path, "image")
            rec["ocr_engine"] = type(ocr.last_provider).__name__ if getattr(ocr, "last_provider", None) else "n/a"
            rec["ocr_s"] = round(time.time() - t1, 4)
            rec["ocr_chars"] = len(text or "")
            rec["ocr_preview"] = (text or "")[:300].replace("\n", " ")
            rec["status"] = "ok"
        except Exception as e:
            rec.update(status="error", error=f"{type(e).__name__}: {e}",
                       trace=traceback.format_exc().splitlines()[-3:])
        rows.append(rec)
        print(f"[{len(rows):02d}/{len(imgs)}] {rel} -> {rec.get('class_')} "
              f"(c={rec.get('class_conf')}) ocr={rec.get('ocr_s')}s "
              f"chars={rec.get('ocr_chars')} [{rec['status']}]", flush=True)
    out = os.path.join(ROOT, "eval_reports", "pipeline_classification_ocr_report.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(rows, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    from collections import Counter
    cnt = Counter(r.get("class_", "ERROR") for r in rows)
    oks = [r for r in rows if r["status"] == "ok"]
    tot = sum(r.get("ocr_s", 0) for r in oks)
    print("\n=== SUMMARY ===")
    print("total:", len(rows), "by class:", dict(cnt), "ok:", len(oks), "errors:", len(rows)-len(oks))
    print(f"total OCR time: {tot:.2f}s avg/img: {(tot/len(oks) if oks else 0):.2f}s")
    print("report ->", out)

if __name__ == "__main__":
    main()
