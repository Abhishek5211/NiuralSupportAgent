import os
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field

from mock_api.auth import EMPLOYER_ID
from mock_api.models import SNAPSHOT_DATE


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
BENCHMARK_DIR = PROJECT_DIR / "benchmark"
MOCK_DIR = PROJECT_DIR / "mock_api"
TODAY = SNAPSHOT_DATE.isoformat()


class Config(BaseModel):
    model_config = ConfigDict(frozen=True)
    api_key: str = Field(default="", repr=False, exclude=True)
    provider: Literal["groq", "openai"] = "groq"
    model: str = "openai/gpt-oss-120b"
    judge_model: str = "openai/gpt-oss-120b"
    mock_token: str = Field(default="local-admin", repr=False, exclude=True)
    max_turns: int = Field(default=4, ge=1)
    turn_timeout: int = Field(default=120, ge=1)

    @property
    def base_url(self):
        if self.provider == "groq":
            return "https://api.groq.com/openai/v1"
        if self.provider == "openai":
            return "https://api.openai.com/v1"
        raise ValueError("MODEL_PROVIDER must be groq or openai")

    @classmethod
    def load(cls):
        # Local configuration is optional; process environment takes precedence.
        values = {**dotenv_values(MOCK_DIR / ".env"),
                  **dotenv_values(PROJECT_DIR / ".env"),
                  **dotenv_values(PACKAGE_DIR / ".env"), **os.environ}
        provider = values.get("MODEL_PROVIDER", "groq")
        default_model = "openai/gpt-oss-120b" if provider == "groq" else "gpt-4.1-mini-2025-04-14"
        return cls(provider=provider,
                   api_key=values.get("GROQ_API_KEY" if provider == "groq" else "OPENAI_API_KEY") or "",
                   model=values.get("AGENT_MODEL") or default_model,
                   judge_model=values.get("JUDGE_MODEL") or default_model,
                   mock_token=values.get("NIURAL_MOCK_TOKEN", "local-admin"))
