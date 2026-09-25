#!/usr/bin/env python3
"""Render a window or dialog to a PNG so the look can be reviewed.

    python tools/render_preview.py OUTPUT [VIEW] [WIDTH] [HEIGHT] [THEME]

VIEW is one of: main (default), add-book, edit-book, add-shelf, edit-shelf,
delete-shelf.  Width and height apply to the main window only; dialogs size
themselves to their content.

Why not the ``offscreen`` platform plugin?  On Windows it uses a fontconfig
database that ships no fonts, so every label renders blank - a preview with no
text is worse than useless.  This uses the *native* platform with
``WA_DontShowOnScreen`` instead: Qt lays out and paints exactly as it would on
screen, real system fonts included, but never puts anything up.

Set ``PREVIEW_PLATFORM=offscreen`` to force the headless plugin anyway.
"""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

platform = os.environ.get("PREVIEW_PLATFORM")
if platform:
    os.environ["QT_QPA_PLATFORM"] = platform

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide2.QtCore import Qt  # noqa: E402
from PySide2.QtWidgets import QApplication, QWidget  # noqa: E402

from homelibrarymanager.config import (  # noqa: E402
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
)
from homelibrarymanager.data.library import Library  # noqa: E402
from homelibrarymanager.ui.dialogs.book_dialog import BookDialog  # noqa: E402
from homelibrarymanager.ui.dialogs.confirm_dialog import ConfirmDialog  # noqa: E402
from homelibrarymanager.ui.dialogs.location_dialog import LocationDialog  # noqa: E402
from homelibrarymanager.ui.dialogs.shelf_delete_dialog import ShelfDeleteDialog  # noqa: E402
from homelibrarymanager.ui.dialogs.shelf_dialog import ShelfDialog  # noqa: E402
from homelibrarymanager.ui.dialogs.warning_dialog import WarningDialog  # noqa: E402
from homelibrarymanager.ui.dpi import configure_high_dpi, scale_for_screen  # noqa: E402
from homelibrarymanager.ui.main_window import MainWindow  # noqa: E402
from homelibrarymanager.ui.theme import apply_theme, get_theme  # noqa: E402

VIEWS = (
    "main",
    "all-books",
    "add-book",
    "edit-book",
    "add-shelf",
    "edit-shelf",
    "delete-shelf",
    "confirm-delete",
    "choose-folder",
    "warnings",
)


def build_view(view: str, theme, library: Library):
    shelves = library.sorted_shelves()
    names = [shelf.name for shelf in shelves]

    if view == "main":
        return MainWindow(library, settings=None, theme=theme)

    if view == "all-books":
        window = MainWindow(library, settings=None, theme=theme)
        window.shelf_panel.select_all_books()
        return window

    if view == "add-shelf":
        return ShelfDialog(theme, existing_names=names)

    if view == "edit-shelf":
        return ShelfDialog(theme, shelf=shelves[0], existing_names=names)

    if view == "add-book":
        return BookDialog(
            theme, shelf_names=names, default_shelf=names[0] if names else ""
        )

    if view == "edit-book":
        return BookDialog(theme, book=library.books[0], shelf_names=names)

    if view == "delete-shelf":
        shelf = shelves[0]
        others = [name for name in names if name != shelf.name]
        return ShelfDeleteDialog(
            theme, shelf, len(library.books_on_shelf(shelf.name)), other_shelves=others
        )

    if view == "confirm-delete":
        return ConfirmDialog(
            theme,
            "删除图书",
            "确定要删除《三体》吗？",
            "删除后无法撤销，书目文件里对应的那一行会被移除。",
        )

    if view == "choose-folder":
        return LocationDialog(theme, ROOT, "首次使用，请选择数据保存位置")

    if view == "warnings":
        return WarningDialog(
            theme,
            [
                "书目文件第 7 行：缺少必填项：作者",
                "有 1 本书指向了不存在的书架，已暂归“未归档”：这本书的书架不存在",
                "书架名称重复：客厅书架（书目按名称指向书架，重名会让指向变得不明确）",
                "书架文件：文件不是 UTF-8 编码，已按 gb18030 读取。建议用记事本“另存为”"
                "并选择 UTF-8，否则中文可能显示错乱。",
            ],
        )

    raise SystemExit("unknown view {0!r}; expected one of {1}".format(view, ", ".join(VIEWS)))


def demo_catalogue() -> Library:
    """Build the demo catalogue in a scratch folder.

    The repository root doubles as the data folder while running from source, so
    it holds whatever the developer last worked on - and nothing at all on a
    fresh clone, because the catalogue files are runtime output and are not
    committed.  Previewing must depend on neither, so the demo data is generated
    fresh every time.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    from make_sample_data import sample_books, sample_shelves  # noqa: E402

    scratch = Path(tempfile.mkdtemp(prefix="hlm-preview-"))
    atexit.register(shutil.rmtree, scratch, True)

    library = Library(scratch)
    library.shelves = sample_shelves()
    library.books = sample_books()
    library.save()
    return library


def main(argv) -> int:
    output = Path(argv[1]) if len(argv) > 1 else ROOT / "preview.png"
    view = argv[2] if len(argv) > 2 else "main"
    width = int(argv[3]) if len(argv) > 3 else DEFAULT_WINDOW_WIDTH
    height = int(argv[4]) if len(argv) > 4 else DEFAULT_WINDOW_HEIGHT
    theme_name = argv[5] if len(argv) > 5 else ""

    configure_high_dpi()
    app = QApplication(sys.argv[:1])
    theme = apply_theme(app, get_theme(theme_name or None))

    library = demo_catalogue()

    widget: QWidget = build_view(view, theme, library)
    widget.setAttribute(Qt.WA_DontShowOnScreen, True)
    if view in ("main", "all-books"):
        widget.resize(width, height)
    else:
        widget.adjustSize()
    widget.show()

    # The flow layout works out its height-for-width during layout, so give the
    # event loop a few passes before grabbing.
    for _ in range(6):
        app.processEvents()

    pixmap = widget.grab()
    output.parent.mkdir(parents=True, exist_ok=True)
    if not pixmap.save(str(output)):
        print("failed to write {0}".format(output), file=sys.stderr)
        return 1

    print(
        "rendered {0}\n  view={1}, pixel size {2}x{3}, scale {4:.2f}, theme={5}".format(
            output, view, pixmap.width(), pixmap.height(), scale_for_screen(), theme.name
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
