"""Multi-agent travel planner — interactive CLI.

Run with: python cli.py
"""

import sys

import groq

from src.llm_client import get_client
from src.orchestrator import run_turn

BANNER = """
Multi-Agent Travel Planner
---------------------------
Describe a trip you'd like planned (origin, destination, dates, budget) and
the orchestrator will delegate to flight, hotel, and activity search agents,
then check the plan against your budget. Type 'exit' to quit.
"""


def main() -> None:
    # Windows consoles default to cp1252, which can't print characters models
    # often emit (e.g. non-breaking hyphens) — replace rather than crash.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(BANNER)
    client = get_client()
    messages = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        turn_start = len(messages)
        messages.append({"role": "user", "content": user_input})
        print("\nPlanner is coordinating flight/hotel/activity/budget agents...\n")
        try:
            reply = run_turn(client, messages)
        except groq.APIError as exc:
            # Drop the failed turn so the next message starts from clean history.
            del messages[turn_start:]
            print(f"Planner error: {exc}\n")
            continue
        print(f"Planner: {reply}\n")


if __name__ == "__main__":
    main()
