"""Tests for Kippy API utils."""

from datetime import datetime, timedelta, timezone

from custom_components.kippy.api._utils import (
    _decode_json,
    _get_return_code,
    _redact_json,
    _return_code_error,
    _treat_401_as_success,
    _tz_hours,
    _weeks_param,
)


def test_redact_json():
    """Test redacting JSON strings."""
    raw = '{"app_code": "secret", "safe": "data"}'
    redacted = _redact_json(raw)
    assert '"***"' in redacted
    assert '"data"' in redacted
    # Invalid JSON
    assert _redact_json("invalid") == "invalid"


def test_decode_json():
    """Test decoding JSON safely."""
    assert _decode_json('{"key": "value"}') == {"key": "value"}
    assert _decode_json("invalid") is None


def test_get_return_code():
    """Test extracting return codes."""
    assert _get_return_code({"return": 5}) == 5
    assert _get_return_code({"Result": 10}) == 10
    assert _get_return_code({"return": True}) is True
    assert _get_return_code(None) is None
    assert _get_return_code([]) is None


def test_return_code_error():
    """Test human readable error codes."""
    assert "Invalid credentials" in _return_code_error(108)
    assert "Unknown error" in _return_code_error(999)


def test_treat_401_as_success():
    """Test 401 success handling."""
    assert _treat_401_as_success("path", {"return": 0}) is True
    assert _treat_401_as_success("path", {"return": True}) is True
    assert _treat_401_as_success("path", {"return": False}) is False
    assert _treat_401_as_success("path", {"return": 999}) is False
    assert _treat_401_as_success("path", {}) is False


def test_weeks_param():
    """Test ISO weeks parameter generation."""
    start = datetime(2026, 1, 1)
    end = datetime(2026, 1, 8)
    weeks = _weeks_param(start, end)
    assert "year" in weeks
    assert "number" in weeks


def test_tz_hours():
    """Test timezone offset hours."""
    dt = datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=2)))
    assert _tz_hours(dt) == 2.0
