import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entities import Agent, Workflow

log = logging.getLogger(__name__)
TELEGRAM_WORKFLOW_ID_PATH = Path(__file__).resolve().parents[1] / ".telegram_workflow_id"

TRIAGE_PROMPT = """You are a customer support triage agent. Your job is to classify the incoming
customer message into exactly one of these categories: billing, technical,
order_status, general. Then briefly restate the customer's core question in
one sentence and recommend whether the next agent (a specialist) should look
up an order or do a web search.

Format your response as:
CATEGORY: <category>
SUMMARY: <one-sentence restatement>
RECOMMENDED_ACTIONS: <comma-separated suggestions>

Do not attempt to answer the customer yourself. The next agent will handle the response."""

SPECIALIST_PROMPT = """You are a customer support specialist. You receive a triaged message containing
a category, a summary of the customer's question, and recommended actions.

You have two tools:
- order_lookup(order_id): retrieve order status, carrier, tracking, items
- web_search(query): search the web for policies, delivery windows, general info

Use tools when needed. Once you have enough information, write a clear, friendly
final response addressed to the customer. Cite specific facts from your tool
results. Keep it under 150 words."""


async def _agent_by_name(db: AsyncSession, name: str) -> Agent | None:
    return (await db.execute(select(Agent).where(Agent.name == name))).scalar_one_or_none()


async def _workflow_by_name(db: AsyncSession, name: str) -> Workflow | None:
    return (await db.execute(select(Workflow).where(Workflow.name == name))).scalar_one_or_none()


async def _upsert_agent(db: AsyncSession, name: str, **values) -> Agent:
    agent = await _agent_by_name(db, name)
    if not agent:
        agent = Agent(name=name, **values)
        db.add(agent)
    else:
        for key, value in values.items():
            setattr(agent, key, value)
    await db.flush()
    return agent


async def _upsert_workflow(db: AsyncSession, name: str, **values) -> Workflow:
    workflow = await _workflow_by_name(db, name)
    if not workflow:
        workflow = Workflow(name=name, **values)
        db.add(workflow)
    else:
        for key, value in values.items():
            setattr(workflow, key, value)
    await db.flush()
    return workflow


async def seed_if_empty(db: AsyncSession) -> None:
    triage = await _upsert_agent(
        db,
        "Triage Agent",
        role="Classifies incoming customer messages",
        system_prompt=TRIAGE_PROMPT,
        model=settings.DEFAULT_MODEL,
        tools=[],
        config={"temperature": 0.2, "memory_enabled": True, "guardrails": {"pii": "redact"}},
        channels=["telegram", "internal"],
    )
    specialist = await _upsert_agent(
        db,
        "Support Specialist",
        role="Answers customer questions",
        system_prompt=SPECIALIST_PROMPT,
        model=settings.DEFAULT_MODEL,
        tools=["web_search", "order_lookup"],
        config={"temperature": 0.3, "memory_enabled": True, "max_tokens": 1200},
        channels=["internal"],
    )
    researcher = await _upsert_agent(
        db,
        "Researcher Agent",
        role="Finds source material for research tasks",
        system_prompt="Gather relevant facts and cite the source names in notes.",
        model=settings.DEFAULT_MODEL,
        tools=[],
        config={"temperature": 0.1, "memory_enabled": False},
        channels=["internal"],
    )
    summarizer = await _upsert_agent(
        db,
        "Summarizer Agent",
        role="Turns research notes into concise summaries",
        system_prompt="Summarize research notes into crisp, reviewer-friendly output.",
        model=settings.DEFAULT_MODEL,
        tools=[],
        config={"temperature": 0.2, "memory_enabled": False},
        channels=["internal"],
    )

    support_workflow = await _upsert_workflow(
        db,
        "Customer Support Triage",
        description="Triage incoming customer requests, route to a specialist, and prepare a reply.",
        is_template=True,
        graph={
            "nodes": [
                {"id": "triage", "agent_id": str(triage.id), "position": {"x": 100, "y": 100}},
                {"id": "specialist", "agent_id": str(specialist.id), "position": {"x": 400, "y": 100}},
            ],
            "edges": [{"from": "triage", "to": "specialist"}],
        },
    )
    await _upsert_workflow(
        db,
        "Research & Summarize",
        description="Research a topic, summarize findings, and produce a final answer.",
        is_template=True,
        graph={
            "nodes": [
                {"id": "research", "agent_id": str(researcher.id), "position": {"x": 100, "y": 180}},
                {"id": "summarize", "agent_id": str(summarizer.id), "position": {"x": 400, "y": 180}},
            ],
            "edges": [{"from": "research", "to": "summarize"}],
        },
    )
    await db.commit()
    TELEGRAM_WORKFLOW_ID_PATH.write_text(str(support_workflow.id), encoding="utf-8")
    log.warning(
        "Telegram default workflow id: %s. Set TELEGRAM_DEFAULT_WORKFLOW_ID=%s in backend/.env for Telegram.",
        support_workflow.id,
        support_workflow.id,
    )
