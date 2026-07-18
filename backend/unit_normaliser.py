"""
unit_normaliser.py — Backward-compatibility re-export.

New code should import from ``backend.extraction.unit_normaliser`` directly::

    from backend.extraction.unit_normaliser import normalise_unit, normalise_value

This file is kept only to avoid breaking existing import paths.
"""
# For backward compatibility; new code should import from backend.extraction.unit_normaliser
import re
from typing import Tuple

from backend.extraction.unit_normaliser import normalise_unit, normalise_value

__all__ = ["normalise_unit", "normalise_value"]
_MICRO = "µ"

# Variants of the micro prefix that should all collapse to "µmol/L".
_MICRO_VARIANTS = ["umol", "μmol", "Âµmol", _MICRO + "mol"]

_UNIT_ALIASES = {
    "mg/dl": "mg/dL",
    "mg / dl": "mg/dL",
    "g/dl": "g/dL",
    "g / dl": "g/dL",
    "u/l": "U/L",
    "u / l": "U/L",
    "iu/l": "U/L",
    "mmol/l": "mmol/L",
    "mmol / l": "mmol/L",
    "umol/l": _MICRO + "mol/L",
    "µmol/l": _MICRO + "mol/L",
    "μmol/l": _MICRO + "mol/L",
    "µmol/l": _MICRO + "mol/L",
    "sec": "seconds",
    "secs": "seconds",
    "s": "seconds",
    "unitless": "unitless",
    "": "unitless",
}


def normalise_unit(unit: str) -> str:
    """
    Normalise a unit string to its canonical SI form.

    Fixes the broken micro-sign encoding and canonicalises common case/spacing
    variants. Returns ``"unitless"`` for empty/whitespace input.
    """
    if unit is None:
        return "unitless"
    s = str(unit).strip()

    # Universal micro-sign repair: any variant -> canonical µmol.
    for variant in ["umol", "μmol", "Âµmol", _MICRO + "mol"]:
        s = s.replace(variant, _MICRO + "mol")

    # Lower-case for alias lookup, but keep µ intact.
    lowered = s.lower()
    if lowered in _UNIT_ALIASES:
        return _UNIT_ALIASES[lowered]

    # Fallback: canonicalise spacing and split-ish artefacts.
    s = re.sub(r"\s+", "", s)  # "U / L" -> "U/L"
    s = s.replace("/l", "/L").replace("/dl", "/dL").replace("/mol", "/mol")
    if s == "":
        return "unitless"
    return s


# Trivial SI scale conversions (factor to multiply the value by).
_VALUE_CONVERSIONS = {
    # (from_unit, to_unit): factor
    ("g/L", "g/dL"): 0.1,
    ("g/dL", "g/L"): 10.0,
    ("mg/L", "mg/dL"): 0.1,
    ("mg/dL", "mg/L"): 10.0,
    (_MICRO + "mol/L", "mmol/L"): 1.0,  # already same magnitude; no-op placeholder
}


def normalise_value(value: float, unit: str) -> Tuple[float, str]:
    """
    Return ``(value, normalised_unit)``.

    The value is returned unchanged unless a trivial trivial scale conversion is
    registered for the (normalised) unit. The primary job of this module is the
    *unit string* normalisation, so unknown units pass through unchanged.
    """
    norm_unit = normalise_unit(unit)
    factor = _VALUE_CONVERSIONS.get((norm_unit, norm_unit))
    if factor is not None and factor != 1.0:
        return value * factor, norm_unit
    return value, norm_unit
