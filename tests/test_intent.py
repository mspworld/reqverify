"""Unit tests for intent.py's parsing logic. No Claude calls — the Anthropic
client is mocked with a hand-built fixture standing in for a real tool_use
response, so this stays fast and free while still exercising the real
extract_intent() code path.
"""
from unittest.mock import MagicMock, patch

import pytest

from core.intent import extract_intent
from core.schema import Intent


def _fake_tool_response(payload: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.name = "record_intent"
    block.input = payload
    resp = MagicMock()
    resp.content = [block]
    return resp


FIXTURE_PAYLOAD = {
    "goal": "Apply a valid coupon during checkout.",
    "actor": "user",
    "action": "enters a coupon code and clicks Apply",
    "expected": ["discount reflected in total"],
    "not_expected": ["discount applied when coupon is invalid"],
    "keywords": ["coupon", "checkout", "discount"],
}


def test_extract_intent_parses_tool_call_into_intent():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_tool_response(FIXTURE_PAYLOAD)
    with patch("core.intent.anthropic.Anthropic", return_value=fake_client):
        result = extract_intent("some requirement text")

    assert isinstance(result, Intent)
    assert result.goal == FIXTURE_PAYLOAD["goal"]
    assert result.not_expected == ["discount applied when coupon is invalid"]
    fake_client.messages.create.assert_called_once()


def test_extract_intent_forces_the_tool_choice():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_tool_response(FIXTURE_PAYLOAD)
    with patch("core.intent.anthropic.Anthropic", return_value=fake_client):
        extract_intent("some requirement text")

    _, kwargs = fake_client.messages.create.call_args
    assert kwargs["tool_choice"] == {"type": "tool", "name": "record_intent"}


def test_extract_intent_raises_if_model_never_calls_the_tool():
    resp = MagicMock()
    resp.content = []
    fake_client = MagicMock()
    fake_client.messages.create.return_value = resp
    with patch("core.intent.anthropic.Anthropic", return_value=fake_client):
        with pytest.raises(RuntimeError):
            extract_intent("some requirement text")
