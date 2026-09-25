"""Domain objects and errors.  No I/O and no Qt live in this package."""

from __future__ import annotations

from .errors import (
    HomeLibraryManagerError,
    DataFileError,
    ParseIssue,
    ValidationProblem,
)
from .models import Book, Shelf, natural_key

__all__ = [
    "Book",
    "Shelf",
    "natural_key",
    "HomeLibraryManagerError",
    "DataFileError",
    "ParseIssue",
    "ValidationProblem",
]
