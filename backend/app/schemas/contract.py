from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.entities import Channel, MessageRole, RunEventType, RunStatus


JsonDict = dict[str, Any]


class AgentBase(BaseModel):
    name: str
    role: str
    system_prompt: str
    model: str
    tools: list[str] = Field(default_factory=list)
    config: JsonDict = Field(default_factory=dict)
    channels: list[str] = Field(default_factory=list)


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    tools: list[str] | None = None
    config: JsonDict | None = None
    channels: list[str] | None = None


class Agent(AgentBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class Tool(BaseModel):
    name: str
    description: str
    params_schema: JsonDict


class Model(BaseModel):
    id: str
    provider: str
    display_name: str
    input_cost_per_1k: Decimal
    output_cost_per_1k: Decimal


class WorkflowBase(BaseModel):
    name: str
    description: str
    graph: JsonDict = Field(default_factory=dict)
    is_template: bool = False


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    graph: JsonDict | None = None
    is_template: bool | None = None


class Workflow(WorkflowBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class RunCreate(BaseModel):
    input: str | None = None
    trigger: JsonDict = Field(default_factory=dict)


class RunTriggerResponse(BaseModel):
    run_id: UUID


class Run(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: UUID
    status: RunStatus
    trigger: JsonDict
    started_at: datetime | None
    completed_at: datetime | None
    total_tokens: int
    total_cost_usd: Decimal
    error: str | None


class RunEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    agent_id: UUID | None
    event_type: RunEventType
    payload: JsonDict
    tokens: int
    cost_usd: Decimal
    created_at: datetime


class RunDetail(Run):
    events: list[RunEvent] = Field(default_factory=list)


class Conversation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel: Channel
    external_id: str
    agent_id: UUID
    created_at: datetime
    updated_at: datetime


class ConversationSummary(Conversation):
    last_message_preview: str | None = None
    last_message_at: datetime | None = None
    message_count: int = 0
    telegram_user: JsonDict | None = None


class Message(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    metadata: JsonDict = Field(default_factory=dict, validation_alias="metadata_")
    created_at: datetime


class ConversationDetail(Conversation):
    messages: list[Message] = Field(default_factory=list)


class Health(BaseModel):
    status: str
    db: str


class TelegramWebhookResponse(BaseModel):
    ok: bool
    conversation_id: UUID | None = None
    message_id: UUID | None = None


class DashboardRecentRun(BaseModel):
    id: UUID
    workflow_id: UUID
    workflow_name: str
    status: RunStatus
    started_at: datetime | None
    total_tokens: int
    total_cost_usd: Decimal


class DashboardStats(BaseModel):
    agents: int
    workflows: int
    runs_today: int
    tokens_today: int
    recent_runs: list[DashboardRecentRun] = Field(default_factory=list)
