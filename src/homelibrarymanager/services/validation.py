"""Validation shared by the dialogs and the load path.

Keeping the rules here, rather than inside the dialog code, is what stops the
form and the file from disagreeing about what a valid record is.  Each function
raises :class:`ValueError` carrying a message that can be shown to the user
verbatim, so the dialogs contain no rules of their own.
"""

from __future__ import annotations

from typing import Iterable, Optional

from ..core.models import Book, Shelf


def build_shelf(
    name: str,
    sequence: str,
    note: str = "",
    existing_names: Iterable[str] = (),
) -> Shelf:
    """Validate the 添加/编辑书架 form.

    书架名称 and 书架序号 are required.  A duplicate name is rejected because
    books point at their shelf *by name*, so two shelves sharing one would make
    that pointer ambiguous.  书架序号 is free-form - digits, letters or Chinese
    are all fine, per the project owner.
    """
    name = (name or "").strip()
    sequence = (sequence or "").strip()
    note = (note or "").strip()

    if not name:
        raise ValueError("请填写书架名称。")
    if not sequence:
        raise ValueError("请填写书架序号。")
    if name in set(existing_names):
        raise ValueError("已存在名为“{0}”的书架，请换一个名称。".format(name))
    return Shelf(name=name, sequence=sequence, note=note)


def build_book(
    title: str,
    author: str,
    shelf: str,
    translator: str = "",
    isbn: str = "",
    published: str = "",
    note: str = "",
    shelf_names: Iterable[str] = (),
    existing: Optional[Book] = None,
) -> Book:
    """Validate the 添加/编辑图书 form.

    书名, 作者 and 书架 are required.  The shelf must be one of the existing
    ones: a book pointing at a shelf that does not exist would immediately show
    up under 未归档 the next time the file was read.

    When editing, ``existing`` supplies any fields the form does not cover -
    including ones the user typed into the file by hand - so an edit can never
    silently discard them.
    """
    title = (title or "").strip()
    author = (author or "").strip()
    shelf = (shelf or "").strip()
    known = set(shelf_names)

    if not title:
        raise ValueError("请填写书名。")
    if not author:
        raise ValueError("请填写作者。")
    if not shelf:
        raise ValueError("请选择一个书架。")
    if shelf not in known:
        raise ValueError("书架“{0}”不存在，请重新选择。".format(shelf))

    book = Book(
        title=title,
        author=author,
        shelf=shelf,
        translator=(translator or "").strip(),
        isbn=(isbn or "").strip(),
        published=(published or "").strip(),
        note=(note or "").strip(),
    )
    if existing is not None:
        book.extra = dict(existing.extra)
    return book
