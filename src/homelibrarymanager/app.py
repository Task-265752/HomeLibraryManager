"""Application entry point: build the ``QApplication``, resolve the catalogue,
show the window.

Kept separate from ``__main__`` so the same wiring can be reused by the preview
renderer and by ``--self-test``, which the packaging script runs against a built
bundle to prove it actually starts.
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

from PySide2.QtCore import Qt
from PySide2.QtWidgets import QApplication

from .config import (
    APP_NAME,
    APP_NAME_EN,
    APP_VERSION,
    ORG_NAME,
    SETTINGS_FILENAME,
    application_dir,
    resource_dir,
)
from .data.library import Library
from .data.settings import Settings
from .ui.dpi import configure_high_dpi
from .ui.main_window import MainWindow
from .ui.startup_flow import run_startup
from .ui.theme import apply_theme, get_theme


def build_application(argv: Optional[Sequence[str]] = None) -> QApplication:
    """Create the ``QApplication`` with high DPI configured first.

    The order matters: Qt reads its scaling attributes when the application
    object is constructed, so ``configure_high_dpi`` has to run before this.
    """
    configure_high_dpi()
    app = QApplication(list(argv) if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME_EN)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(APP_VERSION)
    return app


def load_settings() -> Settings:
    """Settings always live beside the program, so they can be located before
    the catalogue folder is known."""
    settings = Settings(application_dir() / SETTINGS_FILENAME)
    settings.load()
    return settings


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments: List[str] = list(sys.argv if argv is None else argv)

    if "--self-test" in arguments:
        return run_self_test(arguments)

    app = build_application(arguments)
    theme = apply_theme(app, get_theme())

    # Before anything else can fail: leave a trace if it does.
    install_exception_reporting(application_dir())

    settings = load_settings()

    # Folder chooser, format check, warnings - or nothing at all on the common
    # path where the remembered folder still holds its files.
    result = run_startup(theme, settings)
    if result is None:
        return 0

    window = MainWindow(result.library, settings, theme)
    window.show()
    return app.exec_()


#: Written next to the program when something fails.
CRASH_LOG_NAME = "crash.log"


def install_exception_reporting(folder: Path) -> Path:
    """Make sure a failure leaves evidence on disk.

    A windowed build has no console, and PySide2 routes an exception raised
    inside a *slot* to ``sys.excepthook`` and then carries on running.  The
    visible result is a window that quietly stops updating - "sometimes the book
    I just added doesn't show up" - with nothing on screen to explain it and
    nothing to send to anyone.

    Writing the traceback next to the program turns that into a reportable
    problem.  Returns the log path.
    """
    log_path = folder / CRASH_LOG_NAME

    def hook(exc_type, value, trace):  # noqa: ANN001 - sys.excepthook signature
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, value, trace)
            return
        text = "".join(traceback.format_exception(exc_type, value, trace))
        try:
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write("\n" + "=" * 70 + "\n")
                handle.write("{0}  ({1})\n".format(datetime.now().isoformat(), APP_VERSION))
                handle.write(text)
        except OSError:
            pass
        _report("unhandled exception:\n" + text, error=True)

    sys.excepthook = hook
    return log_path


def _report(message: str, error: bool = False) -> None:
    """A ``print`` that survives a windowed build.

    PyInstaller's ``console=False`` executables have no stdout handle at all -
    ``sys.stdout`` is ``None`` and a bare ``print`` raises.  The self-test runs
    inside exactly such a bundle, so it must not depend on being able to talk to
    a console.
    """
    stream = sys.stderr if error else sys.stdout
    if stream is None:
        return
    try:
        stream.write(message + "\n")
        stream.flush()
    except (OSError, ValueError):
        pass


def run_self_test(arguments: Sequence[str]) -> int:
    """Render the window without a display, then exit.

    A PyInstaller bundle can build perfectly and still fail to start - a missing
    Qt platform plugin or an unbundled data file are both silent at build time.
    Running the real thing is the only way to catch that, so the packaging
    script invokes ``HomeLibraryManager.exe --self-test <image>`` and checks the
    image appears.
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    output: Optional[Path] = None
    index = list(arguments).index("--self-test")
    if index + 1 < len(arguments) and not arguments[index + 1].startswith("-"):
        output = Path(arguments[index + 1])

    app = build_application(list(arguments)[:1])
    theme = apply_theme(app, get_theme())

    with tempfile.TemporaryDirectory(prefix="hlm-selftest-") as scratch:
        library = Library(Path(scratch))
        library.load()
        library.ensure_files_exist()

        window = MainWindow(library, settings=None, theme=theme)
        window.setAttribute(Qt.WA_DontShowOnScreen, True)
        window.resize(900, 640)
        window.show()
        for _ in range(6):
            app.processEvents()

        if output is not None:
            if not window.grab().save(str(output)):
                _report("self-test: FAILED to write {0}".format(output), error=True)
                return 2
            _report("self-test: rendered {0}".format(output))

    _report("self-test: ok")
    _report("  resources : {0}".format(resource_dir()))
    _report("  platform  : {0}".format(os.environ.get("QT_QPA_PLATFORM", "native")))
    return 0
