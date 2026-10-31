"""Shared runtime and evaluation instructions."""

from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT = (PROMPT_DIR / "system.txt").read_text(encoding="utf-8")
CUSTOMER_STYLE = (PROMPT_DIR / "style.txt").read_text(encoding="utf-8")
CORRECTNESS_PROMPT = (PROMPT_DIR / "correctness.txt").read_text(encoding="utf-8")
