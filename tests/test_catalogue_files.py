"""Tests for the hand-editable catalogue files.

Run with::

    .venv\\Scripts\\python.exe -m unittest discover -s tests -v

The tests deliberately focus on the ways a *human* can break these files -
a stray blank line, a missing comma, a forgotten 作者, an extra field this
program has never heard of - because those are the realistic failure modes for
a catalogue that is meant to be edited in Notepad.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from homelibrarymanager.config import (  # noqa: E402
    BOOKS_FILENAME,
    DATA_DIR_ENV,
    SHELVES_FILENAME,
    resolve_data_dir,
)
from homelibrarymanager.core.errors import DataFileError  # noqa: E402
from homelibrarymanager.core.models import Book, Shelf, natural_key  # noqa: E402
from homelibrarymanager.data.jsonl import HEADER_FORMAT_KEY, read_records, write_records  # noqa: E402
from homelibrarymanager.data.library import Library  # noqa: E402


class TempDirCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def path(self, name: str) -> Path:
        return self.dir / name

    def write_catalogue(self, shelves, books) -> None:
        """Drop hand-written lines straight into the two files."""
        for filename, records in ((SHELVES_FILENAME, shelves), (BOOKS_FILENAME, books)):
            text = "".join(
                json.dumps(record, ensure_ascii=False) + "\n" for record in records
            )
            (self.dir / filename).write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------
# Encoding: Windows 7 Notepad needs both a BOM and CRLF
# --------------------------------------------------------------------------


class EncodingTests(TempDirCase):
    def test_written_file_starts_with_utf8_bom(self) -> None:
        target = self.path("books.jsonl")
        write_records(target, [{"title": "三体"}])
        self.assertTrue(
            target.read_bytes().startswith(b"\xef\xbb\xbf"),
            "缺少 UTF-8 BOM，Windows 7 记事本会显示成乱码",
        )

    def test_written_file_uses_crlf_only(self) -> None:
        target = self.path("books.jsonl")
        write_records(target, [{"title": "三体"}, {"title": "活着"}])
        raw = target.read_bytes()
        self.assertIn(b"\r\n", raw, "缺少 CRLF，Windows 7 记事本会把整个文件显示成一行")
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), "存在裸 LF 换行")

    def test_chinese_is_not_escaped(self) -> None:
        target = self.path("books.jsonl")
        write_records(target, [{"title": "三体"}])
        self.assertIn("三体", target.read_text(encoding="utf-8-sig"))

    def test_reads_file_without_bom(self) -> None:
        target = self.path("books.jsonl")
        target.write_bytes('{"title":"三体"}\n'.encode("utf-8"))
        result = read_records(target)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.encoding_warning, "")

    def test_reads_file_saved_as_gbk_with_warning(self) -> None:
        """Notepad may re-save as ANSI; we recover instead of failing."""
        target = self.path("books.jsonl")
        target.write_bytes('{"title":"三体"}\n'.encode("gb18030"))
        result = read_records(target)
        self.assertEqual([r["title"] for r in result.records], ["三体"])
        self.assertIn("UTF-8", result.encoding_warning)

    def test_undecodable_file_raises_actionable_error(self) -> None:
        target = self.path("books.jsonl")
        target.write_bytes(b"\xff\xfe\x00\x01\x02\x03\xff\xff")
        with self.assertRaises(DataFileError) as ctx:
            read_records(target)
        self.assertIn("UTF-8", str(ctx.exception))


# --------------------------------------------------------------------------
# Robustness: one bad line must cost one record, never the whole catalogue
# --------------------------------------------------------------------------


class RobustnessTests(TempDirCase):
    def test_blank_lines_are_ignored(self) -> None:
        target = self.path("books.jsonl")
        target.write_text('{"title":"三体"}\n\n\n{"title":"活着"}\n', encoding="utf-8")
        result = read_records(target)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.issues, [])

    def test_broken_line_is_reported_and_neighbours_survive(self) -> None:
        target = self.path("books.jsonl")
        target.write_text(
            '{"title":"三体"}\n'
            '{"title":"活着",}\n'          # trailing comma
            '{"title":"围城"}\n',
            encoding="utf-8",
        )
        result = read_records(target)
        self.assertEqual([r["title"] for r in result.records], ["三体", "围城"])
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].line_number, 2)
        self.assertIn("第 2 行", result.issues[0].describe())

    def test_line_numbers_stay_in_step_with_records(self) -> None:
        target = self.path("books.jsonl")
        # line 1 record, line 2 broken, line 3 blank, lines 4-5 records
        target.write_text(
            '{"title":"A"}\n坏行\n\n{"title":"B"}\n{"title":"C"}\n', encoding="utf-8"
        )
        result = read_records(target)
        self.assertEqual(result.lines, [1, 4, 5])
        self.assertEqual(result.issues[0].line_number, 2)

    def test_non_object_line_is_reported(self) -> None:
        target = self.path("books.jsonl")
        target.write_text('[1, 2, 3]\n{"title":"三体"}\n', encoding="utf-8")
        result = read_records(target)
        self.assertEqual(len(result.records), 1)
        self.assertIn("JSON 对象", result.issues[0].message)

    def test_missing_file_yields_empty_result(self) -> None:
        result = read_records(self.path("nope.jsonl"))
        self.assertEqual(result.records, [])
        self.assertEqual(result.issues, [])


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------


class WriteTests(TempDirCase):
    def test_header_line_is_written_and_skipped_on_read(self) -> None:
        target = self.path("books.jsonl")
        write_records(target, [{"title": "三体"}])
        first = target.read_text(encoding="utf-8-sig").splitlines()[0]
        self.assertIn(HEADER_FORMAT_KEY, first)
        result = read_records(target)
        self.assertTrue(result.header_seen)
        self.assertEqual(len(result.records), 1)

    def test_previous_version_is_backed_up(self) -> None:
        target = self.path("books.jsonl")
        write_records(target, [{"title": "三体"}])
        backup = write_records(target, [{"title": "活着"}])
        self.assertIsNotNone(backup)
        self.assertIn("三体", backup.read_text(encoding="utf-8-sig"))
        self.assertIn("活着", target.read_text(encoding="utf-8-sig"))

    def test_no_temporary_files_left_behind(self) -> None:
        target = self.path("books.jsonl")
        write_records(target, [{"title": "三体"}])
        self.assertEqual([p.name for p in self.dir.iterdir() if p.suffix == ".tmp"], [])

    def test_roundtrip_preserves_order(self) -> None:
        target = self.path("books.jsonl")
        write_records(target, [{"title": "第{0}本".format(i)} for i in range(500)])
        result = read_records(target)
        self.assertEqual(len(result.records), 500)
        self.assertEqual(result.records[-1]["title"], "第499本")


# --------------------------------------------------------------------------
# Models: exactly the fields the project owner specified
# --------------------------------------------------------------------------


class ModelTests(unittest.TestCase):
    def test_shelf_has_only_the_specified_fields(self) -> None:
        self.assertEqual(Shelf.KNOWN_FIELDS, ("name", "sequence", "note"))

    def test_book_has_only_the_specified_fields(self) -> None:
        self.assertEqual(
            Book.KNOWN_FIELDS,
            ("title", "author", "shelf", "translator", "isbn", "published", "note"),
        )

    def test_unknown_fields_survive_roundtrip(self) -> None:
        book = Book.from_record({"title": "三体", "author": "刘慈欣", "借给": "爸爸"})
        self.assertEqual(book.extra["借给"], "爸爸")
        self.assertEqual(Book.from_record(book.to_record()).extra["借给"], "爸爸")

    def test_structured_value_is_preserved_not_flattened(self) -> None:
        book = Book.from_record({"title": "三体", "author": "刘", "shelf_pos": {"row": 2}})
        self.assertEqual(book.to_record()["shelf_pos"], {"row": 2})

    def test_declared_fields_come_first_and_hand_added_fields_last(self) -> None:
        """Lines should look alike, so the eye can scan a column."""
        book = Book.from_record({"借给": "爸爸", "title": "三体", "author": "刘慈欣"})
        self.assertEqual(list(book.to_record().keys()), ["title", "author", "借给"])

    def test_stale_raw_copy_gives_way_to_the_parsed_value(self) -> None:
        book = Book.from_record({"title": "三体", "published": {"y": 2008}})
        self.assertEqual(book.to_record()["published"], {"y": 2008})
        book.published = "2008"  # user fixes it through the UI
        self.assertEqual(book.to_record()["published"], "2008")

    def test_empty_fields_are_omitted_to_keep_lines_short(self) -> None:
        self.assertEqual(
            Book(title="三体", author="刘慈欣").to_record(),
            {"title": "三体", "author": "刘慈欣"},
        )

    def test_whitespace_is_trimmed(self) -> None:
        shelf = Shelf.from_record({"name": "  客厅书架 ", "sequence": " 1 "})
        self.assertEqual(shelf.name, "客厅书架")
        self.assertEqual(shelf.sequence, "1")

    def test_missing_required_fields_are_reported(self) -> None:
        self.assertEqual(Book(title="三体").missing_required(), ["作者"])
        self.assertEqual(Book(author="刘慈欣").missing_required(), ["书名"])
        self.assertEqual(Book().missing_required(), ["书名", "作者"])
        self.assertEqual(Shelf(name="客厅").missing_required(), ["书架序号"])
        self.assertEqual(Shelf(name="客厅", sequence="1").missing_required(), [])

    def test_natural_key_sorts_two_before_ten(self) -> None:
        self.assertLess(natural_key("2"), natural_key("10"))

    def test_published_accepts_free_form_dates(self) -> None:
        for text in ("2008", "2008-01", "2008年5月", "2008/05/01"):
            self.assertEqual(Book(published=text).to_record()["published"], text)


# --------------------------------------------------------------------------
# Library
# --------------------------------------------------------------------------


class LibraryTests(TempDirCase):
    def test_missing_files_are_not_an_error(self) -> None:
        library = Library(self.dir)
        report = library.load()
        self.assertEqual(library.books, [])
        self.assertEqual(library.shelves, [])
        self.assertTrue(report.books_file_missing)
        self.assertTrue(report.shelves_file_missing)
        self.assertFalse(report.has_problems)

    def test_ensure_files_exist_creates_both(self) -> None:
        library = Library(self.dir)
        library.ensure_files_exist()
        self.assertTrue(library.books_path.exists())
        self.assertTrue(library.shelves_path.exists())
        reloaded = Library(self.dir)
        self.assertEqual(reloaded.load().issue_count, 0)

    def test_records_missing_required_fields_are_kept_and_reported(self) -> None:
        self.write_catalogue(
            [{"name": "客厅书架", "sequence": "1"}, {"name": "缺序号的架子"}],
            [
                {"title": "三体", "author": "刘慈欣"},
                {"title": "没有作者的书"},
            ],
        )
        library = Library(self.dir)
        report = library.load()

        # nothing was thrown away
        self.assertEqual(len(library.shelves), 2)
        self.assertEqual(len(library.books), 2)

        self.assertEqual(report.problem_count, 2)
        messages = report.all_messages()
        self.assertIn("书架文件第 2 行：缺少必填项：书架序号", messages)
        self.assertIn("书目文件第 2 行：缺少必填项：作者", messages)
        self.assertIn("2 条缺少必填项", report.describe())

    def test_validation_line_numbers_skip_the_header(self) -> None:
        """Files written by the program start with a header line."""
        library = Library(self.dir)
        library.shelves = [Shelf(name="客厅书架", sequence="1")]
        library.books = [Book(title="三体", author="刘慈欣"), Book(title="缺作者")]
        library.save()

        reloaded = Library(self.dir)
        report = reloaded.load()
        self.assertEqual(len(report.books_problems), 1)
        # header is line 1, so the second book is on line 3
        self.assertEqual(report.books_problems[0].line_number, 3)

    def test_sorted_shelves_uses_natural_order(self) -> None:
        self.write_catalogue(
            [
                {"name": "十号架", "sequence": "10"},
                {"name": "二号架", "sequence": "2"},
                {"name": "一号架", "sequence": "1"},
            ],
            [],
        )
        library = Library(self.dir)
        library.load()
        self.assertEqual(
            [s.name for s in library.sorted_shelves()], ["一号架", "二号架", "十号架"]
        )

    def test_duplicate_shelf_names_and_sequences_are_reported(self) -> None:
        self.write_catalogue(
            [
                {"name": "客厅书架", "sequence": "1"},
                {"name": "客厅书架", "sequence": "1"},
                {"name": "卧室", "sequence": "2"},
            ],
            [],
        )
        library = Library(self.dir)
        report = library.load()
        self.assertEqual(report.duplicate_shelf_names, ["客厅书架"])
        self.assertEqual(report.duplicate_shelf_sequences, ["1"])
        self.assertIn("书架重名", report.describe())

    def test_save_then_load_keeps_hand_added_fields(self) -> None:
        self.write_catalogue(
            [{"name": "客厅书架", "sequence": "1", "购入年份": "2019"}],
            [{"title": "三体", "author": "刘慈欣", "借给": "爸爸"}],
        )
        library = Library(self.dir)
        library.load()
        library.save()

        reloaded = Library(self.dir)
        reloaded.load()
        self.assertEqual(reloaded.shelves[0].extra["购入年份"], "2019")
        self.assertEqual(reloaded.books[0].extra["借给"], "爸爸")

    def test_second_save_creates_a_backup(self) -> None:
        library = Library(self.dir)
        library.books = [Book(title="三体", author="刘慈欣")]
        library.save_books(backup=False)
        library.books.append(Book(title="活着", author="余华"))
        backup = library.save_books()
        self.assertIsNotNone(backup)
        self.assertTrue(backup.exists())

    def test_blanks_in_required_fields_count_as_missing(self) -> None:
        self.write_catalogue([], [{"title": "   ", "author": "刘慈欣"}])
        library = Library(self.dir)
        report = library.load()
        self.assertEqual(report.problem_count, 1)
        self.assertIn("书名", report.books_problems[0].message)


# --------------------------------------------------------------------------
# Which book sits on which shelf
# --------------------------------------------------------------------------


class ShelfAssociationTests(TempDirCase):
    def _library(self, shelves, books):
        self.write_catalogue(shelves, books)
        library = Library(self.dir)
        library.load()
        return library

    def test_book_roundtrips_its_shelf(self) -> None:
        library = self._library(
            [{"name": "客厅书架", "sequence": "1"}],
            [{"title": "三体", "author": "刘慈欣", "shelf": "客厅书架"}],
        )
        self.assertEqual(library.books[0].shelf, "客厅书架")
        library.save()
        reloaded = Library(self.dir)
        reloaded.load()
        self.assertEqual(reloaded.books[0].shelf, "客厅书架")
        self.assertEqual(reloaded.orphan_books(), [])

    def test_books_on_shelf_and_summary(self) -> None:
        library = self._library(
            [
                {"name": "十号架", "sequence": "10"},
                {"name": "一号架", "sequence": "1"},
            ],
            [
                {"title": "A", "author": "甲", "shelf": "一号架"},
                {"title": "B", "author": "乙", "shelf": "一号架"},
                {"title": "C", "author": "丙", "shelf": "十号架"},
            ],
        )
        self.assertEqual([b.title for b in library.books_on_shelf("一号架")], ["A", "B"])
        # summary follows 序号 order, so 一号架 (1) precedes 十号架 (10)
        self.assertEqual(library.shelf_summary(), [("一号架", 2), ("十号架", 1)])

    def test_orphans_are_shown_not_dropped(self) -> None:
        library = self._library(
            [{"name": "客厅书架", "sequence": "1"}],
            [
                {"title": "三体", "author": "刘慈欣", "shelf": "客厅书架"},
                {"title": "活着", "author": "余华", "shelf": "已经删掉的书架"},
                {"title": "围城", "author": "钱锺书"},
            ],
        )
        report = library.last_report
        self.assertEqual([b.title for b in library.orphan_books()], ["活着"])
        self.assertEqual([b.title for b in library.unplaced_books()], ["围城"])
        self.assertEqual(report.orphan_book_titles, ["活着"])
        self.assertIn("1 本书的书架不存在", report.describe())

        groups = library.group_by_shelf()
        self.assertEqual([b.title for b in groups["客厅书架"]], ["三体"])
        self.assertEqual([b.title for b in groups["未归档"]], ["活着"])
        self.assertEqual([b.title for b in groups["未上架"]], ["围城"])
        # every book accounted for, none lost in the grouping
        self.assertEqual(sum(len(v) for v in groups.values()), 3)

    def test_rename_shelf_updates_both_files(self) -> None:
        library = self._library(
            [{"name": "客厅书架", "sequence": "1"}, {"name": "卧室", "sequence": "2"}],
            [
                {"title": "三体", "author": "刘慈欣", "shelf": "客厅书架"},
                {"title": "活着", "author": "余华", "shelf": "客厅书架"},
                {"title": "围城", "author": "钱锺书", "shelf": "卧室"},
            ],
        )
        moved = library.rename_shelf("客厅书架", "书房铁架")
        self.assertEqual(moved, 2)
        library.save()

        reloaded = Library(self.dir)
        reloaded.load()
        self.assertEqual(reloaded.orphan_books(), [])
        self.assertEqual(len(reloaded.books_on_shelf("书房铁架")), 2)
        self.assertEqual(len(reloaded.books_on_shelf("卧室")), 1)

    def test_rename_rejects_blank_and_duplicate_names(self) -> None:
        library = self._library(
            [{"name": "A", "sequence": "1"}, {"name": "B", "sequence": "2"}], []
        )
        with self.assertRaises(ValueError):
            library.rename_shelf("A", "B")
        with self.assertRaises(ValueError):
            library.rename_shelf("A", "   ")
        with self.assertRaises(KeyError):
            library.rename_shelf("根本不存在", "C")

    def test_deleting_a_shelf_with_books_requires_a_decision(self) -> None:
        """书架 is required on a book, so its books cannot be left pointing at a
        shelf that no longer exists - the program would flag them as invalid the
        next time the file was read."""
        library = self._library(
            [{"name": "客厅书架", "sequence": "1"}],
            [{"title": "三体", "author": "刘慈欣", "shelf": "客厅书架"}],
        )
        with self.assertRaises(ValueError) as ctx:
            library.delete_shelf("客厅书架")
        self.assertIn("去向", str(ctx.exception))
        self.assertEqual(len(library.shelves), 1, "报错时不应该真的把书架删掉")
        self.assertEqual(len(library.books), 1)

    def test_delete_shelf_can_move_the_books_somewhere_else(self) -> None:
        library = self._library(
            [{"name": "客厅书架", "sequence": "1"}, {"name": "书房", "sequence": "2"}],
            [{"title": "三体", "author": "刘慈欣", "shelf": "客厅书架"}],
        )
        moved = library.delete_shelf("客厅书架", move_to="书房")
        self.assertEqual(moved, 1)
        self.assertEqual(library.shelf_names(), ["书房"])
        self.assertEqual(library.books[0].shelf, "书房")
        self.assertEqual(library.orphan_books(), [])

    def test_delete_shelf_can_delete_the_books_with_it(self) -> None:
        library = self._library(
            [{"name": "客厅书架", "sequence": "1"}],
            [{"title": "三体", "author": "刘慈欣", "shelf": "客厅书架"}],
        )
        removed = library.delete_shelf("客厅书架", delete_books=True)
        self.assertEqual(removed, 1)
        self.assertEqual(library.books, [])
        self.assertEqual(library.shelves, [])

    def test_deleting_an_empty_shelf_needs_no_decision(self) -> None:
        library = self._library([{"name": "空架子", "sequence": "1"}], [])
        self.assertEqual(library.delete_shelf("空架子"), 0)
        self.assertEqual(library.shelves, [])

    def test_delete_shelf_rejects_a_bad_destination(self) -> None:
        library = self._library(
            [{"name": "客厅书架", "sequence": "1"}],
            [{"title": "三体", "author": "刘慈欣", "shelf": "客厅书架"}],
        )
        with self.assertRaises(ValueError):
            library.delete_shelf("客厅书架", move_to="不存在的书架")
        with self.assertRaises(ValueError):
            library.delete_shelf("客厅书架", move_to="客厅书架")
        self.assertEqual(len(library.books), 1)


# --------------------------------------------------------------------------
# Portable data location
# --------------------------------------------------------------------------


class ConfigTests(TempDirCase):
    def test_explicit_directory_wins(self) -> None:
        location = resolve_data_dir(self.dir)
        self.assertEqual(location.directory, self.dir)
        self.assertFalse(location.portable)

    def test_environment_override(self) -> None:
        previous = os.environ.get(DATA_DIR_ENV)
        os.environ[DATA_DIR_ENV] = str(self.dir)
        try:
            location = resolve_data_dir()
        finally:
            if previous is None:
                os.environ.pop(DATA_DIR_ENV, None)
            else:
                os.environ[DATA_DIR_ENV] = previous
        self.assertEqual(location.directory, self.dir)

    def test_file_names_are_derived_from_directory(self) -> None:
        location = resolve_data_dir(self.dir)
        self.assertEqual(location.books_path, self.dir / BOOKS_FILENAME)
        self.assertEqual(location.shelves_path, self.dir / SHELVES_FILENAME)

    def test_writable_program_folder_is_used_as_is(self) -> None:
        with mock.patch(
            "homelibrarymanager.config.application_dir", return_value=self.dir
        ), mock.patch("homelibrarymanager.config.is_writable", return_value=True):
            location = resolve_data_dir()
        self.assertTrue(location.portable)
        self.assertEqual(location.fallback_reason, "")
        self.assertEqual(location.directory, self.dir)

    def test_read_only_program_folder_falls_back_instead_of_failing(self) -> None:
        """The 'unzipped into C:\\Program Files' case must still start.

        This is the main risk of the portable layout: the folder holding the
        program is not always writable.  The app has to keep working and tell
        the user where the data actually went.
        """
        fake_home = self.dir / "fakehome"
        (fake_home / "Documents").mkdir(parents=True)
        with mock.patch("homelibrarymanager.config.is_writable", return_value=False), mock.patch(
            "homelibrarymanager.config._documents_dir", return_value=fake_home / "Documents"
        ), mock.patch(
            "homelibrarymanager.config.application_dir", return_value=self.dir / "app"
        ):
            location = resolve_data_dir()

        self.assertFalse(location.portable)
        self.assertIn("不可写", location.fallback_reason)
        self.assertTrue(location.directory.is_dir(), "降级目录应当被真正创建出来")
        self.assertEqual(location.directory, fake_home / "Documents" / "HomeLibraryManager")


if __name__ == "__main__":
    unittest.main(verbosity=2)
