# Labelling rules — golden_v2 (schema v2, Medicare-only)

Labels are hand-made from the transcript text only (`data/raw/<segment>/<call_id>.json`, field `text`). Never look at model output for a call before or while labelling it. Label only what the text supports; when it doesn't, use the field's fallback value (`unknown`, `null`, `not_applicable`, `other`) exactly as below. The rules mirror the `Field(description=...)` text in `src/schema.py`; if the two disagree, fix both and bump the golden version. Compare runs only within one golden version.

File: `data/golden/golden_v2.jsonl`, one JSON object per line, `{"call_id": "<manifest call_id>", "label": {<CallQARecord>}}`, only `golden` rows from `data/manifest.csv`. Check with `uv run python -c "from src.golden import load_golden; print(len(load_golden()))"` (expect `10`). `golden_v1.jsonl` is the abandoned 3-domain draft and is not scored.

## What gets scored

| Field | Kind | Scored as |
|---|---|---|
| `call_type`, `direction`, `outcome` | inferred | exact match, plus per-class accuracy |
| `agent_handoff`, `compliance.recording_disclosed.value`, `compliance.disclaimer_before_benefits.value` | extracted | exact match |
| `objections` | extracted | precision / recall / F1 on types, accuracy of `handled` on matched types |
| `evidence` quotes | — | **not scored** against labels (code checks model quotes against the transcript). Optional: fill in if it helps you decide, otherwise `null` |

The compliance fields are the product: label them most carefully.

## Fields

- **call_type** (inferred): plan_sales (marketing, review or enrollment of Medicare Advantage, Part D or supplement plans, including "your plan is getting upgraded" pitches); medical_equipment (braces, monitors, supplies or other equipment covered by Medicare); member_service (an existing member's billing, claims, card or coverage question); other.
- **direction** (inferred): inbound if the customer called (e.g. "thanks for calling", customer states why they called); outbound if the agent called (e.g. "I'm calling about…", customer surprised by the call); unknown if there's no clue.
- **outcome** (inferred): how the call ends. sale (enrolled or ordered on this call), transfer (call ends by being passed on; also set agent_handoff), callback (a later call agreed), not_interested (customer declined), issue_resolved (member's service request handled), other (incl. calls that drop or are cut off).
- **objections** (extracted): one entry per distinct objection type the *customer* raised: price, already_covered, need_to_think, spouse_or_family, not_eligible, distrust, timing, other. `handled` = true if the agent answered it with an answer, offer or reassurance. Empty list if none.
- **agent_handoff** (extracted): true if the customer is passed to another agent or department at any point, or a second agent joins (e.g. screener → licensed agent).
- **compliance.recording_disclosed.value** (extracted): true if the call says it is recorded or monitored. false **only if the transcript includes the call's opening** (IVR message or first greeting) and no notice is given. null if the transcript starts mid-call or is too short or cut off to tell — a notice may have been played before the recording started.
- **compliance.disclaimer_before_benefits.value** (extracted): yes if the CMS third-party marketing disclaimer (e.g. "we do not offer every plan available in your area", or that the agent represents a limited number of plans) comes before the first description of plan benefits; no if benefits came first or no disclaimer was given; not_applicable if no Medicare Advantage / Part D / supplement plan benefits were discussed (equipment offers and service questions are usually not_applicable). Benefits = premiums, copays, dental/vision/hearing, drug coverage, giveback or allowances; asking about current coverage is not discussing benefits. With a screener → licensed agent handoff, judge the disclaimer against the first benefit description, whoever says it.
