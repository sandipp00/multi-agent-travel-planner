"""Shared Anthropic client and the web-search call pattern used by every
specialist agent.
"""

import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_client() -> anthropic.Anthropic:
    """Return a process-wide Anthropic client.

    Resolves credentials the standard way (ANTHROPIC_API_KEY, or an
    `ant auth login` profile) — no key is hardcoded here.
    """
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def call_with_web_search(
    client: anthropic.Anthropic,
    system: str,
    user_message: str,
    model: str,
    effort: str = "medium",
    max_tokens: int = 4096,
    max_uses: int = 5,
    max_continuations: int = 3,
) -> str:
    """Run a single-purpose Claude call equipped with the web_search tool.

    Handles the `pause_turn` stop reason (the server-side search loop hit its
    round-trip limit) by resending, per the tool-use docs — at most
    `max_continuations` times, so a search that keeps pausing can't loop (and
    bill) forever. Returns the final response's concatenated text blocks.
    """
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": max_uses}]
    messages = [{"role": "user", "content": user_message}]

    for _ in range(max_continuations + 1):
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
            output_config={"effort": effort},
        )

        if response.stop_reason == "pause_turn":
            messages = [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": response.content},
            ]
            continue

        if response.stop_reason == "refusal":
            return '{"error": "The search agent declined this request."}'

        return "".join(block.text for block in response.content if block.type == "text")

    return '{"error": "The search agent did not finish within its continuation limit."}'
