"""Use the filesystem-pinned PyAV module set prepared by roboassist.spec.

The contrib hook imports every PyAV submodule while collecting it. That import
can fail during analysis on Windows when the native FFmpeg DLL search path has
not yet been initialized. The spec already enumerates every ``.py``/``.pyd``
module and stages the hash-locked FFmpeg DLLs, so this hook only declares the
stdlib imports that Cython modules can load dynamically.
"""

hiddenimports = ["dataclasses", "fractions", "uuid"]

