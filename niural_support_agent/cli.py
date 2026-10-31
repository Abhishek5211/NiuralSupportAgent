"""Small terminal adapter for the preserved raw-tool baseline."""
import argparse
import asyncio
from .agent import SupportAgent
from .config import Config


async def chat():
    agent = SupportAgent(Config.load())
    try:
        print("Baseline chat. /reset clears history; /quit exits.")
        while True:
            try:
                question = input("You: ").strip()
            except EOFError:
                break
            if question == "/quit":
                break
            if question == "/reset":
                agent.reset("cli-chat")
                continue
            if not question:
                continue
            print("Assistant: ", end="", flush=True)
            result = await agent.ask("cli-chat", question, on_text=lambda text: print(text, end="", flush=True))
            if result.error:
                print(result.error["message"], end="")
            print()
    finally:
        await agent.close()


def main():
    argparse.ArgumentParser(description="Preserved Niural raw-tool baseline").parse_args()
    try:
        asyncio.run(chat())
    except KeyboardInterrupt:
        print("\nChat closed.")
    return 0
