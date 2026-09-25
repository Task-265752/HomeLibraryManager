"""Tests for the startup flow and the INI settings store.

Run with::

    .venv\\Scripts\\python.exe -m unittest discover -s tests -v

The most important assertions here are the negative ones: a catalogue that is
merely *messy* must never be classified as unusable, because "unusable" is the
only state in which the UI offers to create new files - and saying yes to that
replaces the user's library.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from homelibrarymanager.config import (  # noqa: E402
    BOOKS_FILENAME,
    SHELVES_FILENAME,
    DataLocation,
)
from homelibrarymanager.data.library import Library  # noqa: E402
from homelibrarymanager.data.settings import GENERAL, KEY_DATA_DIR, Settings  # noqa: E402
from homelibrarymanager.services.startup import (  # noqa: E402
    DataState,
    add_shelf_to,
    build_shelf,
    inspect_directory,
    plan_startup,
    start_fresh,
)


class TempDirCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_catalogue(self, shelves, books) -> None:
        for filename, records in ((SHELVES_FILENAME, shelves), (BOOKS_FILENAME, books)):
            text = "".join(
                json.dumps(record, ensure_ascii=False) + "\n" for record in records
            )
            (self.dir / filename).write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------
# Startup classification
# --------------------------------------------------------------------------


class StartupInspectionTests(TempDirCase):
    def test_missing_files_are_fine_and_count_as_fresh(self) -> None:
        result = inspect_directory(self.dir)
        self.assertIs(result.state, DataState.READY)
        self.assertFalse(result.has_shelves, "没有书架时只应显示添加书架按钮")
        self.assertTrue(result.is_fresh)
        self.assertEqual(result.messages, [])

    def test_empty_shelf_file_means_shelf_less_screen(self) -> None:
        """The shelf file exists but holds no records - same screen."""
        self.write_catalogue([], [])
        result = inspect_directory(self.dir)
        self.assertIs(result.state, DataState.READY)
        self.assertFalse(result.has_shelves)

    def test_existing_shelves_go_straight_to_the_normal_screen(self) -> None:
        self.write_catalogue(
            [{"name": "客厅书架", "sequence": "1"}],
            [{"title": "三体", "author": "刘慈欣", "shelf": "客厅书架"}],
        )
        result = inspect_directory(self.dir)
        self.assertIs(result.state, DataState.READY)
        self.assertTrue(result.has_shelves)
        self.assertFalse(result.can_offer_new_files)

    def test_messy_catalogue_warns_but_is_not_unusable(self) -> None:
        """A typo must never produce an offer to replace the library."""
        self.write_catalogue(
            [{"name": "客厅书架", "sequence": "1"}],
            [
                {"title": "三体", "author": "刘慈欣", "shelf": "客厅书架"},
                {"title": "忘了写作者"},                       # missing required
                {"title": "指向不存在的架子", "author": "某人", "shelf": "没有这个架子"},
            ],
        )
        # plus a line that is not valid JSON at all
        with (self.dir / BOOKS_FILENAME).open("a", encoding="utf-8") as handle:
            handle.write("这一行不是 JSON\n")

        result = inspect_directory(self.dir)
        self.assertIs(result.state, DataState.WARNINGS)
        self.assertTrue(result.has_shelves, "仍然应该进入正常界面")
        self.assertFalse(result.can_offer_new_files, "不能因为一行写错就提出新建文件")
        self.assertGreaterEqual(len(result.messages), 3)
        self.assertTrue(any("缺少必填项" in m for m in result.messages))
        self.assertTrue(any("不是有效的 JSON" in m for m in result.messages))
        self.assertTrue(any("不存在的书架" in m for m in result.messages))

    def test_undecodable_file_is_the_only_unusable_case(self) -> None:
        (self.dir / SHELVES_FILENAME).write_bytes(b"\xff\xfe\x00\x01\x02\x03\xff\xff")
        result = inspect_directory(self.dir)
        self.assertIs(result.state, DataState.UNUSABLE)
        self.assertTrue(result.can_offer_new_files)
        self.assertTrue(result.fatal_error)
        self.assertIn("UTF-8", result.messages[0])

    def test_directory_is_created_when_missing(self) -> None:
        target = self.dir / "sub" / "catalogue"
        result = inspect_directory(target)
        self.assertTrue(target.is_dir())
        self.assertFalse(result.has_shelves)


class StartFreshTests(TempDirCase):
    def test_archives_instead_of_deleting(self) -> None:
        """The whole point: a mis-click must be recoverable."""
        self.write_catalogue(
            [{"name": "客厅书架", "sequence": "1"}],
            [{"title": "三体", "author": "刘慈欣", "shelf": "客厅书架"}],
        )
        result = start_fresh(self.dir)

        self.assertIs(result.state, DataState.READY)
        self.assertFalse(result.has_shelves)

        backups = sorted(p.name for p in self.dir.iterdir() if ".bak" in p.name)
        self.assertEqual(len(backups), 2, "两个原文件都应被备份保留")
        archived_books = [
            p for p in self.dir.iterdir() if p.name.startswith(BOOKS_FILENAME + ".")
        ][0]
        self.assertIn("三体", archived_books.read_text(encoding="utf-8"))
        self.assertTrue(any("备份" in m for m in result.messages))

    def test_fresh_catalogue_is_usable_immediately(self) -> None:
        result = start_fresh(self.dir)
        self.assertEqual(result.library.shelves, [])
        self.assertEqual(result.library.books, [])
        reloaded = inspect_directory(self.dir)
        self.assertIs(reloaded.state, DataState.READY)

    def test_works_on_an_empty_folder(self) -> None:
        result = start_fresh(self.dir)
        self.assertEqual(result.messages, [])
        self.assertTrue((self.dir / SHELVES_FILENAME).exists())


# --------------------------------------------------------------------------
# The 添加书架 dialog's rules
# --------------------------------------------------------------------------


class AddShelfTests(TempDirCase):
    def test_required_fields(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            build_shelf("", "1")
        self.assertIn("名称", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            build_shelf("客厅书架", "  ")
        self.assertIn("序号", str(ctx.exception))

    def test_whitespace_is_trimmed(self) -> None:
        shelf = build_shelf("  客厅书架 ", " 1 ", " 客厅东墙 ")
        self.assertEqual((shelf.name, shelf.sequence, shelf.note), ("客厅书架", "1", "客厅东墙"))

    def test_duplicate_name_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            build_shelf("客厅书架", "2", existing_names=["客厅书架"])
        self.assertIn("已存在", str(ctx.exception))

    def test_sequence_may_be_letters_or_chinese(self) -> None:
        for sequence in ("1", "A-01", "客厅", "壹"):
            self.assertEqual(build_shelf("架子", sequence).sequence, sequence)

    def test_duplicate_sequence_is_allowed(self) -> None:
        """The project owner chose free-form sequences, so duplicates are legal."""
        build_shelf("二号架", "1", existing_names=["一号架"])

    def test_add_shelf_writes_to_the_shelf_file(self) -> None:
        library = Library(self.dir)
        library.load()
        add_shelf_to(library, "客厅书架", "1", "客厅东墙")

        self.assertTrue(library.shelves_path.exists())
        reloaded = Library(self.dir)
        reloaded.load()
        self.assertEqual([s.name for s in reloaded.shelves], ["客厅书架"])
        self.assertEqual(reloaded.shelves[0].note, "客厅东墙")

    def test_add_first_shelf_then_normal_screen(self) -> None:
        """The exact sequence from the specification."""
        result = inspect_directory(self.dir)
        self.assertFalse(result.has_shelves)

        add_shelf_to(result.library, "客厅书架", "1")
        again = inspect_directory(self.dir)
        self.assertTrue(again.has_shelves)
        self.assertIs(again.state, DataState.READY)


# --------------------------------------------------------------------------
# When to show the folder chooser
# --------------------------------------------------------------------------


class PlanStartupTests(TempDirCase):
    """Rule from the project owner: ask only on first run or when files are gone."""

    def setUp(self) -> None:
        super().setUp()
        self.settings = Settings(self.dir / "settings.ini")
        self.default_dir = self.dir / "default"
        self.default_dir.mkdir()
        self.location = DataLocation(directory=self.default_dir, portable=True)

    def plan(self, explicit=None):
        # Stand in for "where is the portable default folder", but keep
        # honouring an explicit path the way the real function does - otherwise
        # inspect_directory() would load the wrong folder.
        def fake_resolve(explicit_directory=None):
            if explicit_directory is not None:
                return DataLocation(directory=Path(explicit_directory), portable=False)
            return self.location

        with mock.patch(
            "homelibrarymanager.services.startup.resolve_data_dir", side_effect=fake_resolve
        ):
            return plan_startup(self.settings, explicit)

    def test_first_run_asks_for_a_folder(self) -> None:
        plan = self.plan()
        self.assertTrue(plan.needs_location_prompt)
        self.assertIn("首次使用", plan.reason)
        self.assertEqual(plan.suggested_directory, self.default_dir)
        self.assertIsNone(plan.result)

    def test_default_folder_with_files_skips_the_prompt(self) -> None:
        """Files already beside the program: don't pester the user."""
        self.default_dir.joinpath(SHELVES_FILENAME).write_text("{}\n", encoding="utf-8")
        plan = self.plan()
        self.assertFalse(plan.needs_location_prompt)
        self.assertIsNotNone(plan.result)

    def test_remembered_folder_with_files_skips_the_prompt(self) -> None:
        chosen = self.dir / "chosen"
        chosen.mkdir()
        chosen.joinpath(SHELVES_FILENAME).write_text("{}\n", encoding="utf-8")
        self.settings.data_dir = str(chosen)

        plan = self.plan()
        self.assertFalse(plan.needs_location_prompt)
        self.assertEqual(plan.result.location.directory, chosen)

    def test_remembered_folder_that_lost_its_files_asks_again(self) -> None:
        chosen = self.dir / "chosen"
        chosen.mkdir()
        self.settings.data_dir = str(chosen)

        plan = self.plan()
        self.assertTrue(plan.needs_location_prompt)
        self.assertIn("没有找到", plan.reason)

    def test_remembered_folder_that_no_longer_exists_asks_again(self) -> None:
        self.settings.data_dir = str(self.dir / "gone")
        plan = self.plan()
        self.assertTrue(plan.needs_location_prompt)
        self.assertIn("不存在", plan.reason)

    def test_explicit_directory_wins_over_the_remembered_one(self) -> None:
        chosen = self.dir / "chosen"
        chosen.mkdir()
        chosen.joinpath(SHELVES_FILENAME).write_text("{}\n", encoding="utf-8")
        self.settings.data_dir = str(self.dir / "somewhere-else")

        plan = self.plan(explicit=chosen)
        self.assertFalse(plan.needs_location_prompt)
        self.assertEqual(plan.result.location.directory, chosen)


class PartialCatalogueTests(TempDirCase):
    def test_books_without_a_shelf_file_are_reported(self) -> None:
        """Every book losing its location is worth saying out loud."""
        (self.dir / BOOKS_FILENAME).write_text(
            '{"title":"三体","author":"刘慈欣"}\n', encoding="utf-8"
        )
        result = inspect_directory(self.dir)
        self.assertIs(result.state, DataState.WARNINGS)
        self.assertTrue(any("没有找到书架文件" in m for m in result.messages))
        self.assertEqual(len(result.library.books), 1, "已有的书目必须照常读进来")

    def test_shelves_without_a_book_file_is_not_a_warning(self) -> None:
        """'Added a shelf, no books yet' is the normal early state.

        Warning about it on every launch would be noise, and it is exactly the
        state the app creates when the user adds their first shelf.
        """
        (self.dir / SHELVES_FILENAME).write_text(
            '{"name":"客厅书架","sequence":"1"}\n', encoding="utf-8"
        )
        result = inspect_directory(self.dir)
        self.assertIs(result.state, DataState.READY)
        self.assertEqual(result.messages, [])

    def test_both_missing_is_a_first_run_not_a_warning(self) -> None:
        result = inspect_directory(self.dir)
        self.assertIs(result.state, DataState.READY)
        self.assertEqual(result.messages, [])


# --------------------------------------------------------------------------
# settings.ini
# --------------------------------------------------------------------------


class SettingsTests(TempDirCase):
    def test_roundtrip(self) -> None:
        settings = Settings(self.dir / "settings.ini")
        settings.data_dir = r"D:\Books"
        settings.geometry = "AAAA"
        settings.save()

        reloaded = Settings(self.dir / "settings.ini")
        reloaded.load()
        self.assertEqual(reloaded.data_dir, r"D:\Books")
        self.assertEqual(reloaded.geometry, "AAAA")

    def test_missing_file_gives_defaults(self) -> None:
        settings = Settings(self.dir / "nope.ini")
        settings.load()
        self.assertEqual(settings.data_dir, "")

    def test_corrupt_file_falls_back_to_defaults(self) -> None:
        """A broken settings file must not block startup."""
        path = self.dir / "settings.ini"
        path.write_bytes(b"\x00\x01\x02 not an ini \xff")
        settings = Settings(path)
        settings.load()
        self.assertEqual(settings.data_dir, "")

    def test_written_as_utf8_bom_with_crlf(self) -> None:
        path = self.dir / "settings.ini"
        settings = Settings(path)
        settings.set(GENERAL, KEY_DATA_DIR, r"D:\我的图书")
        settings.save()
        raw = path.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), "记事本需要 BOM")
        self.assertIn(b"\r\n", raw, "记事本需要 CRLF")
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))

    def test_save_leaves_no_temporary_files(self) -> None:
        settings = Settings(self.dir / "settings.ini")
        settings.save()
        self.assertEqual([p.name for p in self.dir.iterdir() if p.suffix == ".tmp"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
