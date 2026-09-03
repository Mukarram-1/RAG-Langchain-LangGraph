"""Command-line adapter for the Legal AI chatbot framework."""

import argparse
import asyncio
import logging
import sys
from uuid import uuid4

from src.chatbot import LegalAIChatbot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a read-only legal data lookup."
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="Question to ask; omit to start an interactive session.",
    )
    return parser.parse_args()


async def run(question: str | None) -> None:
    session_id = str(uuid4())
    async with LegalAIChatbot() as chatbot:
        if question:
            result = await chatbot.ask(question, thread_id=session_id)
            print(result.answer)
            return

        print("Legal AI structured lookup. Type 'quit' to exit.")
        while True:
            try:
                current = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if current.lower() in {"quit", "exit"}:
                return
            if not current:
                continue
            result = await chatbot.ask(current, thread_id=session_id)
            print(f"\nAssistant: {result.answer}")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    args = parse_args()
    try:
        asyncio.run(run(args.question))
    except Exception as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
