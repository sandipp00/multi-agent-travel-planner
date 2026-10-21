"""Lenient JSON extraction from LLM text output.

Specialist agents are instructed to respond with JSON only, but models
occasionally wrap it in prose or a code fence — extract the largest valid
JSON value rather than trusting the response to be pure JSON.
"""

import json

_decoder = json.JSONDecoder()


def parse_json_loose(text: str):
    """Parse the largest JSON object/array found in `text`.

    Tries to decode a JSON value at every `{` or `[` and keeps the longest
    one, so a short bracketed aside like "[1]" in surrounding prose doesn't
    win over the actual payload. Falls back to {"raw": text} if no valid JSON
    is found, so a malformed agent response degrades to visible raw text
    instead of raising.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    best, best_len = None, 0
    pos = 0
    while pos < len(text):
        if text[pos] in "{[":
            try:
                value, end = _decoder.raw_decode(text, pos)
            except json.JSONDecodeError:
                pos += 1
                continue
            if end - pos > best_len:
                best, best_len = value, end - pos
            # Skip past this value: anything nested inside it is smaller.
            pos = end
        else:
            pos += 1

    if best is not None:
        return best

    return {"raw": text}
