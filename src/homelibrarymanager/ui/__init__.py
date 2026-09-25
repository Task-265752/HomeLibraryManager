"""The Qt interface.

This package is the **only** place in the project that imports PySide2.
Everything under ``core``, ``data`` and ``services`` stays Qt-free so it can be
tested without a display and reused from a command line if that is ever wanted.
"""
