"""Modules 03/04 — Identity Registry & Resolution."""

from kipu_pay.identity.db_models import (
    IdentityAlias,
    IdentityBase,
    IdentityConflict,
    IdentityEntity,
    IdentityIdentifier,
    IdentitySourceLink,
)
from kipu_pay.identity.models import (
    ConfidenceLevel,
    RegistryResult,
    ResolutionContext,
    ResolutionResult,
    ResolutionStatus,
)
from kipu_pay.identity.registry import RegistryService, deterministic_entity_id
from kipu_pay.identity.resolver import IdentityResolver

__all__ = [
    "IdentityBase",
    "IdentityEntity",
    "IdentityIdentifier",
    "IdentityAlias",
    "IdentitySourceLink",
    "IdentityConflict",
    "RegistryResult",
    "ResolutionContext",
    "ResolutionResult",
    "ResolutionStatus",
    "ConfidenceLevel",
    "RegistryService",
    "IdentityResolver",
    "deterministic_entity_id",
]
