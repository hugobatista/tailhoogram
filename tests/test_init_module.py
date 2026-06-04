"""Tests for module-level logging setup."""

import importlib
import logging
import sys
from types import ModuleType


def _reload_init_module(monkeypatch, *, version_value: str = "1.2.3", raise_version: bool = False):
    """Reload __init__ module with patched metadata version."""
    import importlib.metadata as metadata

    def fake_version(_name: str) -> str:
        if raise_version:
            raise RuntimeError("boom")
        return version_value

    monkeypatch.setattr(metadata, "version", fake_version)

    if "__init__" in sys.modules:
        del sys.modules["__init__"]

    return importlib.import_module("__init__")


def test_console_handler_uses_console(monkeypatch):
    """Test ConsoleHandler routes to console methods."""
    module = _reload_init_module(monkeypatch)

    calls = []

    class FakeConsole:
        def warn(self, msg):
            calls.append(("warn", msg))

        def error(self, msg):
            calls.append(("error", msg))

        def info(self, msg):
            calls.append(("info", msg))

        def debug(self, msg):
            calls.append(("debug", msg))

        def log(self, msg):
            calls.append(("log", msg))

    module.console = FakeConsole()

    handler = module.ConsoleHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    record = logging.LogRecord("test", logging.WARNING, __file__, 1, "hello", None, None)

    handler.emit(record)

    assert calls
    assert calls[0][0] == "warn"


def test_console_handler_uses_js_console(monkeypatch):
    """Test ConsoleHandler falls back to js.console."""
    module = _reload_init_module(monkeypatch)

    calls = []

    class FakeConsole:
        def info(self, msg):
            calls.append(("info", msg))

    fake_js = ModuleType("js")
    fake_js.console = FakeConsole()  # type: ignore
    monkeypatch.setitem(sys.modules, "js", fake_js)
    module.console = None

    handler = module.ConsoleHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", None, None)

    handler.emit(record)

    assert calls == [("info", "hello")]


def test_console_handler_falls_back_when_missing_console(monkeypatch):
    """Test ConsoleHandler falls back to base handler when no console exists."""
    module = _reload_init_module(monkeypatch)
    module.console = None
    monkeypatch.delitem(sys.modules, "js", raising=False)

    calls = []

    def fake_emit(self, record):
        calls.append(record.getMessage())

    monkeypatch.setattr(logging.StreamHandler, "emit", fake_emit)

    handler = module.ConsoleHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", None, None)

    handler.emit(record)

    assert calls == ["hello"]


def test_console_handler_falls_back_on_exception(monkeypatch):
    """Test ConsoleHandler falls back when console methods fail."""
    module = _reload_init_module(monkeypatch)

    class FakeConsole:
        def info(self, msg):
            raise RuntimeError("boom")

    module.console = FakeConsole()

    calls = []

    def fake_emit(self, record):
        calls.append(record.getMessage())

    monkeypatch.setattr(logging.StreamHandler, "emit", fake_emit)

    handler = module.ConsoleHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", None, None)

    handler.emit(record)

    assert calls == ["hello"]


def test_console_handler_uses_log_for_notset(monkeypatch):
    """Test ConsoleHandler uses console.log for NOTSET level."""
    module = _reload_init_module(monkeypatch)

    calls = []

    class FakeConsole:
        def log(self, msg):
            calls.append(("log", msg))

    module.console = FakeConsole()

    handler = module.ConsoleHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    record = logging.LogRecord("test", logging.NOTSET, __file__, 1, "hello", None, None)

    handler.emit(record)

    assert calls == [("log", "hello")]


def test_console_handler_error_critical_debug(monkeypatch):
    """Test ConsoleHandler routes error, critical, and debug levels."""
    module = _reload_init_module(monkeypatch)

    calls = []

    class FakeConsole:
        def error(self, msg):
            calls.append(("error", msg))

        def debug(self, msg):
            calls.append(("debug", msg))

    module.console = FakeConsole()

    handler = module.ConsoleHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    error_record = logging.LogRecord("test", logging.ERROR, __file__, 1, "err", None, None)
    critical_record = logging.LogRecord("test", logging.CRITICAL, __file__, 1, "crit", None, None)
    debug_record = logging.LogRecord("test", logging.DEBUG, __file__, 1, "dbg", None, None)

    handler.emit(error_record)
    handler.emit(critical_record)
    handler.emit(debug_record)

    assert calls == [("error", "err"), ("error", "crit"), ("debug", "dbg")]


def test_setup_logging_sets_root_level(monkeypatch):
    """Test setup_logging configures root logger."""
    module = _reload_init_module(monkeypatch)

    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level

    try:
        module.setup_logging("DEBUG")
        assert root.level == logging.DEBUG
        assert any(isinstance(h, module.ConsoleHandler) for h in root.handlers)
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)


def test_version_fallback_when_missing(monkeypatch):
    """Test __version__ falls back when metadata fails."""
    module = _reload_init_module(monkeypatch, raise_version=True)

    assert module.__version__ == "0.0.0.dev0"
