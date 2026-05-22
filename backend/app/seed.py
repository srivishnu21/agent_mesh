from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Agent, Workflow


async def seed_if_empty(db: AsyncSession) -> None:
    count = await db.scalar(select(func.count()).select_from(Agent))
    if count:
        return

    triage = Agent(
        name="Triage Agent",
        role="Classifies incoming customer messages",
        system_prompt="Classify the customer request and decide the best next handler.",
        model="claude-sonnet-4-6",
        tools=[],
        config={"temperature": 0.2, "memory_enabled": True, "guardrails": {"pii": "redact"}},
        channels=["telegram", "internal"],
    )
    specialist = Agent(
        name="Support Specialist",
        role="Answers customer questions",
        system_prompt="Resolve customer questions using approved tools and concise explanations.",
        model="gpt-4o",
        tools=["web_search", "order_lookup"],
        config={"temperature": 0.3, "memory_enabled": True, "max_tokens": 1200},
        channels=["internal"],
    )
    researcher = Agent(
        name="Researcher Agent",
        role="Finds source material for research tasks",
        system_prompt="Gather relevant facts and cite the source names in notes.",
        model="gemini-2.0-flash",
        tools=["web_search"],
        config={"temperature": 0.1, "memory_enabled": False},
        channels=["internal"],
    )
    summarizer = Agent(
        name="Summarizer Agent",
        role="Turns research notes into concise summaries",
        system_prompt="Summarize research notes into crisp, reviewer-friendly output.",
        model="claude-sonnet-4-6",
        tools=[],
        config={"temperature": 0.2, "memory_enabled": False},
        channels=["internal"],
    )
    db.add_all([triage, specialist, researcher, summarizer])
    await db.flush()

    db.add_all(
        [
            Workflow(
                name="Customer Support Triage",
                description="Triage incoming customer requests, route to a specialist, and prepare a reply.",
                is_template=True,
                graph={
                    "nodes": [
                        {"id": "triage", "agent_id": str(triage.id), "position": {"x": 80, "y": 120}, "config": {}},
                        {"id": "specialist", "agent_id": str(specialist.id), "position": {"x": 360, "y": 120}, "config": {}},
                        {"id": "reply", "agent_id": str(specialist.id), "position": {"x": 640, "y": 120}, "config": {"mode": "final_reply"}},
                    ],
                    "edges": [
                        {"from": "triage", "to": "specialist", "condition": "needs_answer"},
                        {"from": "specialist", "to": "reply"},
                    ],
                },
            ),
            Workflow(
                name="Research & Summarize",
                description="Research a topic, summarize findings, and produce a final answer.",
                is_template=True,
                graph={
                    "nodes": [
                        {"id": "research", "agent_id": str(researcher.id), "position": {"x": 80, "y": 180}, "config": {}},
                        {"id": "summarize", "agent_id": str(summarizer.id), "position": {"x": 380, "y": 180}, "config": {}},
                        {"id": "output", "agent_id": str(summarizer.id), "position": {"x": 680, "y": 180}, "config": {"format": "brief"}},
                    ],
                    "edges": [
                        {"from": "research", "to": "summarize"},
                        {"from": "summarize", "to": "output"},
                    ],
                },
            ),
        ]
    )
    await db.commit()
