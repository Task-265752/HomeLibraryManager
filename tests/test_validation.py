"""Tests for the form validation shared by the dialogs.

These rules decide what the four dialogs accept, so they are tested without
constructing a dialog: the same functions are called by the form and (for
loading) by the data layer, which is what keeps the two from disagreeing.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from homelibrarymanager.core.models import Book  # noqa: E402
from homelibrarymanager.services.validation import build_book, build_shelf  # noqa: E402

SHELVES = ["客厅书架", "卧室床头柜"]


class BuildBookTests(unittest.TestCase):
    def test_required_fields_are_reported_by_name(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            build_book("", "刘慈欣", "客厅书架", shelf_names=SHELVES)
        self.assertIn("书名", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            build_book("三体", "  ", "客厅书架", shelf_names=SHELVES)
        self.assertIn("作者", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            build_book("三体", "刘慈欣", "", shelf_names=SHELVES)
        self.assertIn("书架", str(ctx.exception))

    def test_shelf_must_already_exist(self) -> None:
        """A book pointing at a missing shelf would land under 未归档 on reload."""
        with self.assertRaises(ValueError) as ctx:
            build_book("三体", "刘慈欣", "阳台上那个架子", shelf_names=SHELVES)
        self.assertIn("不存在", str(ctx.exception))

    def test_happy_path_fills_every_field(self) -> None:
        book = build_book(
            "三体",
            "刘慈欣",
            "客厅书架",
            translator="某人",
            isbn="9787536692930",
            published="2008-01",
            note="第一版",
            shelf_names=SHELVES,
        )
        self.assertEqual(book.title, "三体")
        self.assertEqual(book.author, "刘慈欣")
        self.assertEqual(book.shelf, "客厅书架")
        self.assertEqual(book.translator, "某人")
        self.assertEqual(book.isbn, "9787536692930")
        self.assertEqual(book.published, "2008-01")
        self.assertEqual(book.note, "第一版")

    def test_optional_fields_default_to_empty(self) -> None:
        book = build_book("三体", "刘慈欣", "客厅书架", shelf_names=SHELVES)
        self.assertEqual(book.translator, "")
        self.assertEqual(book.isbn, "")
        self.assertEqual(book.published, "")
        self.assertEqual(book.note, "")

    def test_whitespace_is_trimmed(self) -> None:
        book = build_book("  三体  ", " 刘慈欣 ", " 客厅书架 ", shelf_names=SHELVES)
        self.assertEqual(book.title, "三体")
        self.assertEqual(book.author, "刘慈欣")
        self.assertEqual(book.shelf, "客厅书架")

    def test_editing_keeps_hand_written_fields(self) -> None:
        """A field typed into the file by hand must survive an edit in the UI."""
        original = Book(
            title="三体", author="刘慈欣", shelf="客厅书架", extra={"借给": "爸爸"}
        )
        updated = build_book(
            "三体（修订版）", "刘慈欣", "卧室床头柜", shelf_names=SHELVES, existing=original
        )
        self.assertEqual(updated.extra, {"借给": "爸爸"})
        self.assertEqual(updated.shelf, "卧室床头柜")

    def test_new_book_has_no_extra(self) -> None:
        book = build_book("三体", "刘慈欣", "客厅书架", shelf_names=SHELVES)
        self.assertEqual(book.extra, {})


class BuildShelfTests(unittest.TestCase):
    """build_shelf moved here from the startup module; these lock its contract."""

    def test_required_fields(self) -> None:
        with self.assertRaises(ValueError):
            build_shelf("", "1")
        with self.assertRaises(ValueError):
            build_shelf("客厅书架", "   ")

    def test_duplicate_name_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            build_shelf("客厅书架", "2", existing_names=["客厅书架"])
        self.assertIn("已存在", str(ctx.exception))

    def test_sequence_is_free_form(self) -> None:
        for sequence in ("1", "A-01", "客厅", "壹"):
            self.assertEqual(build_shelf("架子", sequence).sequence, sequence)

    def test_duplicate_sequence_allowed(self) -> None:
        build_shelf("二号架", "1", existing_names=["一号架"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
