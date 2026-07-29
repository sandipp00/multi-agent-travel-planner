"""Model configuration for the orchestrator and specialist agents."""

# The orchestrator plans and reasons over specialist results — run it at the
# API default effort ("high") for planning quality.
MODEL_ORCHESTRATOR = "claude-opus-5"
ORCHESTRATOR_MAX_TOKENS = 8000

# Specialist agents do a bounded, focused web-search task each — "medium"
# effort keeps cost/latency down without hurting result quality.
MODEL_AGENT = "claude-opus-5"
AGENT_EFFORT = "medium"
AGENT_MAX_TOKENS = 4096
