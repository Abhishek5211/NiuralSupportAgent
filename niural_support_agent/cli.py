"""Interactive terminal chat. No model request until a question is entered."""

import argparse
import asyncio
import sys

from pydantic import ValidationError

from .agent import SupportAgent
from .config import Config


async def chat(*, verbose=False):
    config = Config.load()
    agent = SupportAgent(config)
    session_id = "cli-chat"
    print(f"Niural support | {config.model}" if verbose else "Niural support")
    print("/reset clears this conversation; /quit exits. Ctrl+C also exits.")
    try:
        while True:
            try:
                question = input("\nYou: ").strip()
            except EOFError:
                break
            if question.lower() == "/quit":
                break
            if question.lower() == "/reset":
                agent.reset(session_id)
                print("Conversation cleared.")
                continue
            if not question:
                continue

            line_open = False
            received_text = False
            tool_names = {}

            def show_text(text):
                nonlocal line_open, received_text
                if not text:
                    return
                if not line_open:
                    print("Assistant: ", end="", flush=True)
                    line_open = True
                print(text, end="", flush=True)
                received_text = True

            def show_event(event):
                nonlocal line_open
                if event.type != "run_item_stream_event" or event.name not in {"tool_called", "tool_output"}:
                    return
                if line_open:
                    print()
                    line_open = False
                item = event.item
                if event.name == "tool_called":
                    name = item.tool_name or "tool"
                    tool_names[item.call_id] = name
                    raw = item.raw_item
                    arguments = raw.get("arguments", "") if isinstance(raw, dict) else getattr(raw, "arguments", "")
                    print(f"[tool call] {name} {arguments}", flush=True)
                else:
                    name = tool_names.get(item.call_id, "tool")
                    print(f"[tool result received] {name}", flush=True)

            try:
                outcome = await agent.ask(session_id, question, on_text=show_text,
                                          on_event=show_event if verbose else None)
            except ValidationError:
                print("Enter a message between 1 and 8000 characters.")
                continue
            if line_open:
                print()
            if outcome.error:
                print(f"Error: {outcome.error['message']}")
                if verbose and outcome.error.get("detail"):
                    print(outcome.error["detail"])
            elif not received_text and outcome.answer:
                print(f"Assistant: {outcome.answer}")
    finally:
        await agent.close()


def main():
    parser = argparse.ArgumentParser(description="Niural streaming terminal chat; settings come from .env.")
    parser.add_argument("--verbose", action="store_true", help="Show model, tool events and error details.")
    args = parser.parse_args()
    try:
        asyncio.run(chat(verbose=args.verbose))
    except KeyboardInterrupt:
        print("\nChat closed.")
    except ValidationError:
        print("Invalid configuration. Check .env.", file=sys.stderr)
        return 1
    except (FileNotFoundError, ValueError) as error:
        print(f"Setup error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
