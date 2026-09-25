"""A label that shortens its text with an ellipsis instead of overflowing.

Book titles and author names are arbitrary length, and the cards are a fixed
size so the grid stays tidy.  Qt leaves the truncation to the caller, hence this
small helper: it keeps the full text around for the tooltip.
"""

from __future__ import annotations

from PySide2.QtCore import Qt
from PySide2.QtGui import QFontMetrics
from PySide2.QtWidgets import QLabel


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent=None, mode: Qt.TextElideMode = Qt.ElideRight):
        super().__init__(parent)
        self._full_text = ""
        self._mode = mode
        self.setText(text or "")

    def setText(self, text: str) -> None:  # noqa: N802 - Qt naming
        self._full_text = text or ""
        self._refresh()

    def fullText(self) -> str:  # noqa: N802
        return self._full_text

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        width = max(0, self.width())
        if width <= 0:
            # Not laid out yet; show the full text and let resizeEvent fix it.
            super().setText(self._full_text)
            return
        metrics = QFontMetrics(self.font())
        super().setText(metrics.elidedText(self._full_text, self._mode, width))
