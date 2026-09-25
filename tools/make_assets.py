#!/usr/bin/env python3
"""Generate the image assets: the combo-box arrow and the application icon.

Qt's stylesheet box model cannot build a triangle out of borders the way CSS
can, so the dropdown arrow has to be an image.  Drawing it here - with Qt
itself, no image library - rather than committing a PNG keeps the colour in one
place and makes regeneration a one-liner when a theme changes.

Both a 1x and a 2x arrow are produced; Qt's stylesheet picks up the ``@2x`` file
automatically on a high DPI screen, which matters because the target is
everything from an 800x600 netbook to a 4K monitor.

    python tools/make_assets.py
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path
from typing import List, Sequence

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide2.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt  # noqa: E402
from PySide2.QtGui import (  # noqa: E402
    QColor,
    QGuiApplication,
    QImage,
    QPainter,
    QPolygonF,
)

from homelibrarymanager.config import resource_dir  # noqa: E402
from homelibrarymanager.ui.theme import (  # noqa: E402
    ARROW_HEIGHT,
    ARROW_WIDTH,
    BLUE_THEME,
)

#: Sizes Windows asks for: 16 in the title bar, 32/48 in Explorer, 256 for the
#: large-icon view and the installer-free ZIP thumbnail.
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


# --------------------------------------------------------------------------
# Arrow
# --------------------------------------------------------------------------


def draw_arrow(path: Path, scale: int, colour: str) -> None:
    width = ARROW_WIDTH * scale
    height = ARROW_HEIGHT * scale

    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(Qt.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(colour))
    painter.drawPolygon(
        QPolygonF(
            [QPointF(0.0, 0.0), QPointF(float(width), 0.0), QPointF(width / 2.0, float(height))]
        )
    )
    painter.end()

    if not image.save(str(path)):
        raise SystemExit("failed to write {0}".format(path))
    print("wrote {0}  ({1}x{2})".format(path.name, width, height))


# --------------------------------------------------------------------------
# Application icon
# --------------------------------------------------------------------------


def draw_icon(size: int) -> QImage:
    """Three book spines on a rounded blue tile."""
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)

    inset = size * 0.045
    painter.setBrush(QColor(BLUE_THEME.primary))
    painter.drawRoundedRect(
        QRectF(inset, inset, size - 2 * inset, size - 2 * inset),
        size * 0.22,
        size * 0.22,
    )

    spine_width = size * 0.135
    gap = size * 0.075
    total = spine_width * 3 + gap * 2
    left = (size - total) / 2.0
    baseline = size * 0.755
    # Uneven heights so it reads as books rather than a bar chart.
    heights = (0.42, 0.52, 0.34)

    painter.setBrush(QColor(BLUE_THEME.on_primary))
    x = left
    for fraction in heights:
        height = size * fraction
        painter.drawRoundedRect(
            QRectF(x, baseline - height, spine_width, height),
            size * 0.035,
            size * 0.035,
        )
        x += spine_width + gap

    painter.end()
    return image


def write_ico(path: Path, images: Sequence[QImage]) -> None:
    """Assemble an ICO container holding PNG-compressed images.

    Qt reads .ico but does not reliably write one, and PyInstaller needs a real
    .ico for the executable icon.  The format is small enough to build by hand:
    a 6-byte header, one 16-byte directory entry per size, then the payloads.
    """
    payloads: List[bytes] = []
    for image in images:
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        if not image.save(buffer, "PNG"):
            raise SystemExit("failed to encode icon image")
        payloads.append(bytes(buffer.data()))
        buffer.close()

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)

    entries = bytearray()
    for image, payload in zip(images, payloads):
        # 0 means 256 in this format.
        width = 0 if image.width() >= 256 else image.width()
        height = 0 if image.height() >= 256 else image.height()
        entries += struct.pack(
            "<BBBBHHII", width, height, 0, 0, 1, 32, len(payload), offset
        )
        offset += len(payload)

    with path.open("wb") as handle:
        handle.write(header)
        handle.write(bytes(entries))
        for payload in payloads:
            handle.write(payload)

    print(
        "wrote {0}  ({1} sizes, {2:,.0f} KB)".format(
            path.name, len(images), path.stat().st_size / 1024
        )
    )


def main() -> int:
    app = QGuiApplication(sys.argv[:1])  # noqa: F841 - must outlive the painting
    target = resource_dir()
    target.mkdir(parents=True, exist_ok=True)

    colour = BLUE_THEME.text_muted
    draw_arrow(target / "arrow-down.png", 1, colour)
    draw_arrow(target / "arrow-down@2x.png", 2, colour)

    write_ico(target / "app.ico", [draw_icon(size) for size in ICON_SIZES])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
