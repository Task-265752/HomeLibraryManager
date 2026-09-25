"""End-to-end tests that drive MainWindow instead of poking at the data layer.

The dialogs are replaced with stubs so a whole user action - add a book, edit a
shelf, delete something - can run to completion without a person clicking.  That
is the only way to catch bugs that live in the *sequence* of calls: refresh the
panel, re-select the shelf, rebuild the cards, write the file.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide2.QtCore import QTimer  # noqa: E402
from PySide2.QtWidgets import QApplication, QDialog  # noqa: E402

from homelibrarymanager.core.models import Book, Shelf  # noqa: E402
from homelibrarymanager.data.library import Library  # noqa: E402
from homelibrarymanager.ui import main_window as mw  # noqa: E402
from homelibrarymanager.ui.main_window import MainWindow  # noqa: E402
from homelibrarymanager.ui.theme import BLUE_THEME  # noqa: E402
from homelibrarymanager.ui.widgets.shelf_panel import ALL_BOOKS  # noqa: E402


class StubDialog:
    """Stands in for a modal dialog so the flow can run without a user."""

    def __init__(self, result=None, accepted: bool = True, deleted: bool = False):
        self._result = result
        self._accepted = accepted
        self._deleted = deleted

    def exec_(self):
        return QDialog.Accepted if self._accepted else QDialog.Rejected

    @property
    def deleted(self) -> bool:
        return self._deleted

    def book(self):
        return self._result

    def shelf(self):
        return self._result


class WindowTestCase(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        # Close anything a test left open.  Widgets that outlive their test are
        # what made the timer-driven tests above interfere with each other.
        for widget in self.app.topLevelWidgets():
            widget.close()
            widget.deleteLater()
        self.app.processEvents()
        self._tmp.cleanup()

    # -- helpers ---------------------------------------------------------

    def make_window(self, shelves=("客厅书架", "卧室床头柜")) -> MainWindow:
        library = Library(self.dir)
        library.load()
        for index, name in enumerate(shelves, start=1):
            library.add_shelf(Shelf(name=name, sequence=str(index)))
        library.save()
        window = MainWindow(library, settings=None, theme=BLUE_THEME)
        return window

    def empty_window(self) -> MainWindow:
        """A brand-new library, so MainWindow starts on the empty-state screen."""
        library = Library(self.dir)
        library.load()
        library.ensure_files_exist()
        return MainWindow(library, settings=None, theme=BLUE_THEME)

    def add_book(self, window: MainWindow, book: Book) -> None:
        with mock.patch.object(mw, "BookDialog", return_value=StubDialog(book)):
            window.add_book()

    def add_shelf(self, window: MainWindow, shelf: Shelf) -> None:
        with mock.patch.object(mw, "ShelfDialog", return_value=StubDialog(shelf)):
            window.add_shelf()

    def reload(self) -> Library:
        library = Library(self.dir)
        library.load()
        return library

    def card_titles(self, window: MainWindow):
        return sorted(card.book.title for card in window.book_panel._cards)

    def _settle(self, rounds: int = 6) -> None:
        """Let the event loop run so pending layout and paint work happens."""
        for _ in range(rounds):
            self.app.processEvents()


class AddBookFlowTests(WindowTestCase):
    def test_the_first_book_shows_up_in_its_shelf(self) -> None:
        window = self.make_window()
        self.add_book(window, Book(title="三体", author="刘慈欣", shelf="客厅书架"))

        self.assertEqual(len(window.library.books), 1)
        self.assertEqual(window.book_panel.heading.text(), "客厅书架")
        self.assertEqual(self.card_titles(window), ["三体"])

    def test_the_first_book_is_written_to_the_file(self) -> None:
        window = self.make_window()
        self.add_book(window, Book(title="三体", author="刘慈欣", shelf="客厅书架"))

        reloaded = self.reload()
        self.assertEqual([book.title for book in reloaded.books], ["三体"])
        self.assertEqual(reloaded.books[0].shelf, "客厅书架")

    def test_adding_several_books_keeps_them_all(self) -> None:
        window = self.make_window()
        for title in ("三体", "活着", "围城"):
            self.add_book(window, Book(title=title, author="某人", shelf="客厅书架"))

        expected = sorted(["三体", "活着", "围城"])
        self.assertEqual(self.card_titles(window), expected)
        self.assertEqual(sorted(book.title for book in self.reload().books), expected)

    def test_book_added_to_another_shelf_moves_the_view_there(self) -> None:
        window = self.make_window()
        self.add_book(window, Book(title="三体", author="某人", shelf="客厅书架"))
        self.add_book(window, Book(title="活着", author="某人", shelf="卧室床头柜"))

        self.assertEqual(window.book_panel.heading.text(), "卧室床头柜")
        self.assertEqual(self.card_titles(window), ["活着"])

        window.shelf_panel.select("客厅书架")
        self.assertEqual(self.card_titles(window), ["三体"])

    def test_first_book_on_a_second_shelf(self) -> None:
        """The first book anywhere is fine; the *first on a given shelf* is the
        case that looked broken."""
        window = self.make_window()
        window.shelf_panel.select("卧室床头柜")
        self.add_book(window, Book(title="活着", author="余华", shelf="卧室床头柜"))

        self.assertEqual(self.card_titles(window), ["活着"])

    def test_adding_the_first_book_after_a_search(self) -> None:
        """A search leaves the panel showing results; adding a book must not be
        swallowed by the branch that deliberately ignores selection changes."""
        window = self.make_window()
        window.header.search.setText("三体")
        self.app.processEvents()

        self.add_book(window, Book(title="三体", author="刘慈欣", shelf="客厅书架"))
        self.assertEqual(self.card_titles(window), ["三体"])

    def test_added_while_all_books_is_open(self) -> None:
        window = self.make_window()
        window.shelf_panel.select_all_books()
        self.add_book(window, Book(title="三体", author="刘慈欣", shelf="客厅书架"))

        self.assertEqual(window.book_panel.heading.text(), "全部书目")
        self.assertEqual(self.card_titles(window), ["三体"])

    def test_repeated_adds_in_one_session(self) -> None:
        """Catches order-dependent state: rebuild the cards ten times over."""
        window = self.make_window()
        for index in range(10):
            self.add_book(
                window, Book(title="第{0}本".format(index), author="某人", shelf="客厅书架")
            )
            self.assertEqual(
                window.book_panel.card_count(),
                index + 1,
                "第 {0} 次添加后卡片数不对".format(index + 1),
            )


class LayoutTests(WindowTestCase):
    """A card can exist in the model and still be invisible on screen.

    The flow tests above only count cards.  These drive a real (offscreen) window
    through a layout pass and check the geometry, which is where a
    height-for-width layout can go wrong.
    """

    def _shown_window(self, width: int = 1000, height: int = 700) -> MainWindow:
        window = self.make_window()
        window.setAttribute(mw.Qt.WA_DontShowOnScreen, True)
        window.resize(width, height)
        window.show()
        for _ in range(5):
            self.app.processEvents()
        return window

    def test_the_first_card_lands_inside_the_canvas(self) -> None:
        window = self._shown_window()
        self.add_book(window, Book(title="三体", author="刘慈欣", shelf="客厅书架"))
        for _ in range(6):
            self.app.processEvents()

        panel = window.book_panel
        self.assertEqual(panel.card_count(), 1)
        self.assertEqual(panel.stack.currentIndex(), 0, "应当显示卡片页而不是空状态页")

        card = panel._cards[0]
        self.assertGreater(card.width(), 0)
        self.assertGreater(card.height(), 0)
        self.assertTrue(
            panel.canvas.rect().contains(card.geometry()),
            "卡片位置 {0} 不在画布 {1} 内".format(card.geometry(), panel.canvas.rect()),
        )

    def test_canvas_is_tall_enough_for_its_cards(self) -> None:
        """The classic flow-layout trap: the container keeps the height it was
        given on the first pass and later rows are clipped."""
        window = self._shown_window(1000, 620)
        for index in range(8):
            self.add_book(
                window, Book(title="第{0}本".format(index), author="某人", shelf="客厅书架")
            )
        for _ in range(8):
            self.app.processEvents()

        panel = window.book_panel
        bottom = max(
            card.geometry().bottom() for card in panel._cards
        )
        self.assertLessEqual(
            bottom,
            panel.canvas.height(),
            "有卡片被画到画布外面了：最下面一张到 {0}，画布高 {1}".format(
                bottom, panel.canvas.height()
            ),
        )

    def test_switching_away_and_back_leaves_no_ghost_in_the_layout(self) -> None:
        """Reproduces the reported symptom exactly.

        The screenshot showed the shelf heading reading "2 本" while only one
        card was drawn, with a blank space where the first card should be.  That
        means the card was in the model but the *layout* still held a leftover
        item in its slot - so the check has to be on the flow layout's item
        count and on visibility, not on ``_cards``.
        """
        window = self._shown_window()
        for title in ("111", "222"):
            self.add_book(window, Book(title=title, author="某人", shelf="客厅书架"))
        for title in ("333", "444"):
            self.add_book(window, Book(title=title, author="某人", shelf="卧室床头柜"))

        window.shelf_panel.select("卧室床头柜")
        self._settle()
        window.shelf_panel.select("客厅书架")
        self._settle()

        panel = window.book_panel
        self.assertEqual(panel.card_count(), 2, "模型里应当是两张卡片")
        self.assertEqual(
            panel.flow.count(),
            2,
            "流式布局里残留了 {0} 个旧项，会占着位置不画东西".format(panel.flow.count()),
        )

        for card in panel._cards:
            self.assertTrue(card.isVisible(), "卡片 {0} 不可见".format(card.book.title))
            self.assertGreater(card.width(), 0, "卡片 {0} 宽度为 0".format(card.book.title))

    def test_every_card_has_a_real_position_after_switching(self) -> None:
        window = self._shown_window()
        for title in ("111", "222"):
            self.add_book(window, Book(title=title, author="某人", shelf="客厅书架"))
        window.shelf_panel.select("客厅书架")
        self._settle()

        panel = window.book_panel
        placed = [(card.book.title, card.geometry().x()) for card in panel._cards]
        for title, x in placed:
            self.assertGreaterEqual(x, 0, "卡片 {0} 的横坐标是 {1}".format(title, x))
        # Two cards in one row must not sit on top of each other.
        self.assertEqual(
            len({x for _, x in placed}), len(placed), "卡片重叠了：{0}".format(placed)
        )

    def test_switching_shelves_redraws_the_cards(self) -> None:
        window = self._shown_window()
        self.add_book(window, Book(title="三体", author="某人", shelf="客厅书架"))
        self.add_book(window, Book(title="活着", author="某人", shelf="卧室床头柜"))
        for _ in range(6):
            self.app.processEvents()

        window.shelf_panel.select("客厅书架")
        for _ in range(6):
            self.app.processEvents()
        self.assertEqual(self.card_titles(window), ["三体"])
        self.assertEqual(window.book_panel.stack.currentIndex(), 0)

        window.shelf_panel.select("卧室床头柜")
        for _ in range(6):
            self.app.processEvents()
        self.assertEqual(self.card_titles(window), ["活着"])
        self.assertEqual(window.book_panel.stack.currentIndex(), 0)


class FirstRunFlowTests(WindowTestCase):
    """The path a real user takes on day one.

    ``make_window`` above builds the shelves directly on the Library, which
    skips the empty-state screen entirely.  These tests walk the real sequence:
    no shelves -> EmptyState -> add a shelf -> add the first book.
    """

    def empty_window(self) -> MainWindow:
        library = Library(self.dir)
        library.load()
        library.ensure_files_exist()
        return MainWindow(library, settings=None, theme=BLUE_THEME)

    def test_empty_state_then_first_shelf_then_first_book(self) -> None:
        window = self.empty_window()
        self.assertEqual(window.body.currentIndex(), 0, "没有书架时应显示空状态页")

        self.add_shelf(window, Shelf(name="客厅书架", sequence="1"))
        self.assertEqual(window.body.currentIndex(), 1, "加完书架应切到两栏界面")
        self.assertEqual(window.shelf_panel.selection(), "客厅书架")

        self.add_book(window, Book(title="三体", author="刘慈欣", shelf="客厅书架"))
        self.assertEqual(window.book_panel.heading.text(), "客厅书架")
        self.assertEqual(self.card_titles(window), ["三体"])
        self.assertEqual(window.book_panel.stack.currentIndex(), 0, "应显示卡片页")

        reloaded = self.reload()
        self.assertEqual([book.title for book in reloaded.books], ["三体"])

    def test_second_and_third_book_after_the_first(self) -> None:
        window = self.empty_window()
        self.add_shelf(window, Shelf(name="客厅书架", sequence="1"))
        for index, title in enumerate(("三体", "活着", "围城"), start=1):
            self.add_book(window, Book(title=title, author="某人", shelf="客厅书架"))
            self.assertEqual(
                window.book_panel.card_count(),
                index,
                "加第 {0} 本后卡片数为 {1}".format(index, window.book_panel.card_count()),
            )
        self.assertEqual(
            sorted(book.title for book in self.reload().books), ["三体", "围城", "活着"]
        )

    def test_first_book_on_the_second_shelf_of_a_fresh_library(self) -> None:
        window = self.empty_window()
        self.add_shelf(window, Shelf(name="客厅书架", sequence="1"))
        self.add_shelf(window, Shelf(name="卧室床头柜", sequence="2"))
        self.assertEqual(window.shelf_panel.selection(), "卧室床头柜")

        self.add_book(window, Book(title="活着", author="余华", shelf="卧室床头柜"))
        self.assertEqual(self.card_titles(window), ["活着"])

        window.shelf_panel.select("客厅书架")
        self.assertEqual(self.card_titles(window), [])
        window.shelf_panel.select("卧室床头柜")
        self.assertEqual(self.card_titles(window), ["活着"])


class RandomisedFlowTests(WindowTestCase):
    """A small fuzzer over the operations a user actually performs.

    Every step re-checks one invariant: whatever the book panel is showing
    matches what the library holds for the current selection.  A bug of the
    "sometimes the book just added is missing" kind is usually an ordering
    problem that only appears in some interleaving, so a fixed sequence of
    hand-written tests can easily walk straight past it.
    """

    SHELVES = ["客厅书架", "卧室床头柜"]

    def invariants(self, window: MainWindow) -> None:
        panel = window.book_panel
        shown = sorted(card.book.title for card in panel._cards)

        if window.header.query().strip():
            return  # the panel is deliberately showing search results

        if window.shelf_panel.is_all_books():
            expected = sorted(book.title for book in window.library.books)
        else:
            name = window.shelf_panel.selection()
            expected = sorted(book.title for book in window.library.books_on_shelf(name))

        self.assertEqual(
            shown,
            expected,
            "第 {0} 步后界面与数据不一致：界面显示 {1}，数据里是 {2}".format(
                self._step, shown, expected
            ),
        )
        if shown:
            self.assertEqual(panel.stack.currentIndex(), 0, "有书时应显示卡片页")

    def test_many_interleaved_operations(self) -> None:
        import random

        window = self.empty_window()
        window.setAttribute(mw.Qt.WA_DontShowOnScreen, True)
        window.resize(1000, 640)
        window.show()
        for index, name in enumerate(self.SHELVES, start=1):
            self.add_shelf(window, Shelf(name=name, sequence=str(index)))

        counter = 0
        for seed in (11, 20260911, 4242):
            random.seed(seed)
            for step in range(50):
                self._step = "seed {0} / #{1}".format(seed, step)
                action = random.choice(
                    ["add", "select", "select_all", "search", "clear", "edit"]
                )

                if action == "add":
                    counter += 1
                    self.add_book(
                        window,
                        Book(
                            title="书{0}".format(counter),
                            author="某人",
                            shelf=random.choice(self.SHELVES),
                        ),
                    )
                elif action == "select":
                    window.shelf_panel.select(random.choice(self.SHELVES))
                elif action == "select_all":
                    window.shelf_panel.select_all_books()
                elif action == "search":
                    window.header.search.setText(
                        "书{0}".format(random.randint(1, max(1, counter)))
                    )
                elif action == "clear":
                    window.header.clear()
                elif action == "edit" and window.library.books:
                    book = random.choice(window.library.books)
                    updated = Book(title=book.title, author="改过", shelf=book.shelf)
                    with mock.patch.object(
                        mw, "BookDialog", return_value=StubDialog(updated)
                    ):
                        window.edit_book(book)

                for _ in range(3):
                    self.app.processEvents()
                self.invariants(window)


class RealDialogFlowTests(WindowTestCase):
    """Drives the *actual* dialogs, including their nested event loop.

    Every test above replaces the dialog with a stub.  That skips the one thing
    a stub cannot reproduce: QDialog.exec_() runs a second event loop, and that
    is where deferred deletes and pending layout requests get processed.  If a
    bug depends on that, only a real dialog will show it.
    """

    @contextmanager
    def _drive(self, dialog_type, fill):
        """Fill the dialog that ``action`` is about to open.

        The patch is applied to the class for the duration of the call and then
        removed, and it fills *that instance* rather than searching
        ``topLevelWidgets()``.  Searching for "a dialog of this type" finds
        leftovers from earlier tests and fills the wrong one, which leaves the
        real dialog waiting forever.
        """
        original = dialog_type.__dict__.get("exec_") or dialog_type.exec_

        def patched(dialog_self):
            # Queued so it fires inside the dialog's own event loop, which is
            # the thing a stubbed dialog cannot reproduce.
            QTimer.singleShot(0, lambda: fill(dialog_self))
            return original(dialog_self)

        dialog_type.exec_ = patched
        try:
            yield
        finally:
            dialog_type.exec_ = original
            self._settle()

    def _ready_window(self) -> MainWindow:
        window = self.empty_window()
        window.setAttribute(mw.Qt.WA_DontShowOnScreen, True)
        window.resize(1000, 700)
        window.show()
        self._settle()
        return window

    def _settle(self, rounds: int = 6) -> None:
        for _ in range(rounds):
            self.app.processEvents()

    def _add_shelf_for_real(self, window: MainWindow, name: str, sequence: str) -> None:
        def fill(dialog):
            dialog.name_edit.setText(name)
            dialog.sequence_edit.setText(sequence)
            dialog.save_button.click()

        with self._drive(mw.ShelfDialog, fill):
            window.add_shelf()

    def _add_book_for_real(self, window: MainWindow, title: str, author: str) -> None:
        def fill(dialog):
            dialog.title_edit.setText(title)
            dialog.author_edit.setText(author)
            dialog.save_button.click()

        with self._drive(mw.BookDialog, fill):
            window.add_book()

    def test_first_book_through_the_real_dialog(self) -> None:
        window = self._ready_window()
        self._add_shelf_for_real(window, "客厅书架", "1")
        self._add_book_for_real(window, "三体", "刘慈欣")

        self.assertEqual(len(window.library.books), 1)
        self.assertEqual(self.card_titles(window), ["三体"])
        self.assertEqual(
            window.book_panel.stack.currentIndex(), 0, "应当切回卡片页而不是停在空状态页"
        )
        self.assertTrue(window.book_panel._cards[0].isVisible(), "卡片必须真的可见")

    def test_three_books_through_the_real_dialog(self) -> None:
        window = self._ready_window()
        self._add_shelf_for_real(window, "客厅书架", "1")
        for index, title in enumerate(("三体", "活着", "围城"), start=1):
            self._add_book_for_real(window, title, "某人")
            self.assertEqual(
                window.book_panel.card_count(),
                index,
                "加第 {0} 本后界面显示 {1} 张卡片".format(
                    index, window.book_panel.card_count()
                ),
            )

    def test_first_book_after_a_real_search(self) -> None:
        """The search branch deliberately ignores selection changes, so adding
        a book while a query is showing is the riskiest ordering."""
        window = self._ready_window()
        self._add_shelf_for_real(window, "客厅书架", "1")
        window.header.search.setText("不存在的东西")
        self._settle()

        self._add_book_for_real(window, "三体", "刘慈欣")
        self.assertEqual(self.card_titles(window), ["三体"])
        self.assertEqual(window.header.query(), "")


class ShelfCountTests(WindowTestCase):
    def test_the_count_beside_a_shelf_matches_its_books(self) -> None:
        window = self.make_window()
        self.add_book(window, Book(title="三体", author="某人", shelf="客厅书架"))

        counts = {}
        for row in range(window.shelf_panel.list.count()):
            item = window.shelf_panel.list.item(row)
            counts[item.data(0)] = item.data(257)  # DisplayRole, COUNT_ROLE

        self.assertEqual(counts["客厅书架"], 1)
        self.assertEqual(counts["全部书目"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
