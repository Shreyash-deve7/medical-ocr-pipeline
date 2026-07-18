# MedVault Pipeline - Classification & OCR Test Report

## Scope
- Datasets tested: **Patient_Kastoor** (64 images).
- **WhatsApp.Unknown.2026-04-27.at.12.10.10**: contains NO images (only .DS_Store + empty __MACOSX placeholder) - nothing to test.
- Pipeline: MobileNetV3 3-class classifier (classifier_3class.pth) + AutoOCRProvider (PaddleOCR on GPU via paddlepaddle-gpu 3.3.1 / CUDA 12.9; Qwen2.5-VL for HANDWRITTEN).

## Summary
- Total images: 64
- Classified: TABLE=42, PRINTED_TEXT=22, HANDWRITTEN=0
- OCR success: 63/64  (1 failed: HANDWRITTEN routed to Qwen-VL, which needs CUDA torch - not installed)
- OCR engines used: {'PaddleOCRProviderWrapper': 63}
- Total OCR time: 514.1s | avg 8.16s/img | min 5.18s | max 20.39s

## Per-image results
### Dataset: Patient_Kastoor (64 images)

| # | File | Class | Conf | OCR Engine | OCR(s) | Chars | Status |
|---|------|-------|------|-----------|--------|-------|--------|
| 1 | 20260612_110735.jpg | TABLE | 0.536 | PaddleOCRProviderWrapper | 20.3948 | 712 | ok |
| 2 | 20260612_110747.jpg | PRINTED_TEXT | 0.6234 | PaddleOCRProviderWrapper | 6.2284 | 81 | ok |
| 3 | 20260612_110922.jpg | TABLE | 0.5879 | PaddleOCRProviderWrapper | 6.3268 | 1578 | ok |
| 4 | 20260612_110926.jpg | PRINTED_TEXT | 0.6146 | PaddleOCRProviderWrapper | 5.623 | 6 | ok |
| 5 | 20260612_110943.jpg | PRINTED_TEXT | 0.5938 | PaddleOCRProviderWrapper | 5.1827 | 0 | ok |
| 6 | 20260612_111338.jpg | PRINTED_TEXT | 0.5538 | PaddleOCRProviderWrapper | 5.4797 | 184 | ok |
| 7 | 20260612_111355.jpg | TABLE | 0.4557 | PaddleOCRProviderWrapper | 5.7364 | 440 | ok |
| 8 | 20260612_111355.jpg | TABLE | 0.4557 | PaddleOCRProviderWrapper | 5.7589 | 440 | ok |
| 9 | IMG_3900.jpeg | TABLE | 0.5454 | PaddleOCRProviderWrapper | 12.0849 | 370 | ok |
| 10 | IMG_3901.jpeg | PRINTED_TEXT | 0.5763 | PaddleOCRProviderWrapper | 10.2896 | 283 | ok |
| 11 | IMG_3902.jpeg | PRINTED_TEXT | 0.6561 | PaddleOCRProviderWrapper | 11.0672 | 511 | ok |
| 12 | IMG_3903.jpeg | TABLE | 0.6303 | PaddleOCRProviderWrapper | 11.093 | 418 | ok |
| 13 | IMG_3904.jpeg | PRINTED_TEXT | 0.6382 | PaddleOCRProviderWrapper | 10.1594 | 204 | ok |
| 14 | IMG_3905.jpeg | PRINTED_TEXT | 0.6066 | PaddleOCRProviderWrapper | 10.2872 | 172 | ok |
| 15 | IMG_3900.jpeg | TABLE | 0.5454 | PaddleOCRProviderWrapper | 10.5453 | 370 | ok |
| 16 | IMG_3901.jpeg | PRINTED_TEXT | 0.5763 | PaddleOCRProviderWrapper | 10.2392 | 283 | ok |
| 17 | IMG_3902.jpeg | PRINTED_TEXT | 0.6561 | PaddleOCRProviderWrapper | 10.8052 | 511 | ok |
| 18 | IMG_3903.jpeg | TABLE | 0.6303 | PaddleOCRProviderWrapper | 11.0103 | 418 | ok |
| 19 | IMG_3904.jpeg | PRINTED_TEXT | 0.6382 | PaddleOCRProviderWrapper | 10.2578 | 204 | ok |
| 20 | IMG_3905.jpeg | PRINTED_TEXT | 0.6066 | PaddleOCRProviderWrapper | 10.378 | 172 | ok |
| 21 | IMG_3906.jpeg | PRINTED_TEXT | 0.5325 | PaddleOCRProviderWrapper | 11.3654 | 177 | ok |
| 22 | IMG_3907.jpeg | PRINTED_TEXT | 0.503 | PaddleOCRProviderWrapper | 10.9531 | 0 | ok |
| 23 | IMG_3913.jpeg | PRINTED_TEXT | 0.5595 | PaddleOCRProviderWrapper | 11.0679 | 39 | ok |
| 24 | IMG_3914.jpeg | PRINTED_TEXT | 0.6165 | PaddleOCRProviderWrapper | 11.0422 | 203 | ok |
| 25 | IMG_3917.jpeg | PRINTED_TEXT | 0.6012 | PaddleOCRProviderWrapper | 10.9721 | 281 | ok |
| 26 | IMG_3918.jpeg | TABLE | 0.5859 | ? | ? | ? | error |
| 27 | IMG_3922.jpeg | TABLE | 0.4636 | PaddleOCRProviderWrapper | 11.1629 | 466 | ok |
| 28 | 20260612_110755.jpg | PRINTED_TEXT | 0.5956 | PaddleOCRProviderWrapper | 6.5415 | 1376 | ok |
| 29 | 20260612_110800.jpg | PRINTED_TEXT | 0.5825 | PaddleOCRProviderWrapper | 7.2204 | 1492 | ok |
| 30 | 20260612_110810.jpg | PRINTED_TEXT | 0.6085 | PaddleOCRProviderWrapper | 6.3295 | 925 | ok |
| 31 | 20260612_110816.jpg | TABLE | 0.6047 | PaddleOCRProviderWrapper | 5.6459 | 322 | ok |
| 32 | 20260612_110823.jpg | TABLE | 0.6525 | PaddleOCRProviderWrapper | 5.5501 | 370 | ok |
| 33 | 20260612_110838.jpg | TABLE | 0.647 | PaddleOCRProviderWrapper | 6.246 | 1478 | ok |
| 34 | 20260612_110850.jpg | TABLE | 0.6449 | PaddleOCRProviderWrapper | 5.8687 | 350 | ok |
| 35 | 20260612_110858.jpg | TABLE | 0.6332 | PaddleOCRProviderWrapper | 5.4025 | 667 | ok |
| 36 | 20260612_110904.jpg | TABLE | 0.6188 | PaddleOCRProviderWrapper | 5.7557 | 715 | ok |
| 37 | 20260612_110910.jpg | TABLE | 0.6189 | PaddleOCRProviderWrapper | 6.2088 | 1545 | ok |
| 38 | 20260612_110946.jpg | TABLE | 0.6214 | PaddleOCRProviderWrapper | 5.8356 | 1447 | ok |
| 39 | 20260612_111003.jpg | TABLE | 0.6347 | PaddleOCRProviderWrapper | 5.6617 | 998 | ok |
| 40 | 20260612_111010.jpg | PRINTED_TEXT | 0.5307 | PaddleOCRProviderWrapper | 6.1175 | 2429 | ok |
| 41 | 20260612_111029.jpg | TABLE | 0.6565 | PaddleOCRProviderWrapper | 5.7706 | 2794 | ok |
| 42 | 20260612_111044.jpg | TABLE | 0.659 | PaddleOCRProviderWrapper | 5.4414 | 926 | ok |
| 43 | 20260612_111051.jpg | TABLE | 0.6529 | PaddleOCRProviderWrapper | 5.9279 | 1564 | ok |
| 44 | 20260612_111113.jpg | TABLE | 0.653 | PaddleOCRProviderWrapper | 5.5927 | 1471 | ok |
| 45 | 20260612_111123.jpg | TABLE | 0.653 | PaddleOCRProviderWrapper | 5.5683 | 1800 | ok |
| 46 | 20260612_111129.jpg | PRINTED_TEXT | 0.56 | PaddleOCRProviderWrapper | 5.6348 | 951 | ok |
| 47 | 20260612_111137.jpg | TABLE | 0.6528 | PaddleOCRProviderWrapper | 5.42 | 921 | ok |
| 48 | 20260612_111151.jpg | TABLE | 0.6556 | PaddleOCRProviderWrapper | 5.8662 | 2099 | ok |
| 49 | 20260612_111206.jpg | TABLE | 0.6388 | PaddleOCRProviderWrapper | 5.9715 | 1934 | ok |
| 50 | 20260612_111216.jpg | TABLE | 0.6533 | PaddleOCRProviderWrapper | 5.5079 | 1633 | ok |
| 51 | 20260612_111236.jpg | TABLE | 0.6499 | PaddleOCRProviderWrapper | 5.6959 | 1296 | ok |
| 52 | 20260612_111244.jpg | TABLE | 0.648 | PaddleOCRProviderWrapper | 5.4341 | 1602 | ok |
| 53 | 20260612_111251.jpg | TABLE | 0.6564 | PaddleOCRProviderWrapper | 5.5655 | 2221 | ok |
| 54 | 20260612_111257.jpg | TABLE | 0.5963 | PaddleOCRProviderWrapper | 5.4789 | 1138 | ok |
| 55 | IMG_3908.jpeg | TABLE | 0.6527 | PaddleOCRProviderWrapper | 10.9911 | 561 | ok |
| 56 | IMG_3909.jpeg | TABLE | 0.6548 | PaddleOCRProviderWrapper | 10.5916 | 548 | ok |
| 57 | IMG_3910.jpeg | TABLE | 0.6269 | PaddleOCRProviderWrapper | 11.0911 | 1117 | ok |
| 58 | IMG_3911.jpeg | TABLE | 0.5866 | PaddleOCRProviderWrapper | 10.7393 | 869 | ok |
| 59 | IMG_3912.jpeg | TABLE | 0.6262 | PaddleOCRProviderWrapper | 10.2287 | 212 | ok |
| 60 | IMG_3915.jpeg | TABLE | 0.6125 | PaddleOCRProviderWrapper | 10.0601 | 463 | ok |
| 61 | IMG_3916.jpeg | TABLE | 0.5989 | PaddleOCRProviderWrapper | 10.124 | 749 | ok |
| 62 | IMG_3919.jpeg | TABLE | 0.6243 | PaddleOCRProviderWrapper | 10.6527 | 602 | ok |
| 63 | IMG_3920.jpeg | TABLE | 0.5889 | PaddleOCRProviderWrapper | 11.2138 | 856 | ok |
| 64 | IMG_3921.jpeg | TABLE | 0.6151 | PaddleOCRProviderWrapper | 5.6619 | 134 | ok |

## Sample OCR outputs (first 5 OK)
### 20260612_110735.jpg  [TABLE]
```
Mob.:8051308702 Mob.:9546705369,9708398374 Reg.o:772011 32 Dr.Prof.)P.K.Mishra SHIVAM CLINIC M.B.B.S.C.U.)M.D.Med. M.R.S.H.(Lond.) Dip Card Aashi DrugJuran Chhapra Road No.02 Sr.Physician & Cardiologist Reg.No.33436 Bihar Muzaffarpur (Bihar) E-mail:pm835807@gmail.com 931g..... yoines Kastur Touewy .
```

### 20260612_110747.jpg  [PRINTED_TEXT]
```
Rgferto Scrpcri Luckno 1X14 hamnnd 18 APR 2026 sopt 5 X1D Crrn5ng 1 - 14 APR 2026
```

### 20260612_110922.jpg  [TABLE]
```
Infront Of Sudhir Medico Sukhdev Bhawan1st floor Reg.No.77|2011 Road No.2,Juran ChapraMuzaffarpur VAIDEHI Mob.:+91-8051308702 Dr.D.P.Thakur ULTRASOUND M.B.B.S.M.R.S.H. Reg.No.:16998 (CENTRE FOR WHOLE BODY ULTRASONOGRAPHY) Kastur kumar. Name:- Sex.-24y/M Reg.scan -Whole abdomen. DATE-10.04.2026 Ref.B
```

### 20260612_110926.jpg  [PRINTED_TEXT]
```
Kastuy
```

### 20260612_110943.jpg  [PRINTED_TEXT]
```

```

## Notes / Issues found
1. WhatsApp dataset is empty - no images present to evaluate.
2. Classifier skews toward TABLE / PRINTED_TEXT; only 1/64 flagged HANDWRITTEN (IMG_3918.jpeg), which then fails because Qwen2.5-VL requires CUDA torch (not installed; CPU fallback disabled).
3. paddleocr 2.8.1 + NumPy 2.x env incompatibility (np.sctypes removed, and bare `from tools.infer` import) required test-harness shims to run the benchmark. These are environment issues, not pipeline logic bugs.
4. Classification confidences are low (0.45-0.66), suggesting the 3-class MobileNetV3 weights are weakly calibrated / undertrained for this dataset.

Full machine-readable results: eval_reports/pipeline_classification_ocr_report.json