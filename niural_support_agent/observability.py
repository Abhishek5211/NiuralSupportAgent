"""Opt-in LangSmith export for the OpenAI Agents SDK."""

from .config import Config
from .runtime import git_metadata


def configure_langsmith(config: Config):
    if not config.langsmith_tracing:
        return None
    if not config.langsmith_api_key:
        raise ValueError("Set LANGSMITH_API_KEY in .env to enable tracing.")

    from agents import set_trace_processors, set_tracing_disabled
    from langsmith import Client
    from langsmith.integrations.openai_agents_sdk import OpenAIAgentsTracingProcessor

    client = Client(
        api_key=config.langsmith_api_key,
        api_url=config.langsmith_endpoint,
        workspace_id=config.langsmith_workspace_id or "",
    )
    # Replace the default exporter: traces go to LangSmith only.
    set_trace_processors([OpenAIAgentsTracingProcessor(
        client=client, project_name=config.langsmith_project, metadata={"implementation": "account-tools", **git_metadata()},
    )])
    set_tracing_disabled(False)
    return client
