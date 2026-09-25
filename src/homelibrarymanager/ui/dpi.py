"""High DPI configuration and screen-aware window sizing.

The project owner's requirement is a window that resizes from 800x600 up to a
4K monitor.  Two different mechanisms cover that:

* **Scaling** - handled here.  Qt has to be told to scale *before* the
  ``QApplication`` exists; setting these attributes afterwards silently does
  nothing, which is the classic "why is my app tiny on a 4K screen" bug.
* **Layout** - handled by the widgets themselves, which reflow rather than
  clipping, so the same window works at either extreme.
"""

from __future__ import annotations

from typing import Optional, Tuple

from PySide2.QtCore import Qt
from PySide2.QtGui import QGuiApplication
from PySide2.QtWidgets import QApplication


def configure_high_dpi() -> None:
    """Prepare Qt for scaled displays.  **Must run before QApplication exists.**"""
    # Fractional factors (125%, 150%) are common on laptops.  Without this Qt
    # rounds them, so a 125% display gets either 100% (cramped) or 200% (huge).
    try:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except AttributeError:
        # Older Qt builds lack the rounding policy; integer scaling still works.
        pass

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


def primary_screen_size() -> Optional[Tuple[int, int]]:
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return None
    size = screen.availableGeometry().size()
    return size.width(), size.height()


def initial_window_size(
    preferred_width: int,
    preferred_height: int,
    minimum_width: int,
    minimum_height: int,
    fill: float = 0.88,
) -> Tuple[int, int]:
    """A sensible first size: the preferred one, shrunk to fit the screen.

    On an 800x600 netbook the preferred size cannot be honoured, so the window
    opens near-fullscreen instead of hanging off the edges.  It never returns
    less than the declared minimum - below that the layout is expected to
    scroll, not to break.
    """
    screen = primary_screen_size()
    if screen is None:
        return max(preferred_width, minimum_width), max(preferred_height, minimum_height)
    screen_width, screen_height = screen
    width = min(preferred_width, int(screen_width * fill))
    height = min(preferred_height, int(screen_height * fill))
    return max(width, minimum_width), max(height, minimum_height)


def scale_for_screen() -> float:
    """Current device pixel ratio, for logging and diagnostics."""
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return 1.0
    try:
        return float(screen.devicePixelRatio())
    except AttributeError:
        return float(screen.logicalDotsPerInch()) / 96.0
