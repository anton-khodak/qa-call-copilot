import json

import httpx2
import openai

from src.clients.base import Completion
from src.config import load_model
from src.dataset import Transcript
from tests.test_schema import VALID

VALID_JSON = json.dumps(VALID)


def transcript(text="Hi, this call is recorded.", domain="medicare", call_id="c1", split="golden"):
    return Transcript(call_id=call_id, domain=domain, split=split, text=text, audio_duration=10, words=[])


def timeout_error():
    return openai.APITimeoutError(request=httpx2.Request("POST", "https://openrouter.ai"))


def bad_request():
    req = httpx2.Request("POST", "https://openrouter.ai")
    return openai.BadRequestError("bad schema", response=httpx2.Response(400, request=req), body=None)


class FakeClient:
    """ModelClient that returns (str/None → Completion) or raises queued items in order."""

    def __init__(self, *items, input_tokens=1000, output_tokens=200):
        self.config = load_model("gpt4o_mini")
        self.items = list(items)
        self.tokens = (input_tokens, output_tokens)
        self.calls = []

    def complete(self, system, user, schema, sampling):
        self.calls.append((system, user, schema, sampling))
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        return Completion(item, *self.tokens)
