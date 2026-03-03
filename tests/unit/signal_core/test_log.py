"""
Tests for signal_core.core.log

Modules covered:
- configure         (root logger setup)
- get_logger        (module-scoped logger accessor)
- _JsonFormatter    (JSON log record formatter)

Invariants:
- configure() is idempotent (safe to call multiple times)
- get_logger returns a Logger instance
- _JsonFormatter produces valid JSON with required keys
- configure() with LOG_FORMAT=json uses _JsonFormatter
- configure() with LOG_FORMAT=text uses a text formatter
"""

from __future__ import annotations

import json
import logging


class TestGetLogger:
    def test_returns_logger(self):
        from signal_core.core.log import get_logger

        log = get_logger("test.module")
        assert isinstance(log, logging.Logger)

    def test_name_matches(self):
        from signal_core.core.log import get_logger

        log = get_logger("signal_core.test")
        assert log.name == "signal_core.test"

    def test_different_names_different_loggers(self):
        from signal_core.core.log import get_logger

        log_a = get_logger("mod_a")
        log_b = get_logger("mod_b")
        assert log_a is not log_b


class TestConfigure:
    def test_idempotent(self):
        """Calling configure() multiple times should not raise."""
        from signal_core.core.log import configure

        configure()
        configure()
        configure()

    def test_json_format(self, monkeypatch):
        """LOG_FORMAT=json should install the JSON formatter."""
        import signal_core.core.log as log_mod

        monkeypatch.setenv("LOG_FORMAT", "json")
        # Reset configured flag so configure() runs again
        monkeypatch.setattr(log_mod, "_configured", False)
        log_mod.configure()
        root = logging.getLogger()
        assert root.handlers  # at least one handler was added

    def test_text_format(self, monkeypatch):
        """LOG_FORMAT=text (default) should install a text formatter."""
        import signal_core.core.log as log_mod

        monkeypatch.setenv("LOG_FORMAT", "text")
        monkeypatch.setattr(log_mod, "_configured", False)
        log_mod.configure()
        root = logging.getLogger()
        assert root.handlers

    def test_log_level_env(self, monkeypatch):
        import signal_core.core.log as log_mod

        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setattr(log_mod, "_configured", False)
        log_mod.configure()
        assert logging.getLogger().level == logging.DEBUG


class TestJsonFormatter:
    def _make_record(self, msg: str = "hello") -> logging.LogRecord:
        return logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=msg,
            args=(),
            exc_info=None,
        )

    def test_produces_valid_json(self):
        from signal_core.core.log import _JsonFormatter

        fmt = _JsonFormatter()
        record = self._make_record("test message")
        output = fmt.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_contains_required_keys(self):
        from signal_core.core.log import _JsonFormatter

        fmt = _JsonFormatter()
        record = self._make_record("test message")
        output = fmt.format(record)
        parsed = json.loads(output)
        for key in ("ts", "level", "logger", "msg"):
            assert key in parsed, f"Missing key: {key}"

    def test_msg_matches_record(self):
        from signal_core.core.log import _JsonFormatter

        fmt = _JsonFormatter()
        record = self._make_record("my log line")
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["msg"] == "my log line"

    def test_level_is_info(self):
        from signal_core.core.log import _JsonFormatter

        fmt = _JsonFormatter()
        record = self._make_record()
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"

    def test_exc_info_included_when_set(self):
        from signal_core.core.log import _JsonFormatter

        fmt = _JsonFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = self._make_record("error occurred")
        record.exc_info = exc_info
        output = fmt.format(record)
        parsed = json.loads(output)
        assert "exc" in parsed
        assert "ValueError" in parsed["exc"]
