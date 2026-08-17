"""Single source of truth for the Anthropic API key and model name.

One API key, one provider: every LLM call in this project (intent
extraction, generation, the DeepEval judges, the Promptfoo provider) goes
through this module.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# Cheapest model that's good enough for structured extraction/judging in this
# project. Override via REQVERIFY_MODEL if this snapshot ages out.
ANTHROPIC_MODEL = os.environ.get("REQVERIFY_MODEL", "claude-haiku-4-5-20251001")


def get_anthropic_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it or put it in a .env file "
            "and load it before running reqverify."
        )
    return key
