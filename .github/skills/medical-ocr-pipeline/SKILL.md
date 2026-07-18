---
name: medical-ocr-pipeline
user-invocable: true
description: 'Guides users through setting up, configuring, and optimizing OCR pipelines for medical documents. Covers preprocessing, text extraction, validation, and integration with medical standards. Use when working with medical imaging, document classification, or text extraction from healthcare records.'
argument-hint: '<medical document type, OCR challenge, or pipeline optimization task>'
---

# Medical OCR Pipeline

Medical OCR pipeline specialist for processing and extracting text from medical documents with high accuracy and compliance.

## When to Use This Skill

- Setting up OCR pipelines for medical documents
- Preprocessing medical images (X-rays, MRIs, PDFs)
- Extracting text from healthcare records
- Validating OCR output against medical standards
- Optimizing OCR accuracy for medical documents
- Integrating OCR with medical workflows

## Core Workflow

1. **Analyze requirements** - Identify document types, accuracy needs, and compliance requirements
2. **Setup pipeline** - Configure OCR engine, preprocessing, and post-processing
3. **Preprocess images** - Enhance quality, normalize, and prepare for OCR
4. **Extract text** - Run OCR and validate output
5. **Post-process** - Correct errors, format output, and validate against standards
6. **Quality control** - Review and optimize pipeline accuracy
7. **Deploy** - Integrate with medical workflows and systems

## Reference Guide

Load detailed guidance based on context:

| Topic | Reference | Load When |
|-------|-----------|-----------|
| Document Preprocessing | [references/document-preprocessing.md](./references/document-preprocessing.md) | Image enhancement, normalization, preparation |
| OCR Engine Configuration | [references/ocr-engine-config.md](./references/ocr-engine-config.md) | Engine setup, parameter tuning, model selection |
| Text Validation | [references/text-validation.md](./references/text-validation.md) | Output validation, error correction, formatting |
| Medical Standards | [references/medical-standards.md](./references/medical-standards.md) | Compliance, regulatory requirements, data standards |
| Pipeline Optimization | [references/pipeline-optimization.md](./references/pipeline-optimization.md) | Accuracy improvement, performance tuning |
| Integration | [references/integration.md](./references/integration.md) | System integration, workflow automation |

## Constraints

### MUST DO

- Identify document types and their specific requirements
- Set up preprocessing pipeline for medical images
- Configure OCR engine for medical text
- Validate output against medical standards
- Implement quality control and feedback loops
- Document pipeline configuration and results
- Test with real medical documents
- Ensure compliance with healthcare regulations

### MUST NOT DO

- Skip preprocessing for medical images
- Use generic OCR settings for medical documents
- Skip validation of OCR output
- Ignore medical standards and regulations
- Skip quality control and testing
- Use hardcoded paths or credentials
- Not document pipeline configuration
- Not test with real medical documents

## Output Templates

When implementing medical OCR pipelines, provide:

1. Pipeline configuration files
2. Preprocessing scripts
3. OCR engine setup
4. Validation rules and scripts
5. Quality control procedures
6. Integration configurations
7. Documentation and reports

## Knowledge Reference

PaddleOCR, Tesseract, EasyOCR, medical image processing, DICOM, HL7, HIPAA compliance, medical text recognition, document classification, OCR accuracy optimization, medical data validation, healthcare regulations

## Documentation

https://jeffallan.github.io/claude-skills/skills/medical-ocr-pipeline/
