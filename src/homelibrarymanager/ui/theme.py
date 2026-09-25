"""Colour and metric definitions, and the stylesheet generated from them.

Every colour the interface uses is a field on :class:`Theme`, and the entire
stylesheet is produced from one instance - **no widget hard-codes a colour**.
That is what makes "custom themes later" a matter of registering another
``Theme`` rather than hunting through widget code:

    register_theme(Theme(name="dark", display_name="深色", primary="#2B3A4A", ...))
    apply_theme(app, get_theme("dark"))

The stylesheet is built with :class:`string.Template` rather than ``str.format``
because QSS is full of braces; an ``$name`` placeholder avoids having to double
every one of them.

Metrics are in device-independent pixels.  With Qt's high DPI scaling enabled
they are scaled by the window system, which is why the same numbers give a
sensible layout on an 800x600 netbook and on a 4K monitor.

Deliberately **no drop shadows** on the book cards: ``QGraphicsDropShadowEffect``
is per-widget and gets expensive once a shelf holds a few hundred books.  A 1px
border gives almost the same separation for free.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from string import Template
from typing import Dict, List, Optional

from ..config import resource_path

#: Logical size of the combo-box arrow.  ``tools/make_assets.py`` renders the
#: image and this stylesheet declares the same numbers, so they are defined once
#: here rather than in two places that could drift apart.
ARROW_WIDTH = 12
ARROW_HEIGHT = 7

#: Preferred UI fonts, most specific first.  Picked so Chinese text renders with
#: a proper CJK face on Windows 7 (Microsoft YaHei), macOS (PingFang) and Linux
#: rather than falling back to a bitmap font.
CJK_FONT_CANDIDATES = (
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "PingFang SC",
    "Hiragino Sans GB",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "WenQuanYi Micro Hei",
    "DejaVu Sans",
)


@dataclass(frozen=True)
class Theme:
    """A complete visual description of the interface."""

    name: str = "blue"
    display_name: str = "海蓝"

    # -- brand / header --------------------------------------------------
    primary: str = "#1E6FA8"
    primary_dark: str = "#14547F"
    primary_light: str = "#2E8BC0"
    accent: str = "#38B6E5"
    on_primary: str = "#FFFFFF"
    on_primary_muted: str = "#B8DAF0"

    # -- surfaces --------------------------------------------------------
    canvas: str = "#EAF3F9"
    sidebar: str = "#F2F8FC"
    surface: str = "#FFFFFF"
    surface_alt: str = "#F7FBFD"
    card: str = "#FFFFFF"
    card_hover: str = "#F2F9FD"
    card_selected: str = "#DCEBF7"

    # -- text ------------------------------------------------------------
    text: str = "#1F3B4D"
    text_muted: str = "#63849B"
    text_faint: str = "#9BB3C4"

    # -- lines and states ------------------------------------------------
    border: str = "#D6E6F1"
    border_strong: str = "#A9C9DE"
    selection: str = "#2E8BC0"
    on_selection: str = "#FFFFFF"
    focus: str = "#38B6E5"
    danger: str = "#C0504D"
    disabled: str = "#C3D4E0"
    scrollbar: str = "#BBD5E6"
    scrollbar_hover: str = "#93BAD2"

    # -- metrics ---------------------------------------------------------
    radius: int = 10
    radius_small: int = 6
    space: int = 12
    space_small: int = 8
    space_large: int = 20

    header_title_pt: int = 17
    header_subtitle_pt: int = 9
    section_title_pt: int = 13
    body_pt: int = 10
    small_pt: int = 9
    card_title_pt: int = 11

    sidebar_width: int = 196
    shelf_item_height: int = 52
    book_card_width: int = 262
    book_card_height: int = 86
    action_button: int = 46

    def stylesheet(self) -> str:
        """Return the QSS for this theme."""
        values = dict(asdict(self))
        values["header_gradient"] = (
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "stop:0 {0}, stop:1 {1})".format(self.primary, self.primary_dark)
        )
        values["arrow_down"] = resource_path("arrow-down.png")
        values["arrow_width"] = ARROW_WIDTH
        values["arrow_height"] = ARROW_HEIGHT
        return _STYLESHEET.safe_substitute(values)

    def colors(self) -> Dict[str, str]:
        """Just the colour fields, for widgets that paint by hand."""
        skip = {"name", "display_name"}
        return {
            key: value
            for key, value in asdict(self).items()
            if key not in skip and isinstance(value, str) and value.startswith("#")
        }


# --------------------------------------------------------------------------
# The built-in themes
# --------------------------------------------------------------------------

BLUE_THEME = Theme()


def light_theme() -> Theme:
    """A neutral, low-saturation variant - useful as a "print friendly" mode."""
    return Theme(
        name="paper",
        display_name="素纸",
        primary="#4A6572",
        primary_dark="#33474F",
        primary_light="#5C7A88",
        accent="#7FA8B8",
        canvas="#F4F6F7",
        sidebar="#FAFBFC",
        surface="#FFFFFF",
        surface_alt="#F7F9FA",
        card="#FFFFFF",
        card_hover="#F1F5F7",
        card_selected="#E2EAEE",
        text="#26333A",
        text_muted="#6B7F8A",
        text_faint="#A3B3BC",
        border="#DDE5E9",
        border_strong="#B8C6CE",
        selection="#5C7A88",
        scrollbar="#C6D2D8",
        scrollbar_hover="#A9B9C1",
    )


_REGISTRY: Dict[str, Theme] = {}


def register_theme(theme: Theme) -> Theme:
    """Add a theme to the registry so the UI can offer it in a menu."""
    _REGISTRY[theme.name] = theme
    return theme


def get_theme(name: Optional[str] = None) -> Theme:
    if not name:
        return BLUE_THEME
    return _REGISTRY.get(name, BLUE_THEME)


def available_themes() -> List[Theme]:
    return sorted(_REGISTRY.values(), key=lambda theme: theme.name)


register_theme(BLUE_THEME)
register_theme(light_theme())


# --------------------------------------------------------------------------
# Application-wide application of a theme
# --------------------------------------------------------------------------

_active: Theme = BLUE_THEME


def active_theme() -> Theme:
    return _active


def pick_ui_font(fallback: str = "") -> str:
    """First CJK-capable family actually installed, so Chinese never falls back
    to a bitmap font on Windows 7."""
    from PySide2.QtGui import QFontDatabase

    installed = set(QFontDatabase().families())
    for family in CJK_FONT_CANDIDATES:
        if family in installed:
            return family
    return fallback


def apply_theme(app, theme: Optional[Theme] = None) -> Theme:
    """Install ``theme`` on the application and remember it as the active one.

    ``Fusion`` is forced because the native Windows style ignores large parts of
    any stylesheet, which would make the interface look different on every
    platform - and because Fusion renders consistently under high DPI scaling.
    """
    global _active
    theme = theme or _active
    _active = theme

    app.setStyle("Fusion")
    font = app.font()
    family = pick_ui_font(font.family())
    if family:
        font.setFamily(family)
    font.setPointSize(theme.body_pt)
    app.setFont(font)
    app.setStyleSheet(theme.stylesheet())
    return theme


# --------------------------------------------------------------------------
# The stylesheet template
# --------------------------------------------------------------------------

_STYLESHEET = Template(
    """
QWidget {
    color: $text;
    font-size: ${body_pt}pt;
}

QMainWindow, #RootSurface {
    background: $canvas;
}

/* ---------------------------------------------------------------- header */

#HeaderBar {
    background: $header_gradient;
    border: none;
}

#HeaderTitle {
    color: $on_primary;
    font-size: ${header_title_pt}pt;
    font-weight: 600;
}

#HeaderSubtitle {
    color: $on_primary_muted;
    font-size: ${header_subtitle_pt}pt;
    letter-spacing: 1px;
}

#HeaderDivider {
    background: $primary_dark;
    max-height: 1px;
    border: none;
}

/* ---------------------------------------------------------------- search */

#SearchBox {
    background: $surface;
    border: 1px solid $primary_dark;
    border-radius: ${radius}px;
    padding: 7px 14px;
    font-size: ${body_pt}pt;
    color: $text;
    selection-background-color: $selection;
    selection-color: $on_selection;
}

#SearchBox:focus {
    border: 1px solid $accent;
}

#SearchBox[text=""] {
    color: $text;
}

/* ---------------------------------------------------------------- sidebar */

#Sidebar {
    background: $sidebar;
    border-right: 1px solid $border;
}

#SidebarTitle {
    color: $text_muted;
    font-size: ${small_pt}pt;
    font-weight: 600;
    letter-spacing: 2px;
    padding-left: 2px;
}

#ShelfList {
    background: transparent;
    border: none;
    outline: none;
}

#ShelfList::item {
    background: transparent;
    border: none;
}

QScrollArea, #BookScroll {
    background: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background: transparent;
}

#AddShelfButton {
    background: transparent;
    border: 1px dashed $border_strong;
    border-radius: ${radius}px;
    color: $primary_light;
    font-size: ${section_title_pt}pt;
    font-weight: 600;
}

#AddShelfButton:hover {
    background: $card_hover;
    border: 1px dashed $primary_light;
    color: $primary;
}

#AddShelfButton:pressed {
    background: $card_selected;
}

/* ---------------------------------------------------------------- content */

#BookPanel {
    background: $canvas;
    border: none;
}

#ShelfHeading {
    color: $text;
    font-size: ${section_title_pt}pt;
    font-weight: 600;
}

#ShelfSubheading {
    color: $text_muted;
    font-size: ${small_pt}pt;
}

#PlaceholderText {
    color: $text_faint;
    font-size: ${body_pt}pt;
}

/* ------------------------------------------------------------------ cards */

#BookCard {
    background: $card;
    border: 1px solid $border;
    border-radius: ${radius}px;
}

#BookCard:hover {
    background: $card_hover;
    border: 1px solid $border_strong;
}

#BookCard[selected="true"] {
    background: $card_selected;
    border: 1px solid $selection;
}

#BookCardTitle {
    color: $text;
    font-size: ${card_title_pt}pt;
    font-weight: 600;
}

#BookCardMeta {
    color: $text_muted;
    font-size: ${small_pt}pt;
}

#BookCardMetaStrong {
    color: $text_muted;
    font-size: ${small_pt}pt;
    font-weight: 600;
}

/* --------------------------------------------------------- action buttons */

#ActionButton {
    background: $primary;
    border: none;
    border-radius: ${radius}px;
    color: $on_primary;
    font-size: ${header_title_pt}pt;
    font-weight: 600;
}

#ActionButton:hover {
    background: $primary_light;
}

#ActionButton:pressed {
    background: $primary_dark;
}

#ActionButton:disabled {
    background: $disabled;
    color: $surface;
}

/* -------------------------------------------------------------- empty state */

#EmptyStateTitle {
    color: $text;
    font-size: ${header_title_pt}pt;
    font-weight: 600;
}

#EmptyStateHint {
    color: $text_muted;
    font-size: ${body_pt}pt;
}

#PrimaryButton {
    background: $primary;
    border: none;
    border-radius: ${radius}px;
    color: $on_primary;
    font-size: ${body_pt}pt;
    font-weight: 600;
    padding: 10px 26px;
}

#PrimaryButton:hover {
    background: $primary_light;
}

#PrimaryButton:pressed {
    background: $primary_dark;
}

/* -------------------------------------------------------------- scrollbars */

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: $scrollbar;
    border-radius: 5px;
    min-height: 32px;
}

QScrollBar::handle:vertical:hover {
    background: $scrollbar_hover;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0;
}

QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: $scrollbar;
    border-radius: 5px;
    min-width: 32px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
    width: 0;
}

/* ---------------------------------------------------------------- dialogs */

QDialog {
    background: $surface;
}

QLineEdit, QPlainTextEdit {
    background: $surface;
    border: 1px solid $border_strong;
    border-radius: ${radius_small}px;
    padding: 7px 10px;
    color: $text;
    selection-background-color: $selection;
    selection-color: $on_selection;
}

QLineEdit:focus, QPlainTextEdit:focus {
    border: 1px solid $focus;
}

QLineEdit:disabled, QPlainTextEdit:disabled {
    background: $surface_alt;
    color: $text_faint;
}

QLabel#FieldLabel {
    color: $text_muted;
    font-size: ${small_pt}pt;
    font-weight: 600;
}

QLabel#RequiredMark {
    color: $danger;
    font-size: ${small_pt}pt;
    font-weight: 600;
}

QLabel#ErrorText {
    color: $danger;
    font-size: ${small_pt}pt;
}

QLabel#DialogTitle {
    color: $text;
    font-size: ${header_title_pt}pt;
    font-weight: 600;
}

QLabel#DialogHint {
    color: $text_muted;
    font-size: ${small_pt}pt;
}

#SecondaryButton {
    background: transparent;
    border: 1px solid $border_strong;
    border-radius: ${radius}px;
    color: $primary;
    font-size: ${body_pt}pt;
    padding: 9px 22px;
}

#SecondaryButton:hover {
    background: $card_hover;
    border: 1px solid $primary_light;
}

#SecondaryButton:pressed {
    background: $card_selected;
}

/* Destructive actions sit on the far left of the button row, away from 保存,
   so a mis-click cannot both intend to save and end up deleting. */
#DangerButton {
    background: transparent;
    border: 1px solid $danger;
    border-radius: ${radius}px;
    color: $danger;
    font-size: ${body_pt}pt;
    padding: 9px 20px;
}

#DangerButton:hover {
    background: $danger;
    color: $surface;
}

#DangerButton:pressed {
    background: $danger;
    color: $surface;
}

QComboBox {
    background: $surface;
    border: 1px solid $border_strong;
    border-radius: ${radius_small}px;
    padding: 6px 10px;
    color: $text;
    min-height: 20px;
}

QComboBox:focus, QComboBox:on {
    border: 1px solid $focus;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 24px;
    border: none;
    background: transparent;
}

/* The arrow has to be an image: Qt's stylesheet box model cannot build a
   triangle from borders, and the border trick renders as a small square.
   A resource, generated by tools/make_assets.py, is the only reliable way. */
QComboBox::down-arrow {
    image: url($arrow_down);
    width: ${arrow_width}px;
    height: ${arrow_height}px;
    margin-right: 9px;
}

QComboBox QAbstractItemView {
    background: $surface;
    border: 1px solid $border_strong;
    selection-background-color: $selection;
    selection-color: $on_selection;
    outline: none;
    padding: 4px;
}

QRadioButton {
    color: $text;
    font-size: ${body_pt}pt;
    spacing: 8px;
}

QRadioButton::indicator {
    width: 14px;
    height: 14px;
}

QCheckBox {
    color: $text;
    font-size: ${body_pt}pt;
    spacing: 8px;
}

QLabel#BodyText {
    color: $text;
    font-size: ${body_pt}pt;
}

/* The ⋯ button opens this menu (编辑书架 / 编辑图书). */
QMenu {
    background: $surface;
    border: 1px solid $border_strong;
    border-radius: ${radius_small}px;
    padding: 5px;
}

QMenu::item {
    padding: 8px 22px 8px 16px;
    border-radius: ${radius_small}px;
    color: $text;
    font-size: ${body_pt}pt;
}

QMenu::item:selected {
    background: $selection;
    color: $on_selection;
}

QMenu::item:disabled {
    color: $text_faint;
}

QMenu::separator {
    height: 1px;
    background: $border;
    margin: 5px 8px;
}

QToolTip {
    background: $primary_dark;
    color: $on_primary;
    border: none;
    padding: 4px 8px;
}
"""
)
