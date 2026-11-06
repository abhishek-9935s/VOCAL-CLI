from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class CommandProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    command: str = Field(min_length=1, max_length=10000)
    explanation: str = Field(min_length=1, max_length=10000)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    target_binary: str = Field(min_length=1, max_length=256)
    requires_sudo: bool
    is_destructive: bool
