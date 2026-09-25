#!/usr/bin/env python3
"""Write a small demo catalogue into a folder, so the format can be inspected.

The files are produced through the real codec rather than by hand, which means
they carry the UTF-8 BOM and CRLF line endings that Windows 7 Notepad needs.
Writing them any other way would produce files that look fine in an editor on
Windows 11 and like mojibake on Windows 7.

Usage::

    python tools/make_sample_data.py [target-dir]

Defaults to the project root, which is the portable data folder while running
from source (next to the program, as chosen for the shipped build).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from homelibrarymanager.core.models import Book, Shelf  # noqa: E402
from homelibrarymanager.data.library import Library  # noqa: E402


def sample_shelves():
    return [
        Shelf(name="客厅书架", sequence="1", note="客厅东墙，靠窗"),
        Shelf(name="卧室床头柜", sequence="2", note="常读的放这里"),
        Shelf(name="书房铁架", sequence="10", note="工具书为主"),
    ]


def sample_books():
    return [
        Book(
            title="三体",
            author="刘慈欣",
            shelf="客厅书架",
            isbn="9787536692930",
            published="2008-01",
            note="第一版，封面略有磨损",
        ),
        Book(title="活着", author="余华", shelf="卧室床头柜", isbn="9787506365437", published="2012"),
        Book(title="围城", author="钱锺书", shelf="客厅书架", published="1991"),
        Book(
            title="百年孤独",
            author="加西亚·马尔克斯",
            shelf="书房铁架",
            translator="范晔",
            isbn="9787544253994",
            published="2011-06",
        ),
        # A hand-written style line with fields the program does not know.
        Book(
            title="手工加的例子",
            author="某人",
            shelf="客厅书架",
            extra={"借给": "爸爸", "购入年份": 2019},
        ),
        # Deliberately missing 作者, to demonstrate the validation message.
        Book(title="这本书故意没写作者", shelf="书房铁架"),
        # Deliberately pointing at a shelf that does not exist, to demonstrate
        # that nothing is lost when the two files disagree.
        Book(title="这本书的书架不存在", author="某人", shelf="阳台上那个架子"),
    ]


def main(argv):
    target = Path(argv[1]).expanduser().resolve() if len(argv) > 1 else ROOT
    library = Library(target)
    library.shelves = sample_shelves()
    library.books = sample_books()
    library.save()

    print("已生成示例数据：")
    for path in (library.shelves_path, library.books_path):
        raw = path.read_bytes()
        print(
            "  {0}\n    {1} 字节 | BOM={2} | CRLF={3}".format(
                path,
                len(raw),
                raw.startswith(b"\xef\xbb\xbf"),
                b"\r\n" in raw,
            )
        )

    reloaded = Library(target)
    report = reloaded.load()
    print(
        "回读校验：{0} 个书架，{1} 本书".format(len(reloaded.shelves), len(reloaded.books))
    )
    for name, count in reloaded.shelf_summary():
        print("    {0}：{1} 本".format(name, count))
    print(
        "    未上架：{0} 本".format(len(reloaded.unplaced_books()))
    )
    if report.has_problems:
        print("  发现的问题：")
        for message in report.all_messages():
            print("    - " + message)
        for warning in report.warnings:
            print("    - " + warning)
    else:
        print("  没有问题")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
