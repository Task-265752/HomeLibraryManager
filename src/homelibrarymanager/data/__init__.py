"""Persistence layer: the hand-editable JSONL catalogue files."""

from __future__ import annotations

from .jsonl import (
    HEADER_FORMAT_KEY,
    ReadResult,
    read_records,
    write_records,
)
from .library import Library, LoadReport

__all__ = [
    "Library",
    "LoadReport",
    "ReadResult",
    "read_records",
    "write_records",
    "HEADER_FORMAT_KEY",
]
