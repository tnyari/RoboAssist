# Supplemental Python license sources

These license texts fill gaps in the exact locked wheels. Each text was fetched
from the repository tag matching the locked package version; SHA-256 values are
recorded in the generated `manifest.json` beside the packaged copy.

| Distribution | Version | License | Source |
|---|---:|---|---|
| ctranslate2 | 4.9.1 | MIT | [OpenNMT/CTranslate2 `v4.9.1` LICENSE](https://github.com/OpenNMT/CTranslate2/blob/v4.9.1/LICENSE) |
| flatbuffers | 25.12.19 | Apache-2.0 | [google/flatbuffers `v25.12.19` LICENSE](https://github.com/google/flatbuffers/blob/v25.12.19/LICENSE) |
| tokenizers | 0.23.3 | Apache-2.0 | [huggingface/tokenizers `v0.23.3` LICENSE](https://github.com/huggingface/tokenizers/blob/v0.23.3/LICENSE) |

The ONNX Runtime wheel supplies its own `LICENSE` and `ThirdPartyNotices.txt`;
the package collector copies those from the installed wheel into its license
directory. This supplemental list does not replace the package metadata or the
broader license review in `THIRD_PARTY_NOTICES.md`.
