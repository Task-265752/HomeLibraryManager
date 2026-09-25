"""Search across shelves and books.  Deliberately free of Qt so it can be tested.

The search box in the header promises to find "书架、书目、作者、ISBN", so this
walks every declared field of both record types.  It also walks the *unknown*
fields - someone who writes ``"借给": "爸爸"`` into the file by hand reasonably
expects to find that book by searching for 爸爸.

ISBNs get special treatment: people type them with hyphens and without, so both
the needle and the haystack are also compared with spaces and hyphens stripped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Sequence

from ..core.models import Book, Shelf

#: Characters ignored when comparing "compact" text (ISBNs, mostly).
_IGNORED = " -_\u3000\t"


def compact(text: str) -> str:
    return "".join(character for character in text.lower() if character not in _IGNORED)


def flatten(value: Any) -> str:
    """Turn any JSON value into searchable text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return " ".join(flatten(item) for item in value)
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            parts.append(str(key))
            parts.append(flatten(item))
        return " ".join(parts)
    return str(value)


def haystack(record) -> str:
    """Every searchable value on a record, lower-cased."""
    parts = [flatten(getattr(record, name, "")) for name in record.KNOWN_FIELDS]
    for key, value in getattr(record, "extra", {}).items():
        parts.append(str(key))
        parts.append(flatten(value))
    return " ".join(parts).lower()


def matches(record, needle: str, compact_needle: str) -> bool:
    text = haystack(record)
    if needle in text:
        return True
    return bool(compact_needle) and compact_needle in compact(text)


@dataclass
class SearchResults:
    query: str = ""
    shelves: List[Shelf] = field(default_factory=list)
    books: List[Book] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return bool(self.query.strip())

    @property
    def total(self) -> int:
        return len(self.shelves) + len(self.books)

    def describe(self) -> str:
        if not self.active:
            return ""
        if not self.total:
            return "没有找到匹配「{0}」的内容".format(self.query.strip())
        return "「{0}」：{1} 个书架、{2} 本书".format(
            self.query.strip(), len(self.shelves), len(self.books)
        )


def search(library, query: str) -> SearchResults:
    """Return everything matching ``query``; an empty query matches nothing.

    A query that matches a shelf also pulls in the books standing on it.  The
    search box advertises that it searches shelves, and the only reason to
    search for a shelf by its note is to see what is on it - returning the shelf
    but an empty book area would be a dead end.
    """
    needle = (query or "").strip().lower()
    if not needle:
        return SearchResults(query="")
    portable = compact(needle)

    shelves = [shelf for shelf in library.shelves if matches(shelf, needle, portable)]
    shelf_names = {shelf.name for shelf in shelves}
    books = [
        book
        for book in library.books
        if matches(book, needle, portable) or book.shelf in shelf_names
    ]
    return SearchResults(query=query, shelves=shelves, books=books)
