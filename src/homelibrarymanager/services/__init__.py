"""Service layer: use cases that sit between the data layer and the UI.

Nothing here imports Qt.  That is what lets the whole startup flow - choosing a
folder, validating the files, deciding which screen to show - be tested without
a display, and what will let import/export be added later without touching the
persistence code.
"""

from __future__ import annotations

from .startup import (
    DataState,
    StartupPlan,
    StartupResult,
    add_shelf_to,
    inspect_directory,
    plan_startup,
    start_fresh,
)
from .validation import build_book, build_shelf

__all__ = [
    "DataState",
    "StartupPlan",
    "StartupResult",
    "inspect_directory",
    "plan_startup",
    "start_fresh",
    "build_shelf",
    "build_book",
    "add_shelf_to",
]
