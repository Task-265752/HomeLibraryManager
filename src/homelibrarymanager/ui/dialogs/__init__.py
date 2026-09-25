"""Modal dialogs.

Every form derives from :class:`FormDialog`, so they share one layout, one
required-field marker and one button row by construction rather than by
imitation.
"""

from __future__ import annotations

from .base_dialog import FormDialog
from .book_dialog import BookDialog
from .confirm_dialog import ConfirmDialog
from .location_dialog import LocationDialog
from .shelf_delete_dialog import ShelfDeleteDialog
from .shelf_dialog import ShelfDialog
from .warning_dialog import WarningDialog

__all__ = [
    "FormDialog",
    "ConfirmDialog",
    "ShelfDialog",
    "BookDialog",
    "ShelfDeleteDialog",
    "LocationDialog",
    "WarningDialog",
]
