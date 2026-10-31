"""Deterministic identifier and name normalization utilities.

Normalized forms are used for matching only. Original values are always
preserved separately and never modified.
"""

from __future__ import annotations

import re
import unicodedata

_CEDULA_SEPARATORS = re.compile(r"[.\s\-]")
_WHITESPACE = re.compile(r"\s+")
_NON_DIGIT = re.compile(r"\D")


def normalize_cedula(value: str) -> str | None:
    """Strip formatting separators from a cédula; keep digits only.

    Returns None when the value does not look like a cédula
    (6–10 digits after cleanup).
    """
    if not value:
        return None
    cleaned = _CEDULA_SEPARATORS.sub("", value.strip())
    if not cleaned.isdigit():
        return None
    if not (6 <= len(cleaned) <= 10):
        return None
    return cleaned


def normalize_email(value: str) -> str | None:
    """Conservative email normalization: trim + lowercase domain only.

    The local part keeps its case, dots and plus tags untouched.
    """
    if not value:
        return None
    v = value.strip()
    if "@" not in v or v.count("@") != 1:
        return None
    local, _, domain = v.partition("@")
    if not local or not domain or "." not in domain:
        return None
    return f"{local}@{domain.lower()}"


def normalize_phone(value: str) -> str | None:
    """Normalize phone formatting to digits, preserving country prefix.

    Keeps a leading '+' country context when present.
    """
    if not value:
        return None
    v = value.strip()
    has_plus = v.startswith("+")
    digits = _NON_DIGIT.sub("", v)
    if len(digits) < 7 or len(digits) > 15:
        return None
    return f"+{digits}" if has_plus else digits


def normalize_name(value: str) -> str:
    """Unicode-aware normalization for name matching.

    NFKD-decompose, strip combining marks, casefold, collapse whitespace.
    Original names are never modified by callers; this is lookup-only.
    """
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _WHITESPACE.sub(" ", without_accents).strip().casefold()
