#!/usr/bin/env python3
"""Build the portable Windows ZIP.

    .venv\\Scripts\\python.exe tools\\build_windows.py

Five steps, and each one can stop the build:

1. regenerate the image assets (arrow + application icon);
2. run the Windows 7 compatibility check over the PyInstaller bootloader, the
   Python runtime and the Qt DLLs - shipping a release that will not start on
   the target machines is not worth doing;
3. run PyInstaller from ``packaging/HomeLibraryManager.spec``;
4. **run the built executable with ``--self-test``** - a bundle can build
   perfectly and still be missing a Qt plugin or a data file, and that is silent
   at build time;
5. zip the folder.

The result is a ZIP the user extracts anywhere and double-clicks.  Nothing is
installed, nothing is written outside the folder, and no admin rights are
needed.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from homelibrarymanager.config import APP_NAME_EN, APP_VERSION  # noqa: E402

SPEC = ROOT / "packaging" / "HomeLibraryManager.spec"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
PYTHON = sys.executable
IS_WINDOWS = sys.platform == "win32"

#: Files that mean a folder is somebody's *data* folder rather than build
#: output.  The build refuses to touch a folder containing any of them.
DATA_FILENAMES = (
    "books.jsonl",
    "shelves.jsonl",
    "books.jsonl.bak",
    "shelves.jsonl.bak",
    "settings.ini",
    "crash.log",
)


def retire(folder: Path) -> None:
    """Move previous build output aside instead of deleting it.

    Two accidents this exists to prevent, one of which has already happened:

    * **The folder holds a running executable.**  ``shutil.rmtree`` deletes
      files one at a time, so it destroys part of the tree and *then* fails on
      the locked file - which is how a user's extracted copy lost its
      ``books.jsonl`` while its ``.exe`` was still open.
    * **The folder has become the user's data folder.**  Unzipping the app into
      ``dist`` and running it from there is a perfectly reasonable thing to do,
      and deleting the folder then destroys their catalogue.

    So: refuse outright when catalogue files are present, and otherwise rename.
    A rename either succeeds completely or fails completely, and the retired
    folder is only discarded once the new build has succeeded.
    """
    if not folder.exists():
        return

    found = sorted(
        {
            path.name
            for path in folder.rglob("*")
            if path.is_file() and path.name.lower() in DATA_FILENAMES
        }
    )
    if found:
        raise SystemExit(
            "\n!! 拒绝删除 {0}\n"
            "   里面发现了数据文件：{1}\n"
            "   这个文件夹已经被当成数据目录在用了。请先把程序和数据移到别的\n"
            "   位置（例如桌面），再重新打包。ZIP 解压后请放在 dist 之外运行。".format(
                folder, "、".join(found)
            )
        )

    aside = folder.with_name(folder.name + ".previous")
    if aside.exists():
        shutil.rmtree(aside, ignore_errors=True)
    try:
        folder.rename(aside)
    except OSError as exc:
        raise SystemExit(
            "\n!! 无法移动 {0}\n   {1}\n"
            "   通常是因为里面的程序正在运行。请先关闭它再打包。".format(folder, exc)
        )
    print("retired {0} -> {1}".format(folder.name, aside.name))


def discard_retired() -> None:
    for name in ("dist.previous", "build.previous"):
        aside = ROOT / name
        if aside.exists():
            shutil.rmtree(aside, ignore_errors=True)


def platform_tag() -> str:
    bits = struct.calcsize("P") * 8
    if IS_WINDOWS:
        return "win{0}".format(bits)
    return "{0}{1}".format(sys.platform, bits)


def run(description: str, command, cwd: Path = ROOT) -> None:
    print("\n=== {0} ===".format(description))
    print("    " + " ".join(str(part) for part in command))
    result = subprocess.run([str(part) for part in command], cwd=str(cwd))
    if result.returncode != 0:
        raise SystemExit(
            "\n!! {0} failed with exit code {1}".format(description, result.returncode)
        )


def human(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return "{0:.1f} {1}".format(size, unit)
        size /= 1024.0
    return "{0:.1f} GB".format(size)


def folder_size(folder: Path) -> int:
    return sum(path.stat().st_size for path in folder.rglob("*") if path.is_file())


def main() -> int:
    started = time.time()

    run("generate image assets", [PYTHON, ROOT / "tools" / "make_assets.py"])
    run(
        "check Windows 7 compatibility",
        [PYTHON, ROOT / "tools" / "check_win7_compat.py"],
    )

    for folder in (BUILD, DIST):
        retire(folder)

    run(
        "run PyInstaller",
        [
            PYTHON,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            DIST,
            "--workpath",
            BUILD,
            SPEC,
        ],
    )

    app_dir = DIST / APP_NAME_EN
    executable = app_dir / (APP_NAME_EN + (".exe" if IS_WINDOWS else ""))
    if not executable.exists():
        raise SystemExit("expected the build to produce {0}".format(executable))

    # The bundle has no console, so the self-test proves itself by writing an
    # image rather than by talking to stdout.
    proof = DIST / "self-test.png"
    run("self-test the built bundle", [executable, "--self-test", proof])
    if not proof.exists():
        raise SystemExit(
            "the self-test produced no image - the bundle did not start correctly"
        )
    print("    self-test image: {0}".format(human(proof.stat().st_size)))
    proof.unlink()

    archive = DIST / "{0}-{1}-{2}-portable.zip".format(
        APP_NAME_EN, APP_VERSION, platform_tag()
    )
    print("\n=== create {0} ===".format(archive.name))
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(app_dir.rglob("*")):
            if path.is_file():
                # Everything under a single top-level folder, so extracting
                # gives one tidy directory instead of a pile of DLLs.
                bundle.write(path, str(Path(APP_NAME_EN) / path.relative_to(app_dir)))

    files = sum(1 for path in app_dir.rglob("*") if path.is_file())
    discard_retired()
    print(
        "\n{0}\n"
        "  folder : {1}  ({2} files, {3})\n"
        "  zip    : {4}  ({5})\n"
        "  time   : {6:.1f}s".format(
            "-" * 60,
            app_dir,
            files,
            human(folder_size(app_dir)),
            archive,
            human(archive.stat().st_size),
            time.time() - started,
        )
    )
    print(
        "\nExtract the ZIP anywhere and run {0}. "
        "Nothing is installed and no admin rights are needed.".format(executable.name)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
