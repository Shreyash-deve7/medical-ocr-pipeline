# Document Preprocessing

Medical document preprocessing is critical for OCR accuracy. Medical images have unique characteristics that require specialized preprocessing.

## Image Enhancement

### Noise Reduction
```python
import cv2
import numpy as np

def denoise_medical_image(image):
    """Reduce noise in medical images while preserving edges.
    
    Args:
        image: Input medical image (numpy array)
        
    Returns:
        Denoised image
    """
    # Apply non-local means denoising
    denoised = cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)
    return denoised
```

### Contrast Enhancement
```python
def enhance_contrast(image):
    """Enhance contrast in medical images.
    
    Args:
        image: Input medical image
        
    Returns:
        Enhanced image
    """
    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l2 = clahe.apply(l)
    lab = cv2.merge([l2, a, b])
    enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    return enhanced
```

### Normalization
```python
def normalize_medical_image(image):
    """Normalize medical image intensity.
    
    Args:
        image: Input medical image
        
    Returns:
        Normalized image
    """
    # Apply histogram normalization
    normalized = cv2.equalizeHist(image)
    return normalized
```

## Document Classification

### Multi-Modal Classification
```python
import torch
import torch.nn as nn

class MedicalDocumentClassifier(nn.Module):
    """Classify medical documents into categories.
    
    Categories:
    - radiology (X-rays, MRIs, CT scans)
    - pathology (slides, reports)
    - prescriptions (medication lists)
    - lab_results (test reports)
    - clinical_notes (doctor notes)
    """
    
    def __init__(self, num_classes=5):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((1, 1))
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128, 256),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(256, num_classes)
        )
    
    def forward(self, x):
        features = self.features(x)
        output = self.classifier(features)
        return output
```

### Specialized Preprocessing for Different Modalities
```python
def preprocess_radiology_image(image):
    """Preprocess radiology images (X-rays, MRIs, CT scans).
    
    Args:
        image: Input radiology image
        
    Returns:
        Preprocessed image
    """
    # Remove noise
    denoised = denoise_medical_image(image)
    
    # Enhance contrast
    enhanced = enhance_contrast(denoised)
    
    # Normalize intensity
    normalized = normalize_medical_image(enhanced)
    
    # Resize to standard dimensions
    resized = cv2.resize(normalized, (1024, 1024))
    
    return resized

def preprocess_pathology_slide(image):
    """Preprocess pathology slides.
    
    Args:
        image: Input pathology slide image
        
    Returns:
        Preprocessed image
    """
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply adaptive thresholding
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 2
    )
    
    # Remove noise
    denoised = cv2.fastNlMeansDenoising(thresh)
    
    return denoised
```

## Quality Control

### Image Quality Metrics
```python
def calculate_image_quality_metrics(image):
    """Calculate quality metrics for medical images.
    
    Args:
        image: Input medical image
        
    Returns:
        Dictionary with quality metrics
    """
    metrics = {}
    
    # Calculate contrast
    contrast = np.std(image)
    metrics['contrast'] = contrast
    
    # Calculate sharpness
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    metrics['sharpness'] = laplacian_var
    
    # Calculate noise level
    denoised = cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)
    noise = np.mean(np.abs(image.astype(np.float32) - denoised.astype(np.float32)))
    metrics['noise'] = noise
    
    # Calculate resolution
    height, width = image.shape[:2]
    metrics['resolution'] = (width, height)
    
    return metrics
```

### Quality Thresholds
```python
QUALITY_THRESHOLDS = {
    'radiology': {
        'min_contrast': 30,
        'min_sharpness': 100,
        'max_noise': 10,
    },
    'pathology': {
        'min_contrast': 20,
        'min_sharpness': 50,
        'max_noise': 5,
    },
    'prescriptions': {
        'min_contrast': 40,
        'min_sharpness': 80,
        'max_noise': 8,
    },
}

def validate_image_quality(image, document_type):
    """Validate image quality against thresholds.
    
    Args:
        image: Input medical image
        document_type: Type of medical document
        
    Returns:
        Boolean indicating if image meets quality standards
    """
    metrics = calculate_image_quality_metrics(image)
    thresholds = QUALITY_THRESHOLDS.get(document_type, {})
    
    for metric, threshold in thresholds.items():
        if metrics.get(metric, 0) < threshold:
            return False, f"Quality metric {metric} ({metrics[metric]}) below threshold ({threshold})"
    
    return True, "Image quality meets standards"
```

## Best Practices

- **Preserve medical details**: Don't over-enhance images
- **Maintain aspect ratio**: Don't distort medical images
- **Use standardized formats**: DICOM, NIfTI, etc.
- **Document preprocessing steps**: Keep track of all transformations
- **Validate output quality**: Use automated quality checks
- **Test with real data**: Validate preprocessing with actual medical documents

## Anti-patterns

- Over-enhancing contrast (can hide important details)
- Skipping noise reduction (can affect OCR accuracy)
- Not validating image quality (can lead to poor OCR results)
- Using generic preprocessing for all medical document types
- Not documenting preprocessing steps (hard to reproduce)
- Skipping quality control (can lead to poor results)
