from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.rag.grounded import GroundedResponse


class CreateSessionRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    provider: str | None
    model: str | None
    source_metadata: dict | None
    created_at: datetime


class SessionResponse(BaseModel):
    id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse]


class ChatRequest(BaseModel):
    session_id: UUID
    message: str = Field(min_length=1, max_length=20_000)
    provider: Literal["ollama", "cloud", "openai"] | None = None


class Ship30Request(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    provider: Literal["ollama", "cloud", "openai"] | None = None


class Ship30Response(BaseModel):
    markdown: str
    word_count: int
    sources: list[dict]
    provider: str
    model: str


class ChatDoneEvent(BaseModel):
    response: GroundedResponse


class DependencyStatus(BaseModel):
    status: str
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    database: DependencyStatus
    ollama: DependencyStatus
    vector_index: DependencyStatus
