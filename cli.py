"""Multi-agent travel planner — interactive CLI.

Run with: python cli.py
"""

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

        messages.append({"role": "user", "content": user_input})
        print("\nPlanner is coordinating flight/hotel/activity/budget agents...\n")
        reply = run_turn(client, messages)
        print(f"Planner: {reply}\n")


if __name__ == "__main__":
    main()
