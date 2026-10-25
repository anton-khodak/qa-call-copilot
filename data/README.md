# Data

Source: [CallCenterEN (AIxBlock)](https://huggingface.co/datasets/AIxBlock/92k-real-world-call-center-scripts-english), English call-centre transcripts in AssemblyAI JSON (`text`, `confidence`, `audio_duration`, `words` with timestamps, `redacted_pii_policies`). PII is already masked (`[PERSON_NAME]`, `[MONEY_AMOUNT]`, `[DATE]`, …). No speaker labels. The dataset is not gated.

**Licence and attribution:** the 36 transcripts in `raw/` are unmodified files from CallCenterEN by AIxBlock (Gaurav Chawla, Raghu Banda, Caleb DeLeeuw; [paper](https://arxiv.org/abs/2507.02958)), licensed [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). They are included for non-commercial coursework only. Note that the dataset card also says "Commercial use, resale, or redistribution is prohibited." `make data` re-downloads exactly the calls in `manifest.csv` if any are missing.

## Scope: Medicare calls, three call types

The product is compliance QA for Medicare sales calls (CMS requires a third-party marketing disclaimer before plan benefits are discussed), so every call is a Medicare call. The three "document types" are call types, each from one source zip:

| Segment | Source zip | Expected `call_type` | Calls in zip | Read | Selected | Golden | Dev |
|---|---|---|---|---|---|---|---|
| inbound_plan | `automotive_and_healthcare_insurance_inbound.zip` | plan_sales | 1,793 | 32 | 12 | 4 | 8 |
| outbound_plan | `insurance_outbound.zip` | plan_sales | 4,005 | 12 | 12 | 3 | 9 |
| outbound_equipment | `medical_equipment_outbound.zip` | medical_equipment | 738 | 14 | 12 | 3 | 9 |
| **total** | | | | | **36** | **10** | **26** |

## Selection

`data/download.py`, seed 42. Per segment, 12 calls: 3 from each file-size band (bottom 5%, 5–35%, 35–65%, 65–100%; file size stands in for call length so selection needs no full download; 0-byte files skipped). Within a band, members are read in seeded random order and kept only if the text mentions "Medicare".

Why the filter: source zips are labelled by campaign, not content. `medicare_inbound.zip` is **not** used: in a random sample of 40 calls only 2 mentioned Medicare (12 were veterinary clinics). `automotive_and_healthcare_insurance_inbound.zip` mixes auto and Medicare calls (about 40% mention Medicare). The filter makes every call relevant to the compliance rules, at a cost: very short or broken calls rarely say "Medicare", so the shortest selected call is 227 words. Short/broken-call behaviour is under-tested as a result.

## Length distribution

| Segment | Duration min / median / max (s) | Words min / median / max |
|---|---|---|
| inbound_plan | 216 / 432 / 3,130 | 274 / 652 / 2,783 |
| outbound_plan | 135 / 296 / 499 | 284 / 644 / 1,060 |
| outbound_equipment | 156 / 490 / 964 | 227 / 766 / 1,883 |
| all | 135 / 354 / 3,130 | 227 / 688 / 2,783 |

## Files

- `manifest.csv`: call_id, segment, source zip and member, file size, duration, word count, split (`golden` / `dev`).
- `golden/golden_v2.jsonl`: hand labels for the 10 golden calls (schema v2); rules in `golden/LABELING.md`.
- `raw/<segment>/<call_id>.json`: the selected transcripts (AssemblyAI JSON as published).
