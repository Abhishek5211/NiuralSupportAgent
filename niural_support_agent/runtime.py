"""Shared model settings and safe run metadata for support and evaluation."""

from agents import MaxTurnsExceeded, ModelSettings
from agents.retry import ModelRetrySettings
from openai import APIConnectionError, APIStatusError
from openai.types.shared import Reasoning


def model_settings(model_name: str, effort: str) -> ModelSettings:
    supports_reasoning = model_name.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4"))
    return ModelSettings(
        max_tokens=4096,
        parallel_tool_calls=False,
        temperature=None if supports_reasoning else 0,
        reasoning=Reasoning(effort=effort) if supports_reasoning else None,
        response_include=["reasoning.encrypted_content"] if supports_reasoning else None,
        store=False,
        retry=ModelRetrySettings(max_retries=0),
    )


def usage_dict(result) -> dict[str, int]:
    usage = result.context_wrapper.usage
    return {name: getattr(usage, name, 0) for name in
            ("requests", "input_tokens", "output_tokens", "total_tokens")}


def error_details(error: Exception) -> dict:
    """Return useful errors without including provider payloads or credentials."""
    if isinstance(error, APIStatusError):
        return {
            "type": "model_service_error",
            "http_status": error.status_code,
            "message": f"OpenAI returned HTTP {error.status_code}. Check model access, credentials and quota.",
        }
    if isinstance(error, APIConnectionError):
        return {"type": "connection_error", "message": "The model service could not be reached."}
    if isinstance(error, TimeoutError):
        return {"type": "timeout", "message": "The agent exceeded its time limit."}
    if isinstance(error, MaxTurnsExceeded):
        return {"type": "step_limit", "message": "The agent exceeded its model-turn limit."}
    return {"type": type(error).__name__, "message": "The run failed. Check the model and configuration."}


def git_metadata() -> dict:
    """Identify the checked-out code in LangSmith experiments."""
    import subprocess
    from .config import PROJECT_DIR

    metadata = {}
    for key, args in [("revision_id", ["rev-parse", "HEAD"]),
                      ("branch", ["branch", "--show-current"])]:
        try:
            result = subprocess.run(["git", *args], cwd=PROJECT_DIR,
                                    capture_output=True, text=True, timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0 and result.stdout.strip():
            metadata[key] = result.stdout.strip()
    return metadata
