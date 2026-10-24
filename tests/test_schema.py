import enum

import pydantic
import pytest

from src import schema
from src.schema import SCHEMA_VERSION, CallQARecord, strict_json_schema

VALID = {
    "domain": "medicare",
    "direction": "inbound",
    "customer_intent": "enroll_or_buy",
    "outcome": "transfer",
    "objections": [{"type": "price", "handled": True}],
    "compliance": {
        "recording_disclosed": {"value": True, "evidence": "this call is recorded"},
        "disclaimer_before_benefits": {"value": "not_applicable", "evidence": None},
    },
    "agent_handoff": True,
    "next_action": "transfer",
    "next_action_note": None,
}

MODELS = [
    schema.CallQARecord,
    schema.Objection,
    schema.Compliance,
    schema.RecordingDisclosed,
    schema.DisclaimerBeforeBenefits,
]


def test_valid_record_parses():
    assert CallQARecord.model_validate(VALID).domain.value == "medicare"


def test_unknown_enum_rejected():
    with pytest.raises(pydantic.ValidationError):
        CallQARecord.model_validate({**VALID, "outcome": "maybe"})


def test_extra_key_rejected():
    with pytest.raises(pydantic.ValidationError):
        CallQARecord.model_validate({**VALID, "foo": 1})


def test_every_enum_has_other_except_fixed_ones():
    # Direction uses `unknown`, DisclaimerValue uses `not_applicable` (spec §4)
    fixed = {schema.Direction: "unknown", schema.DisclaimerValue: "not_applicable"}
    enums = [
        obj
        for obj in vars(schema).values()
        if isinstance(obj, type) and issubclass(obj, enum.Enum) and obj.__module__ == schema.__name__
    ]
    assert len(enums) == 7
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
    assert len(objs) == 5
    for obj in objs:
        assert obj["additionalProperties"] is False
        assert obj["required"] == list(obj["properties"])


def test_strict_schema_has_no_refs():
    # OpenAI strict mode rejects "$ref" with sibling keywords such as "description"
    import json

    s = strict_json_schema()
    assert "$ref" not in json.dumps(s) and "$defs" not in s
    domain = s["properties"]["domain"]
    assert "medicare" in domain["enum"] and domain["description"].startswith("Business domain")
    item = s["properties"]["objections"]["items"]
    assert item["additionalProperties"] is False and "price" in item["properties"]["type"]["enum"]


def test_schema_version():
    assert SCHEMA_VERSION == "v1"
