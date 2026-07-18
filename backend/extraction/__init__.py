"""
backend.extraction — Modular extraction layer.

Exports:
    LabReport, LabResult, ReferenceRange, DiagnosisResult, SummaryResponse
    normalise_unit, normalise_value
    lookup_reference_range, compute_flag, get_clinical_patterns
    format_with_llm
"""
from .schema import (
    ReferenceRange,
    LabResult,
    LabReport,
    ClinicalPattern,
    AbnormalValue,
    DiagnosisResult,
    SummaryResponse,
    RegisterReq,
    LoginReq,
    DoctorRegisterReq,
    AnalyzeReq,
    ProviderReq,
    PatientProfileReq,
    AllergyReq,
    ConditionReq,
    MedicationReq,
    VitalReq,
    PrescriptionReq,
    ClinicalNoteReq,
)
from .unit_normaliser import normalise_unit, normalise_value
from .reference_ranges import (
    lookup_reference_range,
    compute_flag,
    get_clinical_patterns,
    normalise_test_key,
)
from .formatter import format_with_llm

__all__ = [
    # Schema
    "ReferenceRange",
    "LabResult",
    "LabReport",
    "ClinicalPattern",
    "AbnormalValue",
    "DiagnosisResult",
    "SummaryResponse",
    "RegisterReq",
    "LoginReq",
    "DoctorRegisterReq",
    "AnalyzeReq",
    "ProviderReq",
    "PatientProfileReq",
    "AllergyReq",
    "ConditionReq",
    "MedicationReq",
    "VitalReq",
    "PrescriptionReq",
    "ClinicalNoteReq",
    # Unit normalisation
    "normalise_unit",
    "normalise_value",
    # Reference ranges
    "lookup_reference_range",
    "compute_flag",
    "get_clinical_patterns",
    "normalise_test_key",
    # LLM formatter
    "format_with_llm",
]