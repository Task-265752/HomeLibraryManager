"""Tests for the header search box's matching rules.

The search box promises "书架、书目、作者、ISBN", so the cases below cover each of
those, plus the two that are easy to get wrong: an ISBN typed with hyphens, and
a field somebody added by hand in Notepad.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from homelibrarymanager.config import BOOKS_FILENAME, SHELVES_FILENAME  # noqa: E402
from homelibrarymanager.core.models import Book, Shelf  # noqa: E402
from homelibrarymanager.data.library import Library  # noqa: E402
from homelibrarymanager.services.search import compact, search  # noqa: E402


class SearchTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        shelves = [
            {"name": "客厅书架", "sequence": "1", "note": "靠窗"},
            {"name": "卧室床头柜", "sequence": "2"},
        ]
        books = [
            {
                "title": "三体",
                "author": "刘慈欣",
                "shelf": "客厅书架",
                "isbn": "9787536692930",
                "published": "2008-01",
            },
            {
                "title": "百年孤独",
                "author": "加西亚·马尔克斯",
                "translator": "范晔",
                "shelf": "卧室床头柜",
                "isbn": "9787544253994",
            },
            {
                "title": "手工加的例子",
                "author": "某人",
                "shelf": "客厅书架",
                "借给": "爸爸",
            },
        ]
        for filename, records in ((SHELVES_FILENAME, shelves), (BOOKS_FILENAME, books)):
            (self.dir / filename).write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
                encoding="utf-8",
            )
        self.library = Library(self.dir)
        self.library.load()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def titles(self, query: str):
        return sorted(book.title for book in search(self.library, query).books)


class SearchTests(SearchTestCase):
    def test_empty_query_matches_nothing(self) -> None:
        results = search(self.library, "   ")
        self.assertFalse(results.active)
        self.assertEqual(results.total, 0)
        self.assertEqual(results.describe(), "")

    def test_by_title(self) -> None:
        self.assertEqual(self.titles("三体"), ["三体"])

    def test_by_author(self) -> None:
        self.assertEqual(self.titles("刘慈欣"), ["三体"])

    def test_by_translator(self) -> None:
        self.assertEqual(self.titles("范晔"), ["百年孤独"])

    def test_by_isbn_plain(self) -> None:
        self.assertEqual(self.titles("9787536692930"), ["三体"])

    def test_by_isbn_with_hyphens(self) -> None:
        """People type ISBNs with hyphens; the digits alone must still match."""
        self.assertEqual(self.titles("978-7-5366-9293-0"), ["三体"])

    def test_by_isbn_prefix(self) -> None:
        self.assertEqual(self.titles("9787536"), ["三体"])

    def test_by_shelf_name_finds_the_books_on_it(self) -> None:
        self.assertEqual(self.titles("客厅书架"), ["三体", "手工加的例子"])

    def test_by_shelf_note(self) -> None:
        self.assertEqual(self.titles("靠窗"), ["三体", "手工加的例子"])

    def test_by_hand_added_field(self) -> None:
        """Someone who writes "借给": "爸爸" in Notepad expects to find it."""
        self.assertEqual(self.titles("爸爸"), ["手工加的例子"])

    def test_is_case_insensitive(self) -> None:
        self.library.books[0].isbn = "ISBN-ABC"
        self.assertEqual(self.titles("isbn-abc"), ["三体"])

    def test_shelves_are_matched_too(self) -> None:
        results = search(self.library, "卧室")
        self.assertEqual([s.name for s in results.shelves], ["卧室床头柜"])
        self.assertEqual([b.title for b in results.books], ["百年孤独"])

    def test_no_match_reports_clearly(self) -> None:
        results = search(self.library, "这本书不存在")
        self.assertEqual(results.total, 0)
        self.assertIn("没有找到", results.describe())

    def test_describe_counts_both_kinds(self) -> None:
        results = search(self.library, "客厅")
        self.assertIn("1 个书架", results.describe())
        self.assertIn("2 本书", results.describe())

    def test_whitespace_in_query_is_ignored(self) -> None:
        self.assertEqual(self.titles("  三体  "), ["三体"])

    def test_compact_strips_separators(self) -> None:
        self.assertEqual(compact("978-7 5366_9293"), "978753669293")


if __name__ == "__main__":
    unittest.main(verbosity=2)
