"""Smoke tests for the four catalogue dialogs.

These drive real Qt widgets on the ``offscreen`` platform, which lays out and
paints exactly like the real one, so no display is needed.

They exist because of a bug that shipped once: 编辑图书 was built without ever
calling ``enable_delete()``, so the dialog quietly had no way to delete a book.
No amount of data-layer testing could have caught that - the only way to notice
is to ask the dialog what it is actually showing.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

# Must be set before PySide2 is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide2.QtWidgets import QApplication  # noqa: E402

from homelibrarymanager.core.models import Book, Shelf  # noqa: E402
from homelibrarymanager.data.library import Library  # noqa: E402
from homelibrarymanager.ui.dialogs.book_dialog import (  # noqa: E402
    SHELF_PLACEHOLDER,
    BookDialog,
)
from homelibrarymanager.ui.dialogs.confirm_dialog import ConfirmDialog  # noqa: E402
from homelibrarymanager.ui.dialogs.shelf_delete_dialog import (  # noqa: E402
    ShelfDeleteDialog,
)
from homelibrarymanager.ui.dialogs.shelf_dialog import ShelfDialog  # noqa: E402
from homelibrarymanager.ui.theme import BLUE_THEME  # noqa: E402
from homelibrarymanager.ui.widgets.dots_button import DotsButton  # noqa: E402

SHELVES = ["客厅书架", "卧室床头柜"]


class QtTestCase(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


def would_show(dialog, widget) -> bool:
    """True when the widget would appear once the dialog was shown.

    ``isVisible()`` is False for everything until the dialog is shown, so it
    cannot be used here; ``isVisibleTo`` answers the question we actually mean.
    """
    return widget.isVisibleTo(dialog)


class DeleteButtonTests(QtTestCase):
    """The regression that motivated this file."""

    def test_edit_book_offers_delete(self) -> None:
        dialog = BookDialog(
            BLUE_THEME,
            book=Book(title="三体", author="刘慈欣", shelf=SHELVES[0]),
            shelf_names=SHELVES,
        )
        self.assertTrue(
            would_show(dialog, dialog.delete_button), "编辑图书必须能删除图书"
        )

    def test_add_book_does_not_offer_delete(self) -> None:
        dialog = BookDialog(BLUE_THEME, shelf_names=SHELVES, default_shelf=SHELVES[0])
        self.assertFalse(would_show(dialog, dialog.delete_button))

    def test_edit_shelf_offers_delete(self) -> None:
        dialog = ShelfDialog(
            BLUE_THEME,
            shelf=Shelf(name="客厅书架", sequence="1"),
            existing_names=SHELVES,
        )
        self.assertTrue(would_show(dialog, dialog.delete_button))

    def test_add_shelf_does_not_offer_delete(self) -> None:
        dialog = ShelfDialog(BLUE_THEME, existing_names=SHELVES)
        self.assertFalse(would_show(dialog, dialog.delete_button))

    def test_shelf_delete_is_confirmed_first(self) -> None:
        dialog = ShelfDialog(
            BLUE_THEME,
            shelf=Shelf(name="客厅书架", sequence="1"),
            existing_names=SHELVES,
        )
        self.assertFalse(dialog.deleted)

        with mock.patch.object(ConfirmDialog, "ask", return_value=True) as ask:
            dialog.delete_button.click()

        ask.assert_called_once()
        self.assertTrue(dialog.deleted)

    def test_declining_the_confirmation_keeps_the_shelf(self) -> None:
        dialog = ShelfDialog(
            BLUE_THEME,
            shelf=Shelf(name="客厅书架", sequence="1"),
            existing_names=SHELVES,
        )
        with mock.patch.object(ConfirmDialog, "ask", return_value=False):
            dialog.delete_button.click()

        self.assertFalse(dialog.deleted, "取消确认就绝不能删除")
        self.assertEqual(dialog.result(), 0, "取消确认后对话框应当还开着")

    def test_book_delete_asks_before_destroying_anything(self) -> None:
        dialog = BookDialog(
            BLUE_THEME,
            book=Book(title="三体", author="刘慈欣", shelf=SHELVES[0]),
            shelf_names=SHELVES,
        )
        with mock.patch.object(ConfirmDialog, "ask", return_value=True) as ask:
            dialog.delete_button.click()

        ask.assert_called_once()
        self.assertTrue(
            any("三体" in str(argument) for argument in ask.call_args[0]),
            "确认框里应当写明删的是哪本书",
        )
        self.assertTrue(dialog.deleted)
        self.assertIsNone(dialog.book())

    def test_declining_keeps_the_book_and_its_edits(self) -> None:
        dialog = BookDialog(
            BLUE_THEME,
            book=Book(title="三体", author="刘慈欣", shelf=SHELVES[0]),
            shelf_names=SHELVES,
        )
        dialog.title_edit.setText("三体（修订版）")
        with mock.patch.object(ConfirmDialog, "ask", return_value=False):
            dialog.delete_button.click()

        self.assertFalse(dialog.deleted)
        self.assertEqual(dialog.title_edit.text(), "三体（修订版）", "改动应当还在")

    def test_a_shelf_with_books_is_not_confirmed_twice(self) -> None:
        """ShelfDeleteDialog asks once, in MainWindow; a prompt here as well
        would make the user answer the same question twice."""
        dialog = ShelfDialog(
            BLUE_THEME,
            shelf=Shelf(name="客厅书架", sequence="1"),
            existing_names=SHELVES,
            book_count=3,
        )
        with mock.patch.object(ConfirmDialog, "ask", return_value=True) as ask:
            dialog.delete_button.click()

        ask.assert_not_called()
        self.assertTrue(dialog.deleted)


class ValidationTests(QtTestCase):
    def test_add_book_refuses_incomplete_input(self) -> None:
        dialog = BookDialog(BLUE_THEME, shelf_names=SHELVES, default_shelf=SHELVES[0])

        dialog.save_button.click()
        self.assertIsNone(dialog.book())
        self.assertFalse(dialog.error.isHidden())
        self.assertIn("书名", dialog.error.text())

        dialog.title_edit.setText("三体")
        dialog.save_button.click()
        self.assertIn("作者", dialog.error.text())

        dialog.author_edit.setText("刘慈欣")
        dialog.save_button.click()
        self.assertIsNotNone(dialog.book())

    def test_add_shelf_refuses_incomplete_input(self) -> None:
        dialog = ShelfDialog(BLUE_THEME, existing_names=SHELVES)

        dialog.save_button.click()
        self.assertIsNone(dialog.shelf())
        self.assertIn("名称", dialog.error.text())

        dialog.name_edit.setText("客厅书架")
        dialog.save_button.click()
        self.assertIn("序号", dialog.error.text())

    def test_duplicate_shelf_name_is_rejected(self) -> None:
        dialog = ShelfDialog(BLUE_THEME, existing_names=SHELVES)
        dialog.name_edit.setText("客厅书架")
        dialog.sequence_edit.setText("9")
        dialog.save_button.click()
        self.assertIsNone(dialog.shelf())
        self.assertIn("已存在", dialog.error.text())

    def test_editing_a_shelf_may_keep_its_own_name(self) -> None:
        dialog = ShelfDialog(
            BLUE_THEME,
            shelf=Shelf(name="客厅书架", sequence="1"),
            existing_names=SHELVES,
        )
        dialog.sequence_edit.setText("42")
        dialog.save_button.click()
        self.assertIsNotNone(dialog.shelf(), "改自己的序号不该被当成重名")
        self.assertEqual(dialog.shelf().sequence, "42")


class BookDialogDefaultsTests(QtTestCase):
    def test_shelf_defaults_to_the_open_one(self) -> None:
        dialog = BookDialog(BLUE_THEME, shelf_names=SHELVES, default_shelf=SHELVES[1])
        self.assertEqual(dialog.shelf_combo.currentText(), SHELVES[1])

    def test_without_an_open_shelf_the_user_must_choose(self) -> None:
        """The 全部书目 view has no open shelf, so the combo starts unset."""
        dialog = BookDialog(BLUE_THEME, shelf_names=SHELVES, default_shelf="")
        self.assertEqual(dialog.shelf_combo.currentText(), SHELF_PLACEHOLDER)

        dialog.title_edit.setText("三体")
        dialog.author_edit.setText("刘慈欣")
        dialog.save_button.click()
        self.assertIsNone(dialog.book(), "没选书架不能保存")
        self.assertIn("请选择", dialog.error.text())

        dialog.shelf_combo.setCurrentText(SHELVES[0])
        dialog.save_button.click()
        self.assertIsNotNone(dialog.book())

    def test_editing_keeps_the_books_own_shelf(self) -> None:
        dialog = BookDialog(
            BLUE_THEME,
            book=Book(title="三体", author="刘慈欣", shelf=SHELVES[1]),
            shelf_names=SHELVES,
            default_shelf=SHELVES[0],
        )
        self.assertEqual(dialog.shelf_combo.currentText(), SHELVES[1])

    def test_a_shelf_that_no_longer_exists_is_not_silently_replaced(self) -> None:
        """Regression: the combo used to keep index 0 when the shelf could not
        be found, so saving quietly moved the book to whichever shelf happened
        to be first."""
        dialog = BookDialog(
            BLUE_THEME,
            book=Book(title="三体", author="刘慈欣", shelf="已经被删掉的书架"),
            shelf_names=SHELVES,
        )
        self.assertEqual(dialog.shelf_combo.currentText(), SHELF_PLACEHOLDER)

        dialog.save_button.click()
        self.assertIsNone(dialog.book(), "不该悄悄把书挪到别的书架")
        self.assertIn("请选择", dialog.error.text())

    def test_a_default_that_does_not_match_is_not_silently_replaced(self) -> None:
        dialog = BookDialog(BLUE_THEME, shelf_names=SHELVES, default_shelf="不存在的架子")
        self.assertEqual(dialog.shelf_combo.currentText(), SHELF_PLACEHOLDER)

    def test_the_picker_uses_the_same_order_as_the_sidebar(self) -> None:
        """Otherwise "the second shelf" means two different things."""
        import tempfile

        with tempfile.TemporaryDirectory() as scratch:
            library = Library(Path(scratch))
            library.load()
            for name, sequence in (("十号架", "10"), ("一号架", "1"), ("二号架", "2")):
                library.add_shelf(Shelf(name=name, sequence=sequence))

            dialog = BookDialog(
                BLUE_THEME,
                shelf_names=library.sorted_shelf_names(),
                default_shelf="一号架",
            )

        listed = [
            dialog.shelf_combo.itemText(index)
            for index in range(1, dialog.shelf_combo.count())
        ]
        self.assertEqual(listed, ["一号架", "二号架", "十号架"])
        self.assertEqual(dialog.shelf_combo.currentText(), "一号架")

    def test_fields_are_populated_when_editing(self) -> None:
        book = Book(
            title="三体",
            author="刘慈欣",
            shelf=SHELVES[0],
            translator="某人",
            isbn="9787536692930",
            published="2008-01",
            note="第一版",
        )
        dialog = BookDialog(BLUE_THEME, book=book, shelf_names=SHELVES)
        self.assertEqual(dialog.title_edit.text(), "三体")
        self.assertEqual(dialog.author_edit.text(), "刘慈欣")
        self.assertEqual(dialog.translator_edit.text(), "某人")
        self.assertEqual(dialog.isbn_edit.text(), "9787536692930")
        self.assertEqual(dialog.published_edit.text(), "2008-01")
        self.assertEqual(dialog.note_edit.toPlainText(), "第一版")


class ShelfDeleteDialogTests(QtTestCase):
    def test_offers_moving_the_books_by_default(self) -> None:
        dialog = ShelfDeleteDialog(
            BLUE_THEME, Shelf(name="客厅书架", sequence="1"), 3, other_shelves=["卧室"]
        )
        self.assertTrue(dialog.move_radio.isChecked())
        self.assertEqual(dialog.move_to(), "卧室")
        self.assertFalse(dialog.delete_books())

    def test_deleting_the_books_is_reported(self) -> None:
        dialog = ShelfDeleteDialog(
            BLUE_THEME, Shelf(name="客厅书架", sequence="1"), 3, other_shelves=["卧室"]
        )
        dialog.delete_radio.setChecked(True)
        dialog.save_button.click()
        self.assertEqual(dialog.move_to(), "")
        self.assertTrue(dialog.delete_books())

    def test_with_no_other_shelf_only_deleting_is_possible(self) -> None:
        dialog = ShelfDeleteDialog(
            BLUE_THEME, Shelf(name="客厅书架", sequence="1"), 3, other_shelves=[]
        )
        self.assertFalse(dialog.move_radio.isEnabled())
        self.assertTrue(dialog.delete_radio.isChecked())


class ConfirmDialogTests(QtTestCase):
    def test_cancel_is_the_default_button(self) -> None:
        """Enter must not delete.

        FormDialog makes 保存 the default button, which is right for a form and
        wrong for a destructive prompt - so this one deliberately inverts it.
        """
        dialog = ConfirmDialog(BLUE_THEME, "删除图书", "确定要删除《三体》吗？")
        self.assertTrue(dialog.cancel_button.isDefault())
        self.assertFalse(dialog.save_button.isDefault())

    def test_confirm_button_wears_the_danger_style(self) -> None:
        dialog = ConfirmDialog(BLUE_THEME, "删除图书", "确定吗？")
        self.assertEqual(dialog.save_button.objectName(), "DangerButton")
        self.assertFalse(would_show(dialog, dialog.delete_button), "不该有两个删除按钮")


class DotsButtonTests(QtTestCase):
    def test_dots_are_painted_not_typed(self) -> None:
        button = DotsButton(BLUE_THEME.on_primary, BLUE_THEME.surface)
        button.resize(46, 46)
        self.assertEqual(button.text(), "", "三个点应当是画出来的，不是打字的")
        self.assertFalse(button.grab().isNull())


if __name__ == "__main__":
    unittest.main(verbosity=2)
