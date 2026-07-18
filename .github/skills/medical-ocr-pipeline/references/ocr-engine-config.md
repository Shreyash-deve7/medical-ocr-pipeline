# OCR Engine Configuration

Configure OCR engines for medical document processing with optimal settings for accuracy and compliance.

## PaddleOCR Configuration

### Basic Setup
```python
from paddleocr import PaddleOCR
import os

# Initialize PaddleOCR for medical documents
ocr_config = {
    'use_angle_cls': True,  # Enable text direction classification
    'use_space_char': True,  # Handle spaces between words
    'lang': 'en',  # Language
    'use_gpu': True,  # Use GPU if available
    'show_log': False,  # Suppress logs
}

ocr = PaddleOCR(**ocr_config)
```

### Medical Document Optimization
```python
# Enhanced configuration for medical documents
medical_ocr_config = {
    'use_angle_cls': True,
    'use_space_char': True,
    'lang': 'en',
    'use_gpu': True,
    'show_log': False,
    'det_model_dir': './models/det_mv3_db',  # Detection model
    'rec_model_dir': './models/rec_mv3_ocr',  # Recognition model
    'cls_model_dir': './models/cls_mv3',  # Classification model
    'det_limit_side_len': 1024,  # Limit detection side length
    'det_db_box_thresh': 0.5,  # Detection box threshold
    'det_db_unclip_ratio': 1.5,  # Detection unclip ratio
    'det_db_score_thresh': 0.5,  # Detection score threshold
    'max_batch_size': 32,  # Maximum batch size
    'use_dilation': True,  # Use dilation in detection
    'use_space_char': True,  # Handle spaces
    'drop_score': 0.5,  # Drop score threshold
}

medical_ocr = PaddleOCR(**medical_ocr_config)
```

### Model Download and Setup
```python
import wget
import tarfile
import os

def download_medical_ocr_models():
    """Download and setup PaddleOCR models for medical documents."""
    
    # Download detection model
    det_model_url = 'https://paddleocr.bj.bcebos.com/detection/en/det_mv3_db.tar'
    wget.download(det_model_url, './models/')
    
    # Download recognition model
    rec_model_url = 'https://paddleocr.bj.bcebos.com/recognition/en/rec_mv3_ocr.tar'
    wget.download(rec_model_url, './models/')
    
    # Download classification model
    cls_model_url = 'https://paddleocr.bj.bcebos.com/cls/en/cls_mv3.tar'
    wget.download(cls_model_url, './models/')
    
    # Extract models
    for model_dir in ['det_mv3_db', 'rec_mv3_ocr', 'cls_mv3']:
        tar_path = f'./models/{model_dir}.tar'
        with tarfile.open(tar_path, 'r') as tar:
            tar.extractall(path='./models/')
        os.remove(tar_path)
    
    print("Medical OCR models downloaded and setup successfully")
```

## Tesseract Configuration

### Basic Setup
```python
import pytesseract
from PIL import Image
import os

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

# Configuration for medical documents
tesseract_config = {
    'lang': 'eng',
    'psm': 6,  # Assume a single uniform block of text
    'oem': 3,  # Use LSTM OCR Engine
    'preserve_interword_spaces': '1',
    'tessedit_create_hocr': '1',
    'tessedit_write_tsv': '1',
}
```

### Medical Document Optimization
```python
# Enhanced configuration for medical documents
medical_tesseract_config = {
    'lang': 'eng',
    'psm': 4,  # Assume a single uniform block of text
    'oem': 3,  # Use LSTM OCR Engine
    'preserve_interword_spaces': '1',
    'tessedit_create_hocr': '1',
    'tessedit_write_tsv': '1',
    'tessedit_char_whitelist': 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.:-;()[]',
    'tessedit_char_blacklist': '!?@#$%^&*+=<>?/\\|',
    'textonly_box': '1',
    'apply_minimal_nnl': '1',
}
```

## EasyOCR Configuration

### Basic Setup
```python
import easyocr
import torch

# Set device
device = 'cuda' if torch.cuda.is_available() else 'cpu'

# Initialize EasyOCR for medical documents
reader = easyocr.Reader(
    ['en'],
    gpu=True if device == 'cuda' else False,
    model_storage_directory='./models/easyocr',
    download_enabled=True,
)
```

### Medical Document Optimization
```python
# Enhanced configuration for medical documents
medical_easyocr_config = {
    'lang_list': ['en'],
    'gpu': True if device == 'cuda' else False,
    'model_storage_directory': './models/easyocr',
    'download_enabled': True,
    'detector': 'standard',
    'recognizer': 'standard',
    'allowlist': 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.:-;()[]',
    'blocklist': '!?@#$%^&*+=<>?/\\|',
    'threshold': 0.5,
}

medical_reader = easyocr.Reader(**medical_easyocr_config)
```

## Engine Selection and Comparison

### Engine Selection Criteria
```python
def select_ocr_engine(document_type, image_quality, processing_requirements):
    """Select the best OCR engine for medical documents.
    
    Args:
        document_type: Type of medical document
        image_quality: Quality metrics of the image
        processing_requirements: Processing requirements
        
    Returns:
        Selected OCR engine
    """
    
    # Criteria for selection
    criteria = {
        'accuracy': {
            'PaddleOCR': 0.95,
            'Tesseract': 0.92,
            'EasyOCR': 0.94,
        },
        'speed': {
            'PaddleOCR': 2.5,  # seconds per image
            'Tesseract': 1.8,
            'EasyOCR': 2.2,
        },
        'medical_text': {
            'PaddleOCR': 0.98,
            'Tesseract': 0.85,
            'EasyOCR': 0.90,
        },
        'resource_usage': {
            'PaddleOCR': 'medium',
            'Tesseract': 'low',
            'EasyOCR': 'high',
        },
    }
    
    # Select best engine based on criteria
    if document_type == 'radiology' and image_quality['sharpness'] > 100:
        return 'PaddleOCR'
    elif document_type == 'prescriptions' and processing_requirements['speed'] < 2.0:
        return 'Tesseract'
    elif document_type == 'pathology' and image_quality['contrast'] > 30:
        return 'EasyOCR'
    else:
        # Default to PaddleOCR for medical documents
        return 'PaddleOCR'
```

## Configuration Management

### Configuration File
```python
# config/ocr_config.py
OCR_CONFIG = {
    'default_engine': 'PaddleOCR',
    'engines': {
        'PaddleOCR': {
            'use_angle_cls': True,
            'use_space_char': True,
            'lang': 'en',
            'use_gpu': True,
            'show_log': False,
            'det_model_dir': './models/det_mv3_db',
            'rec_model_dir': './models/rec_mv3_ocr',
            'cls_model_dir': './models/cls_mv3',
            'det_limit_side_len': 1024,
            'det_db_box_thresh': 0.5,
            'det_db_unclip_ratio': 1.5,
            'det_db_score_thresh': 0.5,
            'max_batch_size': 32,
            'use_dilation': True,
        },
        'Tesseract': {
            'lang': 'eng',
            'psm': 6,
            'oem': 3,
            'preserve_interword_spaces': '1',
            'tessedit_create_hocr': '1',
            'tessedit_write_tsv': '1',
        },
        'EasyOCR': {
            'lang_list': ['en'],
            'gpu': True,
            'model_storage_directory': './models/easyocr',
            'download_enabled': True,
        },
    },
    'preprocessing': {
        'denoise': True,
        'enhance_contrast': True,
        'normalize': True,
        'resize': True,
        'target_size': (1024, 1024),
    },
    'validation': {
        'min_accuracy': 0.95,
        'max_errors': 3,
        'confidence_threshold': 0.7,
    },
}
```

## Best Practices

- **Use appropriate models**: Select models trained on medical documents
- **Optimize for accuracy**: Prioritize accuracy over speed for medical documents
- **Use GPU acceleration**: Speed up processing with GPU
- **Configure for medical text**: Use appropriate character sets and language models
- **Validate configuration**: Test configuration with real medical documents
- **Monitor performance**: Track accuracy and speed metrics
- **Update models**: Regularly update OCR models with new medical text

## Anti-patterns

- Using generic OCR settings for medical documents
- Skipping model optimization for medical text
- Not using GPU acceleration when available
- Using inappropriate character sets
- Not validating configuration with real medical documents
- Ignoring performance metrics
- Not updating models regularly
- Using outdated OCR models
- Skipping preprocessing configuration
- Not testing with real medical documents
