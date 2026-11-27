# Runtime upstream source archives

These original upstream archives are included under `_internal/licenses/upstream-sources/`
in the Windows package. The staging command downloads missing archives and checks each
SHA-256; `scripts/build-app.ps1 -Offline` and the PyInstaller spec reject missing or
mismatched inputs. Runtime application operation does not download these files.

| Archive | Upstream source | SHA-256 |
|---|---|---|
| `av-17.1.0.tar.gz` | [PyAV 17.1.0 PyPI source](https://pypi.org/packages/source/a/av/av-17.1.0.tar.gz) | `7f1e71ff621b66253333926f948e00faae11d855b2442133c65128bca64cdeb3` |
| `ffmpeg-8.1.2.tar.gz` | [FFmpeg 8.1.2 source release](https://ffmpeg.org/releases/ffmpeg-8.1.2.tar.gz) | `32faba5ef67340d54724941eae1425580791195312a4fd13bf6f820a2818bf22` |
| `qtbase-everywhere-src-6.12.0.tar.xz` | [QtBase 6.12.0 source release](https://download.qt.io/archive/qt/6.12/6.12.0/submodules/qtbase-everywhere-src-6.12.0.tar.xz) | `a951bd163c7b80fc6b8c88d7668fb56abf91c152373e13c10666763238131307` |
| `qtsvg-everywhere-src-6.12.0.tar.xz` | [QtSvg 6.12.0 source release](https://download.qt.io/archive/qt/6.12/6.12.0/submodules/qtsvg-everywhere-src-6.12.0.tar.xz) | `e4ab39534ec97987b1b9b60ef7f4d3253d5912a69f8c713a01753174a4029331` |
| `qtimageformats-everywhere-src-6.12.0.tar.xz` | [Qt Image Formats 6.12.0 source release](https://download.qt.io/archive/qt/6.12/6.12.0/submodules/qtimageformats-everywhere-src-6.12.0.tar.xz) | `0943132b5db8de6b6a7f1d162682173e8763c7ed94e80fd39113292845f67762` |
| `pyside-setup-v6.12.0.tar.gz` | [PySide / Qt for Python v6.12.0 source tag](https://github.com/pyside/pyside-setup/tree/v6.12.0) | `dce2a944b34320e51a0ec8100cb983956399b97dec386f0fbe39e1b52571a336` |

The PySide source archive contains `LICENSES/LGPL-3.0-only.txt`. Source archives
and version matches pin source material but do not by themselves prove that the
distributed wheels and DLLs were built from these trees; vendor build configuration,
toolchain and binary provenance remain under review in
[issue #54](https://github.com/tnyari/RoboAssist/issues/54).

The FFmpeg runtime is staged from the LGPLv2.1-or-later conda-forge build with its
recorded `--disable-gpl --enable-version3` configuration. Source material and build
metadata improve traceability; they are not a legal compliance opinion.

