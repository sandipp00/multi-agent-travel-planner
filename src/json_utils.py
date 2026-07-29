"""Lenient JSON extraction from LLM text output.

Specialist agents are instructed to respond with JSON only, but models
occasionally wrap it in prose or a code fence — extract the first balanced
JSON value rather than trusting the response to be pure JSON.
"""

import json
import re

_JSON_BLOCK_RE = re.compile(r"\{.*\}|\[.*\]", re.DOTALL)


def parse_json_loose(text: str):
    """Parse the first JSON object/array found in `text`.

    Falls back to {"raw": text} if no valid JSON is found, so a malformed
    agent response degrades to visible raw text instead of raising.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = _JSON_BLOCK_RE.search(text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return {"raw": text}
