"""QA record schema for Medicare sales/service calls. Field descriptions are the single source
of truth for what each field means; they are sent to the model via structured output.

v2: Medicare-only scope. `domain` became `call_type`; `customer_intent` and `next_action` were
dropped (weak link to compliance QA, hardest to label consistently)."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "v3"


class CallType(str, Enum):
    plan_sales = "plan_sales"
    medical_equipment = "medical_equipment"
    member_service = "member_service"
    other = "other"


class Direction(str, Enum):
    inbound = "inbound"
    outbound = "outbound"
    unknown = "unknown"


class Outcome(str, Enum):
    sale = "sale"
    transfer = "transfer"
    callback = "callback"
    not_interested = "not_interested"
    issue_resolved = "issue_resolved"
    other = "other"


class ObjectionType(str, Enum):
    price = "price"
    already_covered = "already_covered"
    need_to_think = "need_to_think"
    spouse_or_family = "spouse_or_family"
    not_eligible = "not_eligible"
    distrust = "distrust"
    timing = "timing"
    other = "other"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Objection(_Strict):
    type: ObjectionType = Field(
        description=(
            "Kind of objection the customer raised. price: too expensive / premium or cost concern; "
            "already_covered: already has a plan, policy or provider; need_to_think: wants time to decide; "
            "spouse_or_family: must consult a spouse or family member; not_eligible: does not qualify; "
            "distrust: suspects a scam or distrusts the company/agent; timing: bad time, call later; "
            "other: any other objection."
        )
    )
    handled: bool = Field(
        description="True if the agent responded to this objection with an answer, offer or reassurance; "
        "false if it was ignored or the agent gave up."
    )


class RecordingDisclosed(_Strict):
    value: bool | None = Field(
        description="True if the call states it is recorded or monitored. False only if the transcript "
        "includes the call's opening (IVR message or first greeting) and no such statement is made. Null if "
        "the transcript starts mid-call or is too short or broken to tell, since a notice may have been "
        "played before the recording started."
    )
    evidence: str | None = Field(
        description="Short verbatim quote from the transcript that supports the value; null if value is not true."
    )


class Compliance(_Strict):
    recording_disclosed: RecordingDisclosed = Field(description="Whether call recording was disclosed.")


class CallQARecord(_Strict):
    call_type: CallType = Field(
        description=(
            "Kind of Medicare call. plan_sales: marketing, review or enrollment of Medicare Advantage, Part D or "
            "supplement plans (including 'your plan is getting upgraded' pitches); medical_equipment: offers of "
            "braces, monitors, supplies or other equipment covered by Medicare; member_service: an existing "
            "member's question about billing, claims, cards or coverage; other: anything else."
        )
    )
    direction: Direction = Field(
        description="inbound: the customer called the company; outbound: the agent called the customer; "
        "unknown: cannot be determined from the transcript."
    )
    outcome: Outcome = Field(
        description=(
            "How the call ended. sale: customer bought or enrolled on this call; transfer: the call ended by "
            "being passed to another agent or department (also set agent_handoff); callback: a later call was "
            "agreed; not_interested: customer declined; issue_resolved: the member's service request was "
            "handled on the call; other: anything else, including calls that drop or are cut off."
        )
    )
    objections: list[Objection] = Field(
        description="Each distinct objection the customer raised, once per type; empty list if none."
    )
    compliance: Compliance = Field(description="Compliance checks with verbatim evidence.")
    agent_handoff: bool = Field(
        description="True if the call was passed from one agent to another at any point during the call "
        "(warm/cold transfer or a second agent joining); false otherwise."
    )


def _inline_refs(node, defs: dict):
    if isinstance(node, list):
        return [_inline_refs(v, defs) for v in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        target = defs[node["$ref"].rsplit("/", 1)[-1]]
        siblings = {k: v for k, v in node.items() if k != "$ref"}
        return _inline_refs({**target, **siblings}, defs)
    return {k: _inline_refs(v, defs) for k, v in node.items()}


def strict_json_schema() -> dict:
    """JSON schema passed as structured output to every backend (OpenAI strict-mode compatible).
    $refs are inlined because strict mode rejects "$ref" with sibling keywords like "description"."""
    schema = CallQARecord.model_json_schema()
    defs = schema.pop("$defs", {})
    return _inline_refs(schema, defs)
