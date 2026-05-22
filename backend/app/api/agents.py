from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.entities import Agent as AgentModel
from app.schemas.contract import Agent, AgentCreate, AgentUpdate, Model, Tool

router = APIRouter(prefix="/agents", tags=["agents"])


TOOLS = [
    Tool(name="web_search", description="Search the web for current public information.", params_schema={"query": "string"}),
    Tool(name="order_lookup", description="Look up order status by order ID.", params_schema={"order_id": "string"}),
    Tool(name="send_email", description="Send an email through a configured mail provider.", params_schema={"to": "string", "subject": "string", "body": "string"}),
    Tool(name="calculator", description="Evaluate a deterministic arithmetic expression.", params_schema={"expression": "string"}),
]

MODELS = [
    Model(id="claude-sonnet-4-6", provider="anthropic", display_name="Claude Sonnet 4.6", input_cost_per_1k=0.003, output_cost_per_1k=0.015),
    Model(id="gpt-4o", provider="openai", display_name="GPT-4o", input_cost_per_1k=0.005, output_cost_per_1k=0.015),
    Model(id="gemini-2.0-flash", provider="google", display_name="Gemini 2.0 Flash", input_cost_per_1k=0.0001, output_cost_per_1k=0.0004),
]


@router.get("/tools", response_model=list[Tool])
async def list_tools() -> list[Tool]:
    return TOOLS


@router.get("/models", response_model=list[Model])
async def list_models() -> list[Model]:
    return MODELS


@router.post("", response_model=Agent, status_code=status.HTTP_201_CREATED)
async def create_agent(payload: AgentCreate, db: AsyncSession = Depends(get_db)) -> AgentModel:
    agent = AgentModel(**payload.model_dump())
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("", response_model=list[Agent])
async def list_agents(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[AgentModel]:
    result = await db.execute(select(AgentModel).offset(offset).limit(limit).order_by(AgentModel.created_at))
    return list(result.scalars())


@router.get("/{agent_id}", response_model=Agent)
async def get_agent(agent_id: UUID, db: AsyncSession = Depends(get_db)) -> AgentModel:
    agent = await db.get(AgentModel, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.patch("/{agent_id}", response_model=Agent)
async def update_agent(agent_id: UUID, payload: AgentUpdate, db: AsyncSession = Depends(get_db)) -> AgentModel:
    agent = await db.get(AgentModel, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(agent, key, value)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    agent = await db.get(AgentModel, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.commit()
