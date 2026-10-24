# Labelling rules — golden_v1

Labels are hand-made from the transcript text only (`data/raw/<domain>/<call_id>.json`, field `text`). Never look at model output for a call before or while labelling it. Label only what the text supports; when it doesn't, use the field's fallback value (`unknown`, `null`, `not_applicable`, `other`) exactly as the rules below say. The rules mirror the `Field(description=...)` text in `src/schema.py`; if the two disagree, fix both and bump the golden version.

File format: one JSON object per line, `{"call_id": "<manifest call_id>", "label": {<CallQARecord>}}`. Only `golden` rows from `data/manifest.csv`. Check with `uv run python -c "from src.golden import load_golden; print(len(load_golden()))"`.

## Fields

- **domain**: medicare (Medicare / Medicare Advantage / supplement), auto_insurance, home_services (repair, HVAC, plumbing, roofing, pest control, home warranty…), health_insurance (non-Medicare health plans), telecom, other. Judge from the conversation, not from the source zip.
- **direction**: inbound if the customer called the company (e.g. "thanks for calling", customer states why they called); outbound if the agent called the customer (e.g. "I'm calling about…", customer surprised by the call); unknown if there's no clue.
- **customer_intent**: the customer's main reason for the call. enroll_or_buy (sign up / purchase), plan_or_quote_info (information, quote or comparison without committing), billing, claim, cancel, service_appointment (book / change / check a visit), technical_support, complaint, other.
- **outcome**: how the call ends. sale (bought / enrolled on this call), transfer (call ends by being passed on; also set agent_handoff), callback (a later call agreed), not_interested (customer declined), issue_resolved (service request handled), other (incl. calls that drop or are cut off).
- **objections**: one entry per distinct objection type the *customer* raised: price, already_covered, need_to_think, spouse_or_family, not_eligible, distrust, timing, other. `handled` = true if the agent answered it with an answer, offer or reassurance. Empty list if none.
- **compliance.recording_disclosed.value**: true if the call says it is recorded or monitored; false if the full call is present and no such statement is made; null only if the transcript is too short or cut off to tell. **evidence**: short verbatim quote, or null if value is not true.
- **compliance.disclaimer_before_benefits.value**: yes if the Medicare disclaimer (e.g. "we do not offer every plan available in your area") comes before the first description of plan benefits (premiums, copays, dental/vision/hearing, drug coverage, giveback/allowances); no if benefits came first or no disclaimer was given; not_applicable if no benefits were discussed or the call is not Medicare. Asking about current coverage is not discussing benefits. **evidence**: verbatim disclaimer quote, or null.
- **agent_handoff**: true if the customer is passed to another agent or department at any point, or a second agent joins (e.g. screener → licensed agent).
- **next_action**: none, callback_scheduled (a call at an agreed time), transfer (being transferred now), send_documents (documents, quotes or info will be sent), follow_up_contact (unspecified future contact), other. **next_action_note**: one short sentence, or null if none. Not scored.

## Evidence quotes
Copy verbatim from `text`, including ASR errors and `[PLACEHOLDERS]`. A few words up to one sentence.
