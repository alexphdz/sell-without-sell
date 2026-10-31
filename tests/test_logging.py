"""Tests for structured logging."""

import json
import logging

import structlog

from kipu_pay.core.logging import (
    clear_request_id,
    configure_logging,
    get_logger,
    set_request_id,
)


def test_configure_logging_json():
    configure_logging("DEBUG", json_format=True)
    logger = get_logger("test.json")
    # Logging happens via stdlib; verify logger is usable without raising
    logger.info("hello", key="value")
    assert True


def test_configure_logging_text():
    # Should not raise
    configure_logging("INFO", json_format=False)


def test_get_logger_returns_bound_logger():
    logger = get_logger("test.bound")
    # structlog returns a lazy proxy before first use
    assert hasattr(logger, "info")
    assert hasattr(logger, "bind")


def test_set_request_id_returns_uuid_when_none():
    rid = set_request_id()
    assert len(rid) == 36  # UUID4
    clear_request_id()


def test_set_request_id_propagates_value():
    rid = set_request_id("my-req-123")
    assert rid == "my-req-123"
    clear_request_id()


def test_clear_request_id():
    set_request_id("abc")
    clear_request_id()
    # After clearing, a new call should generate a new ID
    rid = set_request_id()
    assert rid != "abc"
    clear_request_id()
