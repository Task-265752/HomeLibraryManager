"""HomeLibraryManager - a small, dependency-light family library manager.

The package is split into four layers so that each can be changed without
disturbing the others:

    core   - plain data objects and errors, no I/O, no Qt
    data   - persistence (the hand-editable catalogue files)
    ui     - Qt widgets (added later)
    app    - wiring / entry point

Nothing in ``core`` or ``data`` imports Qt, which keeps the heavy GUI toolkit
out of the way during tests and makes the storage layer reusable from a
command line if that is ever wanted.
"""

from __future__ import annotations

from .config import APP_VERSION as __version__

__all__ = ["__version__"]
