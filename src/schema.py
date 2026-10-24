"""QA record schema (spec §4). Field descriptions are the single source of truth for
what each field means; they are sent to the model via structured output."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "v1"


class Domain(str, Enum):
    medicare = "medicare"
    auto_insurance = "auto_insurance"
    home_services = "home_services"
    health_insurance = "health_insurance"
    telecom = "telecom"
    other = "other"


class Direction(str, Enum):
    inbound = "inbound"
    outbound = "outbound"
    unknown = "unknown"


class CustomerIntent(str, Enum):
    enroll_or_buy = "enroll_or_buy"
    plan_or_quote_info = "plan_or_quote_info"
    billing = "billing"
    claim = "claim"
    cancel = "cancel"
    service_appointment = "service_appointment"
    technical_support = "technical_support"
    complaint = "complaint"
    other = "other"


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


class DisclaimerValue(str, Enum):
    yes = "yes"
    no = "no"
    not_applicable = "not_applicable"


class NextAction(str, Enum):
    none = "none"
    callback_scheduled = "callback_scheduled"
    transfer = "transfer"
    send_documents = "send_documents"
    follow_up_contact = "follow_up_contact"
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
        description="True if the call states it is recorded or monitored; false if the full call is present "
        "and no such statement is made; null if the transcript is too short or broken to tell."
    )
    evidence: str | None = Field(
        description="Short verbatim quote from the transcript that supports the value; null if value is not true."
    )


class DisclaimerBeforeBenefits(_Strict):
    value: DisclaimerValue = Field(
        description=(
            "Medicare compliance disclaimer timing. yes: the agent gave the required disclaimer (e.g. 'we do not "
            "offer every plan available in your area') before describing plan benefits; no: benefits were "
            "described before or without the disclaimer; not_applicable: no plan benefits were discussed, or "
            "the call is not a Medicare call."
        )
    )
    evidence: str | None = Field(
        description="Short verbatim quote of the disclaimer from the transcript; null if none was given."
    )


class Compliance(_Strict):
    recording_disclosed: RecordingDisclosed = Field(description="Whether call recording was disclosed.")
    disclaimer_before_benefits: DisclaimerBeforeBenefits = Field(
        description="Whether the Medicare disclaimer was given before benefits were discussed."
    )


class CallQARecord(_Strict):
    domain: Domain = Field(
        description=(
            "Business domain of the call. medicare: Medicare / Medicare Advantage / supplement plans; "
            "auto_insurance: car insurance quotes or policies; home_services: home repair, HVAC, plumbing, "
            "roofing, pest control, home warranty and similar; health_insurance: non-Medicare health plans; "
            "telecom: phone, internet or TV service; other: anything else."
        )
    )
    direction: Direction = Field(
        description="inbound: the customer called the company; outbound: the agent called the customer; "
        "unknown: cannot be determined from the transcript."
    )
    customer_intent: CustomerIntent = Field(
        description=(
            "Main reason the customer is on the call. enroll_or_buy: wants to sign up, enroll or purchase; "
            "plan_or_quote_info: wants information, a quote or a plan comparison without committing; "
            "billing: payments, charges or invoices; claim: filing or checking an insurance claim; "
            "cancel: wants to cancel a policy, plan or service; service_appointment: book, change or check "
            "a service visit; technical_support: help with something not working; complaint: expressing "
            "dissatisfaction; other: anything else."
        )
    )
    outcome: Outcome = Field(
        description=(
            "How the call ended. sale: customer bought or enrolled on this call; transfer: the call ended by "
            "being passed to another agent or department (also set agent_handoff); callback: a later call was "
            "agreed; not_interested: customer declined; issue_resolved: the customer's service request was "
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
    next_action: NextAction = Field(
        description=(
            "Agreed follow-up after the call. none: nothing agreed; callback_scheduled: a call at a specific "
            "or agreed later time; transfer: customer is being transferred now; send_documents: documents, "
            "quotes or information will be sent; follow_up_contact: an unspecified future contact; other: "
            "anything else."
        )
    )
    next_action_note: str | None = Field(
        description="One short sentence describing the next action, or null if next_action is none."
    )


def strict_json_schema() -> dict:
    """JSON schema passed as structured output to every backend (OpenAI strict-mode compatible)."""
    return CallQARecord.model_json_schema()
