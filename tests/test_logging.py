"""Tests for logging module."""

import logging
import pytest

from moldb.logging import (
    setup_logging,
    get_logger,
    build_uvicorn_log_config,
    API_LOGGER,
    BUILDER_LOGGER,
    STORE_LOGGER,
)


class TestSetupLogging:
    def test_console_only(self):
        """Logger has StreamHandler, no FileHandler."""
        logger = setup_logging("moldb.test.console", level="DEBUG")
        assert logger.level == logging.DEBUG
        handlers = logger.handlers
        assert len(handlers) == 1
        assert isinstance(handlers[0], logging.StreamHandler)

    def test_with_file(self, tmp_path):
        """Logger has both StreamHandler and FileHandler, file is created."""
        log_file = tmp_path / "test.log"
        logger = setup_logging(
            "moldb.test.file", level="INFO", log_file=str(log_file),
        )
        handlers = logger.handlers
        assert len(handlers) == 2
        assert any(isinstance(h, logging.StreamHandler) for h in handlers)
        assert any(isinstance(h, logging.FileHandler) for h in handlers)
        # Emit a message to create the file
        logger.info("test message")
        assert log_file.exists()
        content = log_file.read_text()
        assert "test message" in content

    def test_idempotent(self):
        """Calling setup_logging twice does not duplicate handlers."""
        name = "moldb.test.idempotent"
        setup_logging(name, level="INFO")
        setup_logging(name, level="INFO")
        logger = logging.getLogger(name)
        # Should have exactly 1 handler (no file = console only)
        assert len(logger.handlers) == 1

    def test_invalid_level_raises(self):
        with pytest.raises(ValueError, match="log_level"):
            setup_logging("moldb.test.bad", level="TRACE")

    def test_propagate_false(self):
        """Logger should not propagate to root to avoid double-logging."""
        logger = setup_logging("moldb.test.propagate")
        assert logger.propagate is False


class TestGetLogger:
    def test_returns_logger(self):
        logger = get_logger("moldb.test.get")
        assert isinstance(logger, logging.Logger)

    def test_same_name_same_instance(self):
        a = get_logger("moldb.test.same")
        b = get_logger("moldb.test.same")
        assert a is b


class TestBuildUvicornLogConfig:
    def test_console_only(self):
        cfg = build_uvicorn_log_config(level="INFO")
        assert cfg["version"] == 1
        assert "default" in cfg["handlers"]
        assert "access" in cfg["handlers"]
        assert "default_file" not in cfg["handlers"]
        assert cfg["loggers"]["uvicorn"]["handlers"] == ["default"]
        assert cfg["loggers"]["uvicorn.access"]["handlers"] == ["access"]

    def test_with_file(self):
        cfg = build_uvicorn_log_config(log_file="/tmp/uvicorn.log", level="DEBUG")
        assert "default_file" in cfg["handlers"]
        assert "access_file" in cfg["handlers"]
        assert cfg["loggers"]["uvicorn"]["handlers"] == ["default", "default_file"]
        assert cfg["loggers"]["uvicorn.access"]["handlers"] == ["access", "access_file"]
        assert cfg["loggers"]["uvicorn"]["level"] == "DEBUG"


class TestLoggerConstants:
    def test_api_logger_name(self):
        assert API_LOGGER == "moldb.api"

    def test_builder_logger_name(self):
        assert BUILDER_LOGGER == "moldb.builder"

    def test_store_logger_name(self):
        assert STORE_LOGGER == "moldb.store"
