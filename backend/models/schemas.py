from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ChatMessage(BaseModel):
    role: Role
    content: str


class ChatRequest(BaseModel):
    message: str
    model: str | None = None
    session_id: str | None = None
    system_prompt: str | None = None


class ChatResponse(BaseModel):
    reply: str
    chart_path: str | None = None
    model_used: str
    tokens_used: int = 0


class StreamChunk(BaseModel):
    token: str
    done: bool = False
    chart_path: str | None = None
    tool_call: str | None = None


class FileInfo(BaseModel):
    filename: str
    rows: int
    columns: list[str]
    dtypes: dict[str, str]
    preview: list[dict[str, Any]]
    nulls: dict[str, int]
    numeric_summary: dict[str, Any] | None = None


class UploadResponse(BaseModel):
    session_id: str
    file_info: FileInfo


class ModelInfo(BaseModel):
    name: str
    size: int
    modified_at: str | None = None


class ModelListResponse(BaseModel):
    models: list[ModelInfo]


class ModelSelectRequest(BaseModel):
    model: str


class PromptBase(BaseModel):
    name: str
    content: str
    description: str = ""


class PromptCreate(PromptBase):
    pass


class PromptUpdate(BaseModel):
    name: str | None = None
    content: str | None = None
    description: str | None = None


class Prompt(PromptBase):
    id: str


class PromptListResponse(BaseModel):
    prompts: list[Prompt]


class ChartRequest(BaseModel):
    code: str
    filename: str | None = None


class ChartResponse(BaseModel):
    chart_id: str
    chart_path: str
    html_content: str
