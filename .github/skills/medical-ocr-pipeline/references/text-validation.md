# Text Validation

Validate OCR output for medical documents with specialized validation rules and error correction.

## Validation Framework

### Basic Validation
```python
import re
from typing import List, Dict, Tuple, Optional

class MedicalTextValidator:
    """Validate OCR output for medical documents."""
    
    def __init__(self):
        # Medical text patterns
        self.medical_patterns = {
            'dosage': r'\d+\s*(mg|ml|g|mcg|units?)(\s*(once|daily|twice|every|each)\s*\d+\s*(hours?|days?|weeks?|months?|years?)?)?',
            'frequency': r'\d+\s*(times?|daily|twice|every|each)\s*\d+\s*(hours?|days?|weeks?|months?|years?)',
            'route': r'(oral|iv|im|topical|inhalation|injection|infusion|transdermal|rectal|nasal|ophthalmic|otic|oral|topical|inhalation|injection|infusion|transdermal|rectal|nasal|ophthalmic|otic)',
            'strength': r'\d+\s*(mg|ml|g|mcg|units?)(\s*(per|each)\s*\d+\s*(mg|ml|g|mcg|units?))?',
            'duration': r'\d+\s*(hours?|days?|weeks?|months?|years?)',
            'instructions': r'(take|apply|use|administer|inject|infuse|use|apply|take|administer|inject|infuse)',
            'warnings': r'(caution|warning|contraindication|side effect|adverse reaction|allergy|hypersensitivity)',
            'lab_values': r'\d+\.?\d*\s*(mg/dL|g/dL|mmol/L|u/L|cells/µL|mmHg|bpm| breaths/min)',
            'medication_names': r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',
            'dates': r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
            'times': r'\d{1,2}:\d{2}\s*(AM|PM)?',
        }
        
        # Medical validation rules
        self.validation_rules = {
            'dosage_format': r'^\d+\s*(mg|ml|g|mcg|units?)$',
            'frequency_format': r'^\d+\s*(times?|daily|twice|every|each)\s*\d+\s*(hours?|days?|weeks?|months?|years?)$',
            'route_format': r'^(oral|iv|im|topical|inhalation|injection|infusion|transdermal|rectal|nasal|ophthalmic|otic)$',
            'strength_format': r'^\d+\s*(mg|ml|g|mcg|units?)(\s*(per|each)\s*\d+\s*(mg|ml|g|mcg|units?))?$',
            'duration_format': r'^\d+\s*(hours?|days?|weeks?|months?|years?)$',
        }
        
        # Common medical abbreviations
        self.medical_abbreviations = {
            'mg': 'milligrams',
            'ml': 'milliliters',
            'g': 'grams',
            'mcg': 'micrograms',
            'units': 'international units',
            'AM': 'ante meridiem',
            'PM': 'post meridiem',
            'QD': 'once daily',
            'BID': 'twice daily',
            'TID': 'three times daily',
            'QID': 'four times daily',
            'PRN': 'as needed',
            'STAT': 'immediately',
            'OD': 'right eye',
            'OS': 'left eye',
            'OU': 'both eyes',
            'HS': 'at bedtime',
            'AC': 'before meals',
            'PC': 'after meals',
            'PO': 'by mouth',
            'IV': 'intravenous',
            'IM': 'intramuscular',
            'SC': 'subcutaneous',
            'SL': 'sublingual',
            'TOP': 'topical',
            'INH': 'inhalation',
            'OPHT': 'ophthalmic',
            'OT': 'otic',
            'RECT': 'rectal',
            'NAS': 'nasal',
            'INF': 'infusion',
            'TRANS': 'transdermal',
        }
    
    def validate_text(self, text: str, document_type: str) -> Tuple[bool, List[str]]:
        """Validate OCR output text.
        
        Args:
            text: OCR output text
            document_type: Type of medical document
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Basic validation
        if not text or len(text.strip()) == 0:
            errors.append("Text is empty or contains only whitespace")
            return False, errors
        
        # Check for excessive errors
        if len(text) < 10:
            errors.append("Text is too short (less than 10 characters)")
        
        # Check for unusual characters
        unusual_chars = re.findall(r'[^\w\s\-\.:;()\[\]{}]', text)
        if len(unusual_chars) > len(text) * 0.1:
            errors.append(f"Text contains too many unusual characters: {unusual_chars}")
        
        # Document-specific validation
        if document_type == 'prescription':
            prescription_errors = self._validate_prescription(text)
            errors.extend(prescription_errors)
        elif document_type == 'lab_report':
            lab_errors = self._validate_lab_report(text)
            errors.extend(lab_errors)
        elif document_type == 'medical_note':
            note_errors = self._validate_medical_note(text)
            errors.extend(note_errors)
        
        return len(errors) == 0, errors
    
    def _validate_prescription(self, text: str) -> List[str]:
        """Validate prescription text."""
        errors = []
        
        # Check for medication name
        if not re.search(self.medical_patterns['medication_names'], text, re.IGNORECASE):
            errors.append("Prescription does not contain a medication name")
        
        # Check for dosage
        if not re.search(self.medical_patterns['dosage'], text, re.IGNORECASE):
            errors.append("Prescription does not contain a dosage")
        
        # Check for frequency
        if not re.search(self.medical_patterns['frequency'], text, re.IGNORECASE):
            errors.append("Prescription does not contain a frequency")
        
        # Check for route
        if not re.search(self.medical_patterns['route'], text, re.IGNORECASE):
            errors.append("Prescription does not contain a route")
        
        # Check for duration
        if not re.search(self.medical_patterns['duration'], text, re.IGNORECASE):
            errors.append("Prescription does not contain a duration")
        
        return errors
    
    def _validate_lab_report(self, text: str) -> List[str]:
        """Validate lab report text."""
        errors = []
        
        # Check for lab values
        if not re.search(self.medical_patterns['lab_values'], text, re.IGNORECASE):
            errors.append("Lab report does not contain lab values")
        
        # Check for reference ranges
        if not re.search(r'\d+\.?\d*\s*-\s*\d+\.?\d*', text):
            errors.append("Lab report does not contain reference ranges")
        
        return errors
    
    def _validate_medical_note(self, text: str) -> List[str]:
        """Validate medical note text."""
        errors = []
        
        # Check for clinical information
        if not re.search(r'(diagnosis|assessment|plan|history|examination)', text, re.IGNORECASE):
            errors.append("Medical note does not contain clinical information")
        
        return errors
```

### Error Correction
```python
class TextCorrector:
    """Correct common OCR errors in medical text."""
    
    def __init__(self):
        # Common OCR errors and corrections
        self.ocr_corrections = {
            'rn': 'm',
            'cl': 'd',
            '0': 'O',
            '1': 'l',
            '5': 'S',
            '8': 'B',
            'vv': 'w',
            'ii': 'll',
            'cc': 'c',
            'oo': 'o',
            'ee': 'e',
            'aa': 'a',
            'tt': 't',
            'ss': 's',
            'ff': 'f',
            'gg': 'g',
            'hh': 'h',
            'jj': 'j',
            'kk': 'k',
            'll': 'l',
            'nn': 'n',
            'pp': 'p',
            'qq': 'q',
            'rr': 'r',
            'uu': 'u',
            'vv': 'v',
            'ww': 'w',
            'xx': 'x',
            'yy': 'y',
            'zz': 'z',
            ' ': ' ',
            '\n': '\n',
            '\t': '\t',
        }
        
        # Medical abbreviation corrections
        self.abbreviation_corrections = {
            'mg': 'milligrams',
            'ml': 'milliliters',
            'g': 'grams',
            'mcg': 'micrograms',
            'units': 'international units',
            'AM': 'ante meridiem',
            'PM': 'post meridiem',
            'QD': 'once daily',
            'BID': 'twice daily',
            'TID': 'three times daily',
            'QID': 'four times daily',
            'PRN': 'as needed',
            'STAT': 'immediately',
            'OD': 'right eye',
            'OS': 'left eye',
            'OU': 'both eyes',
            'HS': 'at bedtime',
            'AC': 'before meals',
            'PC': 'after meals',
            'PO': 'by mouth',
            'IV': 'intravenous',
            'IM': 'intramuscular',
            'SC': 'subcutaneous',
            'SL': 'sublingual',
            'TOP': 'topical',
            'INH': 'inhalation',
            'OPHT': 'ophthalmic',
            'OT': 'otic',
            'RECT': 'rectal',
            'NAS': 'nasal',
            'INF': 'infusion',
            'TRANS': 'transdermal',
        }
    
    def correct_text(self, text: str, document_type: str) -> str:
        """Correct OCR errors in text.
        
        Args:
            text: OCR output text
            document_type: Type of medical document
            
        Returns:
            Corrected text
        """
        corrected = text
        
        # Apply OCR corrections
        for error, correction in self.ocr_corrections.items():
            corrected = corrected.replace(error, correction)
        
        # Apply abbreviation corrections
        for abbreviation, full_form in self.abbreviation_corrections.items():
            corrected = re.sub(
                r'\b' + re.escape(abbreviation) + r'\b',
                full_form,
                corrected,
                flags=re.IGNORECASE
            )
        
        # Document-specific corrections
        if document_type == 'prescription':
            corrected = self._correct_prescription(corrected)
        elif document_type == 'lab_report':
            corrected = self._correct_lab_report(corrected)
        elif document_type == 'medical_note':
            corrected = self._correct_medical_note(corrected)
        
        return corrected
    
    def _correct_prescription(self, text: str) -> str:
        """Correct prescription text."""
        # Common prescription corrections
        corrections = {
            r'\s+': ' ',  # Remove extra spaces
            r'\s*\n\s*': '\n',  # Normalize newlines
            r'\s*\t\s*': '\t',  # Normalize tabs
        }
        
        for pattern, replacement in corrections.items():
            text = re.sub(pattern, replacement, text)
        
        return text.strip()
    
    def _correct_lab_report(self, text: str) -> str:
        """Correct lab report text."""
        # Common lab report corrections
        corrections = {
            r'\s+': ' ',  # Remove extra spaces
            r'\s*\n\s*': '\n',  # Normalize newlines
            r'\s*\t\s*': '\t',  # Normalize tabs
        }
        
        for pattern, replacement in corrections.items():
            text = re.sub(pattern, replacement, text)
        
        return text.strip()
    
    def _correct_medical_note(self, text: str) -> str:
        """Correct medical note text."""
        # Common medical note corrections
        corrections = {
            r'\s+': ' ',  # Remove extra spaces
            r'\s*\n\s*': '\n',  # Normalize newlines
            r'\s*\t\s*': '\t',  # Normalize tabs
        }
        
        for pattern, replacement in corrections.items():
            text = re.sub(pattern, replacement, text)
        
        return text.strip()
```

### Confidence Scoring
```python
class ConfidenceScorer:
    """Score confidence of OCR output."""
    
    def __init__(self):
        # Confidence weights
        self.weights = {
            'text_length': 0.1,
            'character_accuracy': 0.3,
            'medical_terms': 0.2,
            'format_correctness': 0.2,
            'structure_validity': 0.2,
        }
    
    def score_text(self, text: str, document_type: str) -> float:
        """Score confidence of OCR output.
        
        Args:
            text: OCR output text
            document_type: Type of medical document
            
        Returns:
            Confidence score (0-1)
        """
        if not text:
            return 0.0
        
        scores = {}
        
        # Text length score
        text_length_score = min(len(text) / 1000, 1.0)
        scores['text_length'] = text_length_score
        
        # Character accuracy score
        char_accuracy_score = self._calculate_character_accuracy(text)
        scores['character_accuracy'] = char_accuracy_score
        
        # Medical terms score
        medical_terms_score = self._calculate_medical_terms_score(text, document_type)
        scores['medical_terms'] = medical_terms_score
        
        # Format correctness score
        format_correctness_score = self._calculate_format_correctness(text, document_type)
        scores['format_correctness'] = format_correctness_score
        
        # Structure validity score
        structure_validity_score = self._calculate_structure_validity(text, document_type)
        scores['structure_validity'] = structure_validity_score
        
        # Calculate weighted average
        confidence_score = sum(
            weight * score for weight, score in zip(self.weights.values(), scores.values())
        )
        
        return confidence_score
    
    def _calculate_character_accuracy(self, text: str) -> float:
        """Calculate character accuracy score."""
        # Count valid characters
        valid_chars = re.findall(r'[\w\s\-\.:;()\[\]{}]', text)
        char_accuracy = len(valid_chars) / len(text) if len(text) > 0 else 0
        return char_accuracy
    
    def _calculate_medical_terms_score(self, text: str, document_type: str) -> float:
        """Calculate medical terms score."""
        # Count medical terms
        medical_terms = 0
        for pattern in self._get_medical_patterns(document_type):
            medical_terms += len(re.findall(pattern, text, re.IGNORECASE))
        
        # Normalize score
        max_terms = 10  # Maximum expected medical terms
        medical_terms_score = min(medical_terms / max_terms, 1.0)
        return medical_terms_score
    
    def _calculate_format_correctness(self, text: str, document_type: str) -> float:
        """Calculate format correctness score."""
        # Check format correctness based on document type
        if document_type == 'prescription':
            return self._check_prescription_format(text)
        elif document_type == 'lab_report':
            return self._check_lab_report_format(text)
        elif document_type == 'medical_note':
            return self._check_medical_note_format(text)
        else:
            return 0.5
    
    def _check_prescription_format(self, text: str) -> float:
        """Check prescription format."""
        checks = []
        
        # Check for medication name
        if re.search(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', text):
            checks.append(True)
        else:
            checks.append(False)
        
        # Check for dosage
        if re.search(r'\d+\s*(mg|ml|g|mcg|units?)', text):
            checks.append(True)
        else:
            checks.append(False)
        
        # Check for frequency
        if re.search(r'\d+\s*(times?|daily|twice|every|each)\s*\d+\s*(hours?|days?|weeks?|months?|years?)', text):
            checks.append(True)
        else:
            checks.append(False)
        
        # Check for route
        if re.search(r'(oral|iv|im|topical|inhalation|injection|infusion|transdermal|rectal|nasal|ophthalmic|otic)', text):
            checks.append(True)
        else:
            checks.append(False)
        
        # Check for duration
        if re.search(r'\d+\s*(hours?|days?|weeks?|months?|years?)', text):
            checks.append(True)
        else:
            checks.append(False)
        
        return sum(checks) / len(checks) if checks else 0.5
    
    def _check_lab_report_format(self, text: str) -> float:
        """Check lab report format."""
        checks = []
        
        # Check for lab values
        if re.search(r'\d+\.?\d*\s*(mg/dL|g/dL|mmol/L|u/L|cells/µL|mmHg|bpm| breaths/min)', text):
            checks.append(True)
        else:
            checks.append(False)
        
        # Check for reference ranges
        if re.search(r'\d+\.?\d*\s*-\s*\d+\.?\d*', text):
            checks.append(True)
        else:
            checks.append(False)
        
        return sum(checks) / len(checks) if checks else 0.5
    
    def _check_medical_note_format(self, text: str) -> float:
        """Check medical note format."""
        checks = []
        
        # Check for clinical information
        if re.search(r'(diagnosis|assessment|plan|history|examination)', text, re.IGNORECASE):
            checks.append(True)
        else:
            checks.append(False)
        
        return sum(checks) / len(checks) if checks else 0.5
    
    def _get_medical_patterns(self, document_type: str) -> List[str]:
        """Get medical patterns for document type."""
        patterns = {
            'prescription': [
                r'\d+\s*(mg|ml|g|mcg|units?)',
                r'\d+\s*(times?|daily|twice|every|each)\s*\d+\s*(hours?|days?|weeks?|months?|years?)',
                r'(oral|iv|im|topical|inhalation|injection|infusion|transdermal|rectal|nasal|ophthalmic|otic)',
                r'\d+\s*(hours?|days?|weeks?|months?|years?)',
            ],
            'lab_report': [
                r'\d+\.?\d*\s*(mg/dL|g/dL|mmol/L|u/L|cells/µL|mmHg|bpm| breaths/min)',
                r'\d+\.?\d*\s*-\s*\d+\.?\d*',
            ],
            'medical_note': [
                r'(diagnosis|assessment|plan|history|examination)',
            ],
        }
        
        return patterns.get(document_type, [])
```

### Validation Pipeline
```python
class ValidationPipeline:
    """Pipeline for validating OCR output."""
    
    def __init__(self):
        self.validator = MedicalTextValidator()
        self.corrector = TextCorrector()
        self.scorer = ConfidenceScorer()
    
    def validate(self, text: str, document_type: str) -> Dict:
        """Validate OCR output text.
        
        Args:
            text: OCR output text
            document_type: Type of medical document
            
        Returns:
            Validation results
        """
        # Validate text
        is_valid, errors = self.validator.validate_text(text, document_type)
        
        # Correct text
        corrected_text = self.corrector.correct_text(text, document_type)
        
        # Score confidence
        confidence_score = self.scorer.score_text(corrected_text, document_type)
        
        # Determine if validation passes
        validation_passes = is_valid and confidence_score >= 0.7
        
        return {
            'original_text': text,
            'corrected_text': corrected_text,
            'is_valid': is_valid,
            'errors': errors,
            'confidence_score': confidence_score,
            'validation_passes': validation_passes,
        }
```

## Best Practices

- **Use comprehensive validation**: Validate both format and content
- **Implement error correction**: Correct common OCR errors
- **Score confidence**: Use confidence scoring to assess quality
- **Document validation rules**: Document validation rules and criteria
- **Test validation pipeline**: Test validation pipeline with real data
- **Use medical-specific patterns**: Use medical-specific patterns for validation
- **Validate against standards**: Validate against medical standards
- **Implement feedback loops**: Implement feedback loops for continuous improvement

## Anti-patterns

- Skipping validation (can lead to incorrect results)
- Not correcting OCR errors (can lead to incorrect results)
- Not scoring confidence (can lead to incorrect results)
- Not documenting validation rules (can lead to inconsistent validation)
- Not testing validation pipeline (can lead to incorrect results)
- Using generic validation for medical documents (can lead to incorrect results)
- Not validating against medical standards (can lead to incorrect results)
- Not implementing feedback loops (can lead to incorrect results)
- Using incorrect validation rules (can lead to incorrect results)
- Not validating with real medical documents (can lead to incorrect results)
