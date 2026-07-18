"""
schema.py — Pydantic v2 models for the MedVault Hepatology lab-report JSON.

Mirrors the IBM spec (pipeline_ibm.md Section 6.4) schema used by the
ExtractionAgent and ValidationAgent:

    LabReport
      ├── lab_results: List[LabResult]
      ├── document_metadata: Optional[dict]
      └── pipeline_metadata:  Optional[dict]

    LabResult
      ├── test_name, test_abbreviation?, value?, unit
      ├── reference_range: ReferenceRange
      ├── flag: Literal[HIGH|LOW|CRITICAL_HIGH|CRITICAL_LOW|NORMAL|UNKNOWN]
      └── clinical_significance?

``document_metadata`` and ``pipeline_metadata`` are optional so the
extraction-only ``lab_results`` JSON validates on its own while still honouring
the full IBM §6.4 contract when present.
"""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ReferenceRange(BaseModel):
    """Reference interval for a single lab test."""

    low: Optional[float] = None
    high: Optional[float] = None
    unit: str


class LabResult(BaseModel):
    """A single extracted laboratory test result."""

    test_name: str
    test_abbreviation: Optional[str] = None
    value: Optional[float] = None
    unit: str
    reference_range: ReferenceRange
    flag: Literal[
        "HIGH",
        "LOW",
        "CRITICAL_HIGH",
        "CRITICAL_LOW",
        "NORMAL",
        "UNKNOWN",
    ]
    clinical_significance: Optional[str] = None


class LabReport(BaseModel):
    """Validated Hepatology lab report matching the IBM spec §6.4 schema."""

    lab_results: List[LabResult]
    document_metadata: Optional[Dict[str, Any]] = None
    pipeline_metadata: Optional[Dict[str, Any]] = None


# ── Diagnosis (Agent 6) models ───────────────────────────────────

class ClinicalPattern(BaseModel):
    """A recognised clinical pattern grouping related abnormalities."""

    pattern: str
    supporting_tests: List[str] = Field(default_factory=list)
    description: str = ""


class AbnormalValue(BaseModel):
    """A single abnormal lab value flagged by the diagnosis engine."""

    test: str
    value: Optional[float] = None
    flag: str
    note: Optional[str] = None


class DiagnosisResult(BaseModel):
    """
    Structured diagnosis support output.

    ``llm_narrative`` carries any free-text narrative the LLM produced; it is
    ``None`` when the rule-based fallback was used (no LLM client).
    """

    clinical_patterns: List[ClinicalPattern] = Field(default_factory=list)
    abnormal_values: List[AbnormalValue] = Field(default_factory=list)
    urgent_flags: List[str] = Field(default_factory=list)
    suggested_followup: List[str] = Field(default_factory=list)
    summary_for_doctor: str
    llm_narrative: Optional[str] = None


# ── Summary (Agent 8) models ─────────────────────────────────────

class SummaryResponse(BaseModel):
    """Doctor-facing structured summary of a diagnosis."""

    summary: str = ""
    flags: List[Dict[str, Any]] = Field(default_factory=list)
    critical_alerts: List[str] = Field(default_factory=list)
    discussion_points: List[str] = Field(default_factory=list)


# ── REST API request models ─────────────────────────────────────

class RegisterReq(BaseModel):
    phone: str
    password: str
    name: str = ""


class LoginReq(BaseModel):
    phone: str
    password: str


class DoctorRegisterReq(BaseModel):
    phone: str
    password: str
    name: str
    specialization: str = ""
    license_number: str = ""
    email: str = ""


class AnalyzeReq(BaseModel):
    report_id: str
    ocr_provider_id: str = ""
    ai_provider_id: str = ""
    api_key: str = ""


class ProviderReq(BaseModel):
    kind: str
    name: str
    engine: str
    config: dict = Field(default_factory=dict)
    is_default: bool = False


class PatientProfileReq(BaseModel):
    name: str = ""
    date_of_birth: str = ""
    gender: str = ""
    blood_group: str = ""
    email: str = ""
    address: str = ""
    emergency_contact: str = ""
    emergency_phone: str = ""


class AllergyReq(BaseModel):
    allergen: str
    severity: str = "mild"
    reaction: str = ""


class ConditionReq(BaseModel):
    name: str
    status: str = "active"
    diagnosed_at: str = ""
    notes: str = ""


class MedicationReq(BaseModel):
    name: str
    dosage: str = ""
    frequency: str = ""
    status: str = "active"
    prescribed_by: str = ""
    start_date: str = ""
    end_date: str = ""


class VitalReq(BaseModel):
    patient_id: str
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    heart_rate: Optional[int] = None
    temperature: Optional[float] = None
    spo2: Optional[int] = None
    respiratory_rate: Optional[int] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    blood_sugar: Optional[float] = None
    notes: str = ""


class PrescriptionReq(BaseModel):
    patient_id: str
    doctor_name: str = ""
    diagnosis: str = ""
    notes: str = ""
    items: list[dict] = Field(default_factory=list)


class ClinicalNoteReq(BaseModel):
    patient_id: str
    doctor_name: str = ""