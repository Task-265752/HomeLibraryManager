"""Plain data objects for the catalogue: :class:`Shelf` and :class:`Book`.

The field lists follow the project owner's specification exactly:

===========  ==========================================================
书架          ``name`` 书架名称（必填）、``sequence`` 书架序号（必填）、
             ``note`` 介绍说明（选填）
书目          ``title`` 书名（必填）、``author`` 作者（必填）、
             ``shelf`` 书架、``translator`` 译者、``isbn`` ISBN书号、
             ``published`` 出版时间、``note`` 备注（均选填）
===========  ==========================================================

``shelf`` holds the shelf *name* rather than an opaque id, so the file stays
readable in Notepad.  That is why renaming a shelf has to touch both files -
the cost is paid in one place, ``Library.rename_shelf``.

``shelf`` is optional: a book that has not been placed yet simply carries no
shelf, and the UI shows it as 未上架 rather than nagging about a missing field.

Two behaviours matter more than the field list itself.

**Unknown fields survive a round trip.**  These files are edited in Notepad, so
a user may add a field this program has never heard of (``"借给": "爸爸"``).
Dropping it on the next save would be data loss, so anything unrecognised is
kept in ``extra`` and written back untouched.

**Missing required fields do not discard the record.**  A hand-written line
without a 作者 is reported to the user and kept in memory; refusing to load it
would throw away work the user just typed.

``published`` and ``sequence`` are stored as text on purpose.  "2008",
"2008-05", "2008年5月" and "A-01" are all things a person plausibly types, and
text accepts every one of them.  Ordering uses :func:`natural_key`, which sorts
"2" before "10" instead of lexicographically.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Mapping, Optional, Sequence, Tuple

# --------------------------------------------------------------------------
# Helpers.  None of these raise; bad input degrades instead.
# --------------------------------------------------------------------------


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        return str(value)
    return ""


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _split(record: Mapping[str, Any], known: Sequence[str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Separate recognised keys from anything else the user put in the file."""
    values: Dict[str, Any] = {}
    extra: Dict[str, Any] = {}
    for key, value in record.items():
        if key in known:
            values[key] = value
        else:
            extra[key] = value
    return values, extra


def _take_text(values: Mapping[str, Any], extra: Dict[str, Any], name: str) -> str:
    """Coerce to text.  A list/dict value cannot be flattened without lying, so
    it is parked in ``extra`` and written back verbatim instead of vanishing."""
    raw = values.get(name)
    if raw is None:
        return ""
    text = _as_text(raw)
    if text == "" and not isinstance(raw, str):
        extra[name] = raw
    return text


def _to_record(instance: Any, known_fields: Sequence[str], extra: Mapping[str, Any]) -> Dict[str, Any]:
    """Serialise in a stable, human-friendly order.

    Declared fields come first in the order the specification lists them, so
    every line looks the same and the eye can scan a column.  Fields the user
    added by hand trail at the end rather than being scattered into the front.

    The one subtlety is a field we recognised but could not parse (say
    ``"published": {"y": 2008}``).  Its raw value lives in ``extra``; it must be
    written back while the typed field is empty, and must give way once the
    typed field actually holds something.
    """
    record: Dict[str, Any] = {}
    for name in known_fields:
        value = getattr(instance, name)
        if not _is_empty(value):
            record[name] = value
    for key, value in extra.items():
        if key in known_fields and not _is_empty(getattr(instance, key)):
            continue  # the parsed value wins over a stale raw copy
        record[key] = value
    return record


def natural_key(text: str) -> List[Tuple[int, Any]]:
    """Sort key where ``2`` precedes ``10``.

    Mixed int/str tuples would raise in Python 3, hence the ``(0/1, value)``
    tag on every element.
    """
    parts = re.split(r"(\d+)", text or "")
    return [(1, int(part)) if part.isdigit() else (0, part.lower()) for part in parts if part != ""]


# --------------------------------------------------------------------------
# Shelf
# --------------------------------------------------------------------------


@dataclass
class Shelf:
    """书架：书架名称、书架序号、介绍说明."""

    name: str = ""
    sequence: str = ""
    note: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    KNOWN_FIELDS: ClassVar[Sequence[str]] = ("name", "sequence", "note")
    REQUIRED_FIELDS: ClassVar[Sequence[Tuple[str, str]]] = (
        ("name", "书架名称"),
        ("sequence", "书架序号"),
    )

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "Shelf":
        values, extra = _split(record, cls.KNOWN_FIELDS)
        return cls(
            name=_take_text(values, extra, "name"),
            sequence=_take_text(values, extra, "sequence"),
            note=_take_text(values, extra, "note"),
            extra=extra,
        )

    def to_record(self) -> Dict[str, Any]:
        return _to_record(self, self.KNOWN_FIELDS, self.extra)

    def missing_required(self) -> List[str]:
        """Human-readable names of the required fields that are blank."""
        return [
            label
            for attribute, label in self.REQUIRED_FIELDS
            if not str(getattr(self, attribute) or "").strip()
        ]

    @property
    def sort_key(self) -> List[Tuple[int, Any]]:
        return natural_key(self.sequence)

    @property
    def display_name(self) -> str:
        return self.name or "（未命名书架）"


# --------------------------------------------------------------------------
# Book
# --------------------------------------------------------------------------


@dataclass
class Book:
    """书目：书名、作者、书架、译者、ISBN书号、出版时间、备注."""

    title: str = ""
    author: str = ""
    shelf: str = ""
    translator: str = ""
    isbn: str = ""
    published: str = ""
    note: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    KNOWN_FIELDS: ClassVar[Sequence[str]] = (
        "title",
        "author",
        "shelf",
        "translator",
        "isbn",
        "published",
        "note",
    )
    REQUIRED_FIELDS: ClassVar[Sequence[Tuple[str, str]]] = (
        ("title", "书名"),
        ("author", "作者"),
    )

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "Book":
        values, extra = _split(record, cls.KNOWN_FIELDS)
        return cls(
            title=_take_text(values, extra, "title"),
            author=_take_text(values, extra, "author"),
            shelf=_take_text(values, extra, "shelf"),
            translator=_take_text(values, extra, "translator"),
            isbn=_take_text(values, extra, "isbn"),
            published=_take_text(values, extra, "published"),
            note=_take_text(values, extra, "note"),
            extra=extra,
        )

    def to_record(self) -> Dict[str, Any]:
        return _to_record(self, self.KNOWN_FIELDS, self.extra)

    def missing_required(self) -> List[str]:
        return [
            label
            for attribute, label in self.REQUIRED_FIELDS
            if not str(getattr(self, attribute) or "").strip()
        ]

    @property
    def sort_key(self) -> List[Tuple[int, Any]]:
        return natural_key(self.title)

    @property
    def published_sort_key(self) -> List[Tuple[int, Any]]:
        return natural_key(self.published)

    @property
    def display_title(self) -> str:
        return self.title or "（无书名）"
