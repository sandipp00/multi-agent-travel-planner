"""Model configuration for the orchestrator and specialist agents.

Both run on Groq's free tier. Override the model IDs with environment
variables if Groq retires one (see https://console.groq.com/docs/models).
"""

import os

# The orchestrator plans and reasons over specialist results — use the
# larger model for planning quality and reliable tool calling.
MODEL_ORCHESTRATOR = os.getenv("GROQ_ORCHESTRATOR_MODEL", "openai/gpt-oss-120b")
ORCHESTRATOR_MAX_TOKENS = 8000
# Upper bound on tool-calling rounds per user turn, so a model that keeps
# calling tools can't loop forever.
MAX_TOOL_ROUNDS = 8

# Specialist agents each summarize one bounded set of search results — the
# smaller model is faster and stretches the free-tier rate limits further.
MODEL_AGENT = os.getenv("GROQ_AGENT_MODEL", "openai/gpt-oss-20b")
AGENT_MAX_TOKENS = 4096

# Web results fed to each specialist. Kept small so prompts stay within the
# free tier's tokens-per-minute limit.
SEARCH_MAX_RESULTS = 6
SEARCH_SNIPPET_CHARS = 300
