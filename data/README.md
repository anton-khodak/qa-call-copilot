# Data

Source: [CallCenterEN (AIxBlock)](https://huggingface.co/datasets/AIxBlock/92k-real-world-call-center-scripts-english), English call-centre transcripts in AssemblyAI JSON (`text`, `confidence`, `audio_duration`, `words` with timestamps, `redacted_pii_policies`). PII is already masked (`[PERSON_NAME]`, `[MONEY_AMOUNT]`, `[DATE]`, …). No speaker labels. The dataset is not gated.

**Licence: CC BY-NC 4.0, no redistribution.** Raw transcripts are not committed; `make data` downloads exactly the calls in `manifest.csv` into `data/raw/` (gitignored).

## Selection

36 calls from 3 domains, chosen by `data/download.py` with seed 42. Per domain, 12 calls: 3 from each file-size band (bottom 5%, 5–35%, 35–65%, 65–100%), so a few short or broken calls are always included. File size is used as a proxy for call length so selection needs no full download. 0-byte files are skipped.

| Domain | Source zip | Calls available | Selected | Golden | Dev |
|---|---|---|---|---|---|
| medicare | `medicare_inbound.zip` | 61,513 | 12 | 4 | 8 |
| auto_insurance | `auto_insurance_customer_service_inbound.zip` | 1,749 | 12 | 3 | 9 |
| home_services | `home_service_inbound.zip` | 11,407 | 12 | 3 | 9 |
| **total** | | | **36** | **10** | **26** |

## Length distribution

| Domain | Duration min / median / max (s) | Words min / median / max |
|---|---|---|
| medicare | 194 / 318 / 719 | 81 / 431 / 1,682 |
| auto_insurance | 236 / 310 / 3,482 | 85 / 536 / 7,763 |
| home_services | 123 / 224 / 830 | 71 / 338 / 1,424 |
| all | 123 / 303 / 3,482 | 71 / 460 / 7,763 |

## Files

- `manifest.csv`: call_id, domain, source zip and member, file size, duration, word count, split (`golden` / `dev`).
- `golden/golden_v1.jsonl`: hand labels for the 10 golden calls; rules in `golden/LABELING.md`.
- `raw/<domain>/<call_id>.json`: downloaded transcripts (gitignored).
