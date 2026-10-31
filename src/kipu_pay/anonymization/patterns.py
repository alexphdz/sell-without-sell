"""Deterministic regex and dictionary pattern detection for PII spans."""

from __future__ import annotations

import re
import uuid
from typing import Any, Sequence

from kipu_pay.anonymization.models import Action, DetectionCategory, DetectionSpan
from kipu_pay.identity.normalizers import normalize_cedula, normalize_email, normalize_name, normalize_phone
from kipu_pay.identity.resolver import IdentityResolver


# Email pattern (conservative)
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    re.UNICODE,
)

# Colombian mobile phones: 3xx xxx xxxx, +57 formats
_PHONE_RE = re.compile(
    r"(?:\+57[\s\-]?)?3\d{2}[\s\-]?\d{3}[\s\-]?\d{4}",
    re.UNICODE,
)

# Spoken email patterns: "pedro punto ramirez arroba gmail punto com"
_SPOKEN_EMAIL_RE = re.compile(
    r"\b(?:[a-záéíóúñ]+\s+(?:punto|dot)\s+)*[a-záéíóúñ]+\s+arroba\s+[a-záéíóúñ]+(?:\s+(?:punto|dot)\s+[a-z]+)+\b",
    re.IGNORECASE | re.UNICODE,
)

# Cédula-like: 6-10 digits, optionally dotted
_CEDULA_RE = re.compile(r"\b\d{1,3}(?:\.\d{3})+(?:\.\d{3})?\b|\b\d{6,10}\b")

# Strict cédula dotted pattern
_CEDULA_DOTTED_RE = re.compile(r"\b\d{1,3}(?:\.\d{3})+(?:\.\d{3})?\b")

# Amount/price patterns to AVOID (has $, COP, or looks like money)
_AMOUNT_RE = re.compile(r"\$[\d.,]+|\d+[\d.,]*\s*(?:COP|USD|EUR|\.000|,000)", re.IGNORECASE)

# Transaction IDs to avoid
_TX_ID_RE = re.compile(r"\b(?:TX|CL|KP|PG|PQR)-\d+\b", re.IGNORECASE)

# Date patterns to avoid
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{2}/\d{2}/\d{4}\b")

# Known keep list: organizations, brands, places, public figures (exact match in lowercase)
_KEEP_LIST = {
    # Banks
    "bancolombia", "davivienda", "bbva", "banco de bogotá", "banco de occidente",
    "avvillas", "colpatria", "itau", "santander", "nequi", "daviplata",
    # Brands
    "carulla", "exito", "alkosto", "falabella", "linio", "mercadolibre",
    "rapi", "rappi", "domicilios.com", "uber", "cabify", "movilidad",
    # Places
    "bogotá", "medellín", "cali", "barranquilla", "cartagena", "bucaramanga",
    "pereira", "manizales", "armenia", "cúcuta", "villavicencio", "pasto",
    "santa marta", "montería", "sincelejo", "tunja", "neiva", "popayán",
    "ibagué", "florencia", "quito", "guayaquil", "lima", "santiago", "madrid",
    # Neighborhoods that are also common words/locations (keep unless person-context)
    " laureles", "poblado", "envigado", "sabaneta", "bello", "itagüí", "estadio",
    "sotomayor", "cabecera", "altos del prado", "crespo", "bocagrande",
    "castropol", "astorga", "manila", " Patio Bonito", "牧",
    # Public figures (sample; detection should recognize fame)
}


def _is_keep_token(token: str) -> bool:
    """Check if a token is a known public entity to keep."""
    t = token.lower().strip()
    return t in _KEEP_LIST


def _is_safe_numeric(token: str) -> bool:
    """Reject pure numeric tokens that look like amounts, dates, or IDs."""
    t = token.strip()
    if _DATE_RE.match(t):
        return True
    if _TX_ID_RE.match(t):
        return True
    # Pure 4-digit year
    if re.match(r"^\d{4}$", t):
        return True
    return False


def _looks_like_cedula(text: str) -> bool:
    """Check if text looks like a Colombian cédula."""
    plain = normalize_cedula(text)
    return plain is not None and 6 <= len(plain) <= 10


def _looks_like_phone(text: str) -> bool:
    """Check if text looks like a Colombian mobile."""
    plain = normalize_phone(text)
    return plain is not None and len(plain) >= 10


def _looks_like_email(text: str) -> bool:
    """Check if text looks like an email."""
    return normalize_email(text) is not None


class PatternDetector:
    """Regex-based deterministic PII detector."""

    def detect(self, text: str, surface_path: str = "") -> list[DetectionSpan]:
        spans: list[DetectionSpan] = []
        if not text:
            return spans

        # Emails
        for m in _EMAIL_RE.finditer(text):
            spans.append(
                DetectionSpan(
                    start=m.start(),
                    end=m.end(),
                    surface_path=surface_path,
                    category=DetectionCategory.EMAIL,
                    matched_text=m.group(),
                    detector="pattern_email",
                )
            )

        # Phones
        for m in _PHONE_RE.finditer(text):
            val = m.group()
            # Skip if it looks like an amount or date fragment
            if _amount_overlap(text, m.start(), m.end()):
                continue
            if _looks_like_phone(val):
                spans.append(
                    DetectionSpan(
                        start=m.start(),
                        end=m.end(),
                        surface_path=surface_path,
                        category=DetectionCategory.PHONE,
                        matched_text=val,
                        detector="pattern_phone",
                    )
                )

        # Cédulas (dotted and plain)
        for m in _CEDULA_RE.finditer(text):
            val = m.group()
            # Avoid transaction IDs, amounts, dates
            if _TX_ID_RE.match(val):
                continue
            if _amount_overlap(text, m.start(), m.end()):
                continue
            if _is_safe_numeric(val):
                continue
            if _looks_like_cedula(val):
                spans.append(
                    DetectionSpan(
                        start=m.start(),
                        end=m.end(),
                        surface_path=surface_path,
                        category=DetectionCategory.NATIONAL_ID,
                        matched_text=val,
                        detector="pattern_cedula",
                    )
                )

        return spans


def _amount_overlap(text: str, start: int, end: int) -> bool:
    """Check if span is inside or adjacent to an amount pattern."""
    window_start = max(0, start - 3)
    window_end = min(len(text), end + 3)
    window = text[window_start:window_end]
    return bool(_AMOUNT_RE.search(window))


class RegistryDictionaryDetector:
    """Match known registry aliases and identifiers in text."""

    def __init__(self, resolver: IdentityResolver | None = None) -> None:
        self.resolver = resolver
        self._aliases: dict[str, set[uuid.UUID]] = {}
        self._identifiers: dict[str, uuid.UUID] = {}

    def load(self, resolver: IdentityResolver) -> None:
        self.resolver = resolver
        self._aliases = resolver._aliases if hasattr(resolver, "_aliases") else {}
        self._identifiers = {}
        if hasattr(resolver, "_identifiers"):
            for (itype, val), eid in resolver._identifiers.items():
                if itype in ("client_id", "employee_id", "slack_uid"):
                    self._identifiers[val] = eid

    def detect(self, text: str, surface_path: str = "") -> list[DetectionSpan]:
        spans: list[DetectionSpan] = []
        if not text or not self._aliases:
            return spans

        norm = normalize_name(text)
        # For each alias, check if it appears as whole-word in normalized text
        for alias_norm, entity_ids in self._aliases.items():
            # Use word boundaries via spaces
            pattern = re.compile(r"(?<![a-záéíóúñ])" + re.escape(alias_norm) + r"(?![a-záéíóúñ])")
            for m in pattern.finditer(norm):
                # Map normalized offset back to original text
                # Since normalize_name preserves relative ordering (just removes accents/case),
                # we approximate by searching in original text for a case-insensitive match
                orig_match = self._find_original_span(text, alias_norm)
                for start, end, matched in orig_match:
                    if len(entity_ids) == 1:
                        eid = next(iter(entity_ids))
                        spans.append(
                            DetectionSpan(
                                start=start,
                                end=end,
                                surface_path=surface_path,
                                category=DetectionCategory.PERSON,
                                matched_text=matched,
                                entity_id=eid,
                                evidence=["registry_alias"],
                                confidence="strong" if len(alias_norm.split()) >= 2 else "contextual",
                                detector="registry_dict",
                            )
                        )
                    else:
                        # Homonym: ambiguous, emit without entity_id
                        spans.append(
                            DetectionSpan(
                                start=start,
                                end=end,
                                surface_path=surface_path,
                                category=DetectionCategory.PERSON,
                                matched_text=matched,
                                evidence=["registry_alias_homonym"],
                                confidence="contextual",
                                detector="registry_dict",
                                action=Action.REVIEW,
                            )
                        )
        return spans

    def _find_original_span(self, text: str, alias_norm: str) -> list[tuple[int, int, str]]:
        """Find case/accent-insensitive occurrences of alias in original text."""
        results = []
        # Build a regex that matches the normalized form in original text
        # We use a simple approach: word-by-word case-insensitive matching
        words = alias_norm.split()
        if not words:
            return results
        # Build pattern: word boundaries around phrase
        pat_str = r"\b" + r"\s+".join(re.escape(w) for w in words) + r"\b"
        try:
            pat = re.compile(pat_str, re.IGNORECASE | re.UNICODE)
        except re.error:
            return results
        for m in pat.finditer(text):
            results.append((m.start(), m.end(), m.group()))
        return results


class SchemaDetector:
    """Schema-aware detection for structured table columns and known fields."""

    # Field → (category, action, generalization_hint)
    _FIELD_MAP: dict[str, tuple[DetectionCategory, Action, str | None]] = {
        "nombre_completo": (DetectionCategory.PERSON, Action.REPLACE, None),
        "nombre": (DetectionCategory.PERSON, Action.REPLACE, None),
        "num_doc": (DetectionCategory.NATIONAL_ID, Action.REPLACE, None),
        "documento": (DetectionCategory.NATIONAL_ID, Action.REPLACE, None),
        "cedula": (DetectionCategory.NATIONAL_ID, Action.REPLACE, None),
        "correo": (DetectionCategory.EMAIL, Action.REPLACE, None),
        "celular": (DetectionCategory.PHONE, Action.REPLACE, None),
        "direccion": (DetectionCategory.ADDRESS, Action.REPLACE, None),
        "dirección": (DetectionCategory.ADDRESS, Action.REPLACE, None),
        "fecha_nacimiento": (DetectionCategory.DOB, Action.GENERALIZE, None),
        "ocupacion": (DetectionCategory.OCCUPATION, Action.GENERALIZE, "profesional"),
        "ocupación": (DetectionCategory.OCCUPATION, Action.GENERALIZE, "profesional"),
        "barrio": (DetectionCategory.NEIGHBORHOOD, Action.GENERALIZE, None),
        "reporta_a": (DetectionCategory.REPORTS_TO, Action.REPLACE, None),
        "agente": (DetectionCategory.HANDLE, Action.REPLACE, None),
    }

    # Fields to always keep unchanged
    _KEEP_FIELDS = {
        "cliente_id", "tx_id", "radicado", "id", "tipo_doc",
        "fecha", "fecha_vinculacion", "fecha_vinculación", "ingreso",
        "monto", "tipo", "descripcion", "descripción", "canal", "estado",
        "cargo", "ciudad",
    }

    def detect_column(self, field_name: str, value: str | None, record_id: str = "") -> DetectionSpan | None:
        if not value:
            return None
        fn = field_name.lower().strip()
        if fn in self._KEEP_FIELDS:
            return None
        if fn in self._FIELD_MAP:
            cat, action, hint = self._FIELD_MAP[fn]
            return DetectionSpan(
                start=0,
                end=len(value),
                surface_path=f"{record_id}:columns:{field_name}",
                category=cat,
                matched_text=value,
                detector="schema_field",
                action=action,
                generalization=hint,
            )
        return None
