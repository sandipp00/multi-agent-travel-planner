"""Shared Groq client and the search-then-summarize call pattern used by
every specialist agent.
"""

from ddgs import DDGS
from dotenv import load_dotenv
from groq import Groq

from src.config import SEARCH_MAX_RESULTS, SEARCH_SNIPPET_CHARS

load_dotenv()

_client = None


def get_client() -> Groq:
    """Return a process-wide Groq client.

    Reads GROQ_API_KEY from the environment (or .env) — no key is hardcoded
    here. Free keys come from https://console.groq.com/keys.
    """
    global _client
    if _client is None:
        # The free tier's tokens-per-minute limit is easy to hit mid-plan;
        # extra retries let the SDK wait out the server's retry-after delay.
        _client = Groq(max_retries=6)
    return _client


def web_search(query: str, max_results: int = SEARCH_MAX_RESULTS) -> list:
    """Search the web with DuckDuckGo (free, no API key).

    Returns [] on any search failure (rate limit, network error) so the
    agent can fall back to labeled estimates instead of crashing.
    """
    try:
        return DDGS().text(query, max_results=max_results)
    except Exception:
        return []


def _format_results(results: list) -> str:
    if not results:
        return (
            "No web results were available. Use clearly-labeled realistic "
            'estimates and say so in "notes".'
        )
    lines = []
    for i, result in enumerate(results, 1):
        body = (result.get("body") or "")[:SEARCH_SNIPPET_CHARS]
        lines.append(f"{i}. {result.get('title', '')} — {result.get('href', '')}\n   {body}")
    return "\n".join(lines)


def call_with_web_search(
    client: Groq,
    system: str,
    user_message: str,
    model: str,
    search_query: str = "",
    max_tokens: int = 4096,
) -> str:
    """Run a single-purpose specialist call grounded in fresh web results.

    Searches DuckDuckGo for `search_query` (or `user_message` if empty),
    puts the results in the prompt, and returns the model's text reply.
    """
    results = web_search(search_query or user_message)
    prompt = f"{user_message}\n\nWeb search results:\n{_format_results(results)}"

    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content or ""
