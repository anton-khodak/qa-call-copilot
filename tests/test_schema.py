import enum
import json

import pydantic
import pytest

from src import schema
from src.schema import SCHEMA_VERSION, CallQARecord, strict_json_schema

VALID = {
    "call_type": "plan_sales",
    "direction": "outbound",
    "outcome": "transfer",
    "objections": [{"type": "price", "handled": True}],
    "compliance": {
        "recording_disclosed": {"value": True, "evidence": "this call is recorded"},
    },
    "agent_handoff": True,
}

MODELS = [
    schema.CallQARecord,
    schema.Objection,
    schema.Compliance,
    schema.RecordingDisclosed,
]


def test_valid_record_parses():
    assert CallQARecord.model_validate(VALID).call_type.value == "plan_sales"


def test_unknown_enum_rejected():
    with pytest.raises(pydantic.ValidationError):
        CallQARecord.model_validate({**VALID, "outcome": "maybe"})


def test_extra_key_rejected():
    with pytest.raises(pydantic.ValidationError):
        CallQARecord.model_validate({**VALID, "foo": 1})


def test_every_enum_has_other_except_fixed_ones():
    # Direction uses `unknown` (spec §4)
    fixed = {schema.Direction: "unknown"}
    enums = [
        obj
        for obj in vars(schema).values()
        if isinstance(obj, type) and issubclass(obj, enum.Enum) and obj.__module__ == schema.__name__
    ]
    assert len(enums) == 4
    for e in enums:
        assert fixed.get(e, "other") in {m.value for m in e}, e


def test_every_field_has_description():
    for model in MODELS:
        for name, field in model.model_fields.items():
            assert field.description, f"{model.__name__}.{name}"


def _objects(node):
    if isinstance(node, dict):
        if node.get("type") == "object":
            yield node
        for v in node.values():
            yield from _objects(v)
    elif isinstance(node, list):
        for v in node:
            yield from _objects(v)


def test_strict_schema_shape():
    objs = list(_objects(strict_json_schema()))
    assert len(objs) == 4
    for obj in objs:
        assert obj["additionalProperties"] is False
        assert obj["required"] == list(obj["properties"])


def test_strict_schema_has_no_refs():
    # OpenAI strict mode rejects "$ref" with sibling keywords such as "description"
    import json

    s = strict_json_schema()
    assert "$ref" not in json.dumps(s) and "$defs" not in s
    call_type = s["properties"]["call_type"]
    assert "plan_sales" in call_type["enum"] and call_type["description"].startswith("Kind of Medicare call")
    item = s["properties"]["objections"]["items"]
    assert item["additionalProperties"] is False and "price" in item["properties"]["type"]["enum"]


def test_v3_fields():
    # Medicare-only scope; intent and next_action dropped in v2, the disclaimer field in v3
    assert list(CallQARecord.model_fields) == [
        "call_type", "direction", "outcome", "objections", "compliance", "agent_handoff"]
    assert set(schema.CallType.__members__) == {"plan_sales", "medical_equipment", "member_service", "other"}


def test_recording_rule_only_false_when_opening_present():
    desc = schema.RecordingDisclosed.model_fields["value"].description.lower()
    assert "opening" in desc and "null" in desc


def test_schema_v3_has_no_disclaimer():
    assert SCHEMA_VERSION == "v3"
    assert list(schema.Compliance.model_fields) == ["recording_disclosed"]
    assert "disclaimer" not in json.dumps(strict_json_schema()).lower()


def test_disclaimer_key_rejected():
    d = {**VALID, "compliance": {**VALID["compliance"],
                                 "disclaimer_before_benefits": {"value": "no", "evidence": None}}}
    with pytest.raises(pydantic.ValidationError):
        CallQARecord.model_validate(d)
