"""Shared text and data utilities."""

from __future__ import annotations

import re
import unicodedata


def normalize_text(text: str | None) -> str:
    """Return NFC-normalized, stripped text or empty string."""
    if text is None:
        return ""
    return unicodedata.normalize("NFC", text.strip())


def clean_digits(text: str | None) -> str:
    """Extract only decimal digits from text."""
    if text is None:
        return ""
    return re.sub(r"\D", "", text)


def is_likely_numeric_id(text: str | None, min_length: int = 5) -> bool:
    """Heuristic: string contains mostly digits and meets length threshold."""
    if not text:
        return False
    digits = clean_digits(text)
    return len(digits) >= min_length and len(digits) / len(text) >= 0.5


def safe_request_id(raw: str | None, max_length: int = 64) -> str | None:
    """Sanitize a request ID: strip, limit length, remove control chars."""
    if not raw:
        return None
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", raw.strip())
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    # Reject if nothing remains after sanitization
    if not cleaned:
        return None
    return cleaned
