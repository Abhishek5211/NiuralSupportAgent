from pydantic import BaseModel, ConfigDict, Field, StrictBool


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=8000)


class Outcome(BaseModel):
    answer: str | None = None
    error: dict | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    latency_ms: float = 0


class Judgment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    correct: StrictBool
    reason: str
