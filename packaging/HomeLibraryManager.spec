# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the portable Windows build.

**onedir, not onefile.**  onefile unpacks the whole payload into a temporary
folder on *every* launch, which costs several seconds and requires a writable
temp directory.  onedir starts immediately, and the project owner explicitly
asked for a multi-file folder they can zip and carry around.

**UPX is off.**  UPX-packed executables are one of the most common causes of
antivirus false positives on PyInstaller output, and a family tool that gets
quarantined is far worse than one that is 9 MB larger.

**No binary trimming.**  An earlier revision of this file deleted Qt DLLs that
look unused (Qt5Quick, Qt5QmlModels, Qt5WebSockets, the WebGL platform plugin)
and kept only modules that were explicitly excluded.  It shrank the folder by
about 9 MB and broke the program completely::

    ImportError: DLL load failed while importing QtCore

``pefile`` showed why.  ``PySide2/pyside2.abi3.dll`` - the support library every
PySide2 extension module links against - **statically imports Qt5Qml.dll**, even
though this program never touches QML.  Removing it takes the whole binding down
with it.

Nine megabytes is not worth the risk, so only the Python-level ``excludes``
remain.  That is also enough to keep QtWebEngine out: PyInstaller's analysis
only collects what is actually imported, and this program imports neither
WebEngine nor QML.  ``tools/build_windows.py`` runs the result with
``--self-test`` afterwards regardless, because a bundle that builds is not
automatically a bundle that starts.
"""

import os
import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 - SPECPATH is injected
sys.path.insert(0, str(ROOT / "src"))

from homelibrarymanager.config import APP_NAME_EN, RESOURCES_DIRNAME  # noqa: E402

RESOURCES = ROOT / "src" / "homelibrarymanager" / RESOURCES_DIRNAME
ICON = RESOURCES / "app.ico"

# Python modules this program never imports.  Excluding the Qt binding module
# also stops PyInstaller's hook from collecting the matching DLL, which is how
# WebEngine and the rest of the QML stack stay out without hand-pruning files.
EXCLUDES = [
    "PySide2.QtWebEngine",
    "PySide2.QtWebEngineCore",
    "PySide2.QtWebEngineWidgets",
    "PySide2.QtWebChannel",
    "PySide2.QtWebSockets",
    "PySide2.QtMultimedia",
    "PySide2.QtMultimediaWidgets",
    "PySide2.QtCharts",
    "PySide2.QtDataVisualization",
    "PySide2.QtBluetooth",
    "PySide2.QtNfc",
    "PySide2.QtPositioning",
    "PySide2.QtLocation",
    "PySide2.QtSerialPort",
    "PySide2.QtSensors",
    "PySide2.QtGamepad",
    "PySide2.QtDesigner",
    "PySide2.QtHelp",
    "PySide2.QtTest",
    "PySide2.QtSql",
    "PySide2.QtXmlPatterns",
    "PySide2.QtRemoteObjects",
    "PySide2.QtScript",
    "PySide2.QtScriptTools",
    "PySide2.QtTextToSpeech",
    "PySide2.QtUiTools",
    "PySide2.Qt3DCore",
    "PySide2.Qt3DRender",
    "PySide2.Qt3DInput",
    "PySide2.Qt3DLogic",
    "PySide2.Qt3DAnimation",
    "PySide2.Qt3DExtras",
    # Standard library weight the program never touches.
    "tkinter",
    "unittest",
    "pydoc_data",
    "lib2to3",
    "test",
]

# --------------------------------------------------------------------------
# Third-party licences
# --------------------------------------------------------------------------
# Qt and PySide2 are LGPL v3.  Distributing binaries that contain them obliges us
# to (a) ship the licence text and (b) let the recipient swap the libraries out.
#
# (b) is already satisfied - Qt is linked dynamically, so replacing
# PySide2/Qt5*.dll is enough and needs no rebuild.  But (a) only holds if the
# texts actually travel with the build, and PyInstaller does not collect them on
# its own: the first release of this project shipped with no licence file at all.
import glob  # noqa: E402

import PySide2  # noqa: E402

SITE_PACKAGES = Path(PySide2.__file__).resolve().parent.parent
THIRD_PARTY_LICENCES = [
    (path, "licenses")
    for dist_info in sorted(glob.glob(str(SITE_PACKAGES / "PySide2-*.dist-info")))
    for path in sorted(glob.glob(os.path.join(dist_info, "LICENSE.*")))
]

DATAS = [(str(RESOURCES), "homelibrarymanager/" + RESOURCES_DIRNAME)]
DATAS += THIRD_PARTY_LICENCES

# CPython's LICENSE.txt is the *aggregate* licence file for the whole Python
# distribution: the PSF licence, the Microsoft Distributable Code terms that
# cover VCRUNTIME140.dll and ucrtbase.dll, the OpenSSL/SSLeay licence covering
# libcrypto-1_1.dll and libssl-1_1.dll, plus bzip2, libffi, expat and zlib.
# Bundling it settles every remaining attribution obligation in one file.
PYTHON_LICENCE = Path(sys.base_prefix) / "LICENSE.txt"
if PYTHON_LICENCE.is_file():
    DATAS.append((str(PYTHON_LICENCE), "licenses"))
else:  # pragma: no cover - only if built against an unusual Python
    print("WARNING: {0} not found; the bundle will ship without the Python, "
          "Microsoft runtime and OpenSSL licences".format(PYTHON_LICENCE))

for extra in ("LICENSE", "THIRD-PARTY-NOTICES.md", "README.md"):
    candidate = ROOT / extra
    if candidate.is_file():
        DATAS.append((str(candidate), "."))

a = Analysis(  # noqa: F821 - injected by PyInstaller
    [str(ROOT / "run.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=DATAS,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME_EN,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ICON),
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME_EN,
)
