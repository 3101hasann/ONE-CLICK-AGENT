"""Thread-safe activity log shown in the UI, mirrored to a rotating debug log file.

Only short event descriptions are recorded — never screenshots, API keys or form values.
"""
from __future__ import annotations

import logging
import re
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

_SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),                 # Google API keys
    re.compile(r"\bAQ\.[0-9A-Za-z_\-]{20,}"),               # newer Google API key format
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)\S+"),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),                # e-mail addresses
]


def redact(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            text = pattern.sub(lambda m: m.group(1) + "[redacted]", text)
        else:
            text = pattern.sub("[redacted]", text)
    return text


@dataclass(frozen=True)
class LogEntry:
    timestamp: datetime
    level: str  # INFO | OK | WARN | ERROR
    message: str

    def format(self) -> str:
        return f"{self.timestamp:%H:%M:%S}  {self.message}"


class ActivityLogger:
    def __init__(self, log_dir: Path | None = None, max_entries: int = 500):
        self._entries: deque[LogEntry] = deque(maxlen=max_entries)
        self._lock = threading.Lock()
        self._listeners: list[Callable[[LogEntry], None]] = []
        self._file_logger = logging.getLogger("cheater")
        if log_dir is not None and not self._file_logger.handlers:
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                handler = RotatingFileHandler(log_dir / "cheater.log", maxBytes=512_000,
                                              backupCount=2, encoding="utf-8")
                handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
                self._file_logger.addHandler(handler)
                self._file_logger.setLevel(logging.INFO)
            except OSError:
                pass  # file logging is optional

    def add_listener(self, listener: Callable[[LogEntry], None]) -> None:
        with self._lock:
            self._listeners.append(listener)

    def log(self, message: str, level: str = "INFO") -> LogEntry:
        entry = LogEntry(datetime.now(), level, redact(message))
        with self._lock:
            self._entries.append(entry)
            listeners = list(self._listeners)
        py_level = {"ERROR": logging.ERROR, "WARN": logging.WARNING}.get(level, logging.INFO)
        self._file_logger.log(py_level, entry.message)
        for listener in listeners:
            try:
                listener(entry)
            except Exception:  # a broken listener must never break the agent
                self._file_logger.exception("activity listener failed")
        return entry

    def info(self, message: str) -> LogEntry:
        return self.log(message, "INFO")

    def ok(self, message: str) -> LogEntry:
        return self.log(message, "OK")

    def warn(self, message: str) -> LogEntry:
        return self.log(message, "WARN")

    def error(self, message: str) -> LogEntry:
        return self.log(message, "ERROR")

    def entries(self) -> list[LogEntry]:
        with self._lock:
            return list(self._entries)
