# PyAV / FFmpeg forrásarchívumok

Ezek a változatlan upstream forrásarchívumok a Windows csomag runtime-jához
tartoznak. A buildreceptet, patchfájlokat, manifestet és licencszövegeket az
egy szinttel feljebb található `av-runtime/packages/` könyvtár tartalmazza.

| Archívum | Forrás | SHA-256 |
|---|---|---|
| `av-17.1.0.tar.gz` | [PyPI source distribution](https://pypi.org/packages/source/a/av/av-17.1.0.tar.gz) | `7f1e71ff621b66253333926f948e00faae11d855b2442133c65128bca64cdeb3` |
| `ffmpeg-8.1.2.tar.gz` | [FFmpeg 8.1.2 source release](https://ffmpeg.org/releases/ffmpeg-8.1.2.tar.gz) | `32faba5ef67340d54724941eae1425580791195312a4fd13bf6f820a2818bf22` |

Az FFmpeg runtime LGPLv2.1-or-later licencet és a conda-forge által rögzített
`--disable-gpl --enable-version3` konfigurációt használ. A források és a build
recept jelenléte reprodukálható eredetet dokumentál; ez önmagában nem jogi
megfelelőségi vélemény.
