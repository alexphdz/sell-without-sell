"""Tests for exception hierarchy."""

from kipu_pay.core.exceptions import (
    ConfigurationError,
    DatabaseError,
    KipuError,
    ValidationError as KipuValidationError,
)


def test_base_error_defaults():
    exc = KipuError()
    assert exc.code == "internal_error"
    assert exc.status_code == 500
    assert exc.message == "An unexpected error occurred."
    assert exc.to_dict()["error"]["code"] == "internal_error"


def test_custom_message():
    exc = KipuError("Custom failure")
    assert exc.message == "Custom failure"
    assert str(exc) == "[internal_error] Custom failure"


def test_error_with_details():
    exc = KipuError("Bad input", details={"field": "name"})
    d = exc.to_dict()["error"]
    assert d["details"]["field"] == "name"


def test_configuration_error():
    exc = ConfigurationError("Missing DB URL")
    assert exc.code == "configuration_error"
    assert exc.status_code == 500
    assert "Missing DB URL" in str(exc)


def test_database_error():
    exc = DatabaseError("Connection refused")
    assert exc.code == "database_error"
    assert exc.status_code == 503


def test_validation_error():
    exc = KipuValidationError("Invalid cedula")
    assert exc.code == "validation_error"
    assert exc.status_code == 422


def test_str_no_stacktrace_leak():
    exc = KipuError("secret=abc123")
    s = str(exc)
    assert "secret" in s  # message is preserved
    # But there is no traceback or internal dump beyond code + message
    assert "Traceback" not in s
