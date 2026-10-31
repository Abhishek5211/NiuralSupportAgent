from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field

from mock_api.auth import EMPLOYER_ID


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
BENCHMARK_DIR = PROJECT_DIR / "benchmark"


class Config(BaseModel):
    model_config = ConfigDict(frozen=True)
    api_key: str = Field(default="", repr=False, exclude=True)
    provider: Literal["openai"] = "openai"
    model: str = "gpt-5.4-mini-2026-03-17"
    judge_model: str = "gpt-5.4-2026-03-05"
    mock_token: str = Field(default="local-admin", repr=False, exclude=True)
    max_turns: int = Field(default=15, ge=1)
    turn_timeout: int = Field(default=120, ge=1)
    langsmith_api_key: str = Field(default="", repr=False, exclude=True)
    langsmith_tracing: bool = False
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_project: str = "niural-support-agent"
    langsmith_workspace_id: str | None = None

    @property
    def base_url(self):
        return "https://api.openai.com/v1"

    @classmethod
    def load(cls):
        # No parent files, process-environment overrides or ${ENV} expansion.
        env_path = PROJECT_DIR / ".env"
        if not env_path.is_file():
            raise FileNotFoundError(f"Create {env_path} using .env.example and add OPENAI_API_KEY.")
        values = dotenv_values(env_path, interpolate=False)
        api_key = (values.get("OPENAI_API_KEY") or "").strip()
        if not api_key:
            raise ValueError(f"Set OPENAI_API_KEY in {env_path}.")
        return cls(api_key=api_key,
                   model=values.get("AGENT_MODEL") or cls.model_fields["model"].default,
                   judge_model=values.get("JUDGE_MODEL") or cls.model_fields["judge_model"].default,
                   mock_token=values.get("NIURAL_MOCK_TOKEN", "local-admin"),
                   langsmith_api_key=values.get("LANGSMITH_API_KEY") or "",
                   langsmith_tracing=values.get("LANGSMITH_TRACING") or False,
                   langsmith_endpoint=values.get("LANGSMITH_ENDPOINT") or cls.model_fields["langsmith_endpoint"].default,
                   langsmith_project=values.get("LANGSMITH_PROJECT") or cls.model_fields["langsmith_project"].default,
                   langsmith_workspace_id=values.get("LANGSMITH_WORKSPACE_ID") or None)
