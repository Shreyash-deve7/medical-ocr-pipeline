"""
reference_ranges.py — Hepatology reference-range knowledge base.

Reference ranges are drawn from pipeline_ibm.md Section 7.1 (IBM spec) plus the
Session-4 scope list. Each entry is keyed by canonical test name and by
abbreviation so lookup is robust to either form.

GGT is sex-specific (M: 8-61, F: 5-36); ``lookup_reference_range`` accepts an
optional ``sex`` argument and defaults to male.

This module only depends on the standard library (difflib) so it is importable
and unit-testable with no heavy dependencies.
"""
import difflib
from typing import Optional

from .schema import ReferenceRange


# Canonical ranges. Each value is (low, high, unit). Sex-specific tests carry a
# nested dict keyed by sex instead of a flat tuple.
_RANGES = {
    "alanine aminotransferase": (7.0, 56.0, "U/L"),
    "alt": (7.0, 56.0, "U/L"),
    "sgpt": (7.0, 56.0, "U/L"),
    "aspartate aminotransferase": (10.0, 40.0, "U/L"),
    "ast": (10.0, 40.0, "U/L"),
    "sgot": (10.0, 40.0, "U/L"),
    "alkaline phosphatase": (44.0, 147.0, "U/L"),
    "alp": (44.0, 147.0, "U/L"),
    "gamma-glutamyl transferase": {
        "M": (8.0, 61.0, "U/L"),
        "F": (5.0, 36.0, "U/L"),
    },
    "ggt": {
        "M": (8.0, 61.0, "U/L"),
        "F": (5.0, 36.0, "U/L"),
    },
    "total bilirubin": (0.2, 1.2, "mg/dL"),
    "t.bil": (0.2, 1.2, "mg/dL"),
    "direct bilirubin": (0.0, 0.3, "mg/dL"),
    "d.bil": (0.0, 0.3, "mg/dL"),
    "indirect bilirubin": (0.2, 0.9, "mg/dL"),
    "i.bil": (0.2, 0.9, "mg/dL"),
    "albumin": (3.5, 5.0, "g/dL"),
    "alb": (3.5, 5.0, "g/dL"),
    "total protein": (6.3, 8.2, "g/dL"),
    "tp": (6.3, 8.2, "g/dL"),
    "globulin": (2.0, 3.5, "g/dL"),
    "hemoglobin": (13.5, 17.5, "g/dL"),
    "hb": (13.5, 17.5, "g/dL"),
    "prothrombin time": (11.0, 13.5, "seconds"),
    "pt": (11.0, 13.5, "seconds"),
    "inr": (0.8, 1.2, "unitless"),
    "ammonia": (15.0, 45.0, "µmol/L"),
    "nh3": (15.0, 45.0, "µmol/L"),
    "creatinine": (0.5, 1.5, "mg/dL"),
}


def _normalise_key(name: str) -> str:
    """Lower-case, strip, and fold the broken micro-sign encoding to ASCII."""
    if name is None:
        return ""
    s = str(name).lower().strip()
    # Fix µ mojibake so "µmol/L" / "μmol/L" / "umol/L" all match "ammonia".
    s = s.replace("μmol", "umol").replace("µmol", "umol")
    # Drop punctuation so "t.bil" == "total bilirubin" partially.
    s = s.replace(".", " ").replace("-", " ").replace("(", " ").replace(")", " ")
    return " ".join(s.split())


def normalise_test_key(name: str) -> str:
    """Public alias of :func:`_normalise_key` for the diagnosis rule engine."""
    return _normalise_key(name)


def lookup_reference_range(name: str, sex: str = "M") -> Optional[ReferenceRange]:
    """
    Return the canonical :class:`ReferenceRange` for ``name`` (canonical name or
    abbreviation, any case / unit encoding). Returns ``None`` if unknown.

    :param name: test name or abbreviation as it appears in OCR / extraction.
    :param sex: ``"M"`` or ``"F"`` — only affects sex-specific tests (GGT).
    """
    key = _normalise_key(name)
    if not key:
        return None

    entry = _RANGES.get(key)
    if entry is None:
        # Fuzzy fallback against all known keys (canonical + abbreviation).
        candidates = list(_RANGES.keys())
        matches = difflib.get_close_matches(key, candidates, n=1, cutoff=0.85)
        if not matches:
            return None
        entry = _RANGES[matches[0]]

    if isinstance(entry, dict):
        spec = entry.get(sex.upper()) or entry.get("M") or next(iter(entry.values()))
    else:
        spec = entry

    low, high, unit = spec
    return ReferenceRange(low=low, high=high, unit=unit)


def compute_flag(value: Optional[float], ref: Optional[ReferenceRange]) -> str:
    """
    Classify a numeric value against its reference range.

    Rules (IBM spec §6.3):
      - CRITICAL_HIGH if value > 3 × upper
      - HIGH         if value > upper
      - CRITICAL_LOW if value < 0.5 × lower
      - LOW          if value < lower
      - NORMAL       otherwise
      - UNKNOWN      if value or range is unavailable
    """
    if value is None or ref is None:
        return "UNKNOWN"
    if ref.high is not None:
        if value > 3.0 * ref.high:
            return "CRITICAL_HIGH"
        if value > ref.high:
            return "HIGH"
    if ref.low is not None:
        if ref.low > 0 and value < 0.5 * ref.low:
            return "CRITICAL_LOW"
        if value < ref.low:
            return "LOW"
    return "NORMAL"


# ── Clinical pattern rules (AASLD / Sherlock terminology) ─────────

CLINICAL_PATTERN_RULES = [
    {
        "pattern": "Hepatocellular injury pattern",
        "tests": ["alt", "sgpt", "ast", "sgot"],
        "description": (
            "Predominant elevation of ALT and/or AST (transaminases) relative to "
            "ALP/GGT, suggesting hepatocyte necrosis or inflammation (e.g. viral "
            "hepatitis, drug-induced liver injury, steatohepatitis)."
        ),
    },
    {
        "pattern": "Cholestatic pattern",
        "tests": ["alp", "ggt"],
        "description": (
            "Predominant elevation of ALP and/or GGT, suggesting biliary obstruction "
            "or cholestatic liver disease (e.g. biliary stricture, PBC, PSC, drugs)."
        ),
    },
    {
        "pattern": "Synthetic dysfunction",
        "tests": ["albumin", "alb", "pt", "prothrombin time", "inr"],
        "description": (
            "Abnormal synthetic markers (low albumin, prolonged PT/INR), suggesting "
            "impaired hepatic synthetic function seen in advanced/chronic liver disease."
        ),
    },
    {
        "pattern": "Hyperbilirubinemia",
        "tests": [
            "total bilirubin", "t.bil", "direct bilirubin", "d.bil",
            "indirect bilirubin", "i.bil",
        ],
        "description": (
            "Elevated bilirubin (conjugated and/or unconjugated), suggesting "
            "hepatobiliary dysfunction, hemolysis, or impaired conjugation/excretion."
        ),
    },
]


def get_clinical_patterns() -> list:
    """Return the structured clinical-pattern rule list (AASLD terminology)."""
    return list(CLINICAL_PATTERN_RULES)


def _alias_keys(key: str) -> set:
    """Return the set of all KB keys whose reference range equals ``key``'s."""
    entry = _RANGES.get(key)
    if entry is None:
        return set()
    result = {key}
    for k, v in _RANGES.items():
        if v == entry:
            result.add(k)
    return result