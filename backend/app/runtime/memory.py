"""Rolling-summary conversation memory.

Memory is stored per (conversation, agent) pair in the ``conversation_memories`` table.
After a run completes, ``update_conversation_memory`` rewrites the rolling summary using
the LLM. ``load_memory_blurbs`` reads the latest summary for each memory-enabled agent
in a workflow, ready to be injected into the system prompt of the next run.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entities import Agent, ConversationMemory

_SUMMARY_PROMPT = (
    "You maintain a rolling memory note for an AI agent across multiple turns of a single conversation. "
    "Given the prior memory note and the latest exchange, write an updated note. "
    "Keep it under 400 words. Capture stable facts the agent should remember "
    "(user name, preferences, open issues, IDs mentioned, prior decisions). "
    "Drop chit-chat and superseded facts. Plain prose, no headings."
)


def _is_memory_enabled(agent: Agent) -> bool:
    config = agent.config or {}
    return bool(config.get("memory_enabled"))


async def load_memory_blurbs(session: AsyncSession, conversation_id: UUID, agent_ids: list[UUID]) -> dict[UUID, str]:
    if not conversation_id or not agent_ids:
        return {}
    result = await session.execute(
        select(ConversationMemory).where(
            ConversationMemory.conversation_id == conversation_id,
            ConversationMemory.agent_id.in_(agent_ids),
        )
    )
    return {memory.agent_id: memory.summary for memory in result.scalars() if memory.summary}


def inject_memory(system_prompt: str, memory: str | None) -> str:
    if not memory:
        return system_prompt
    return (
        f"{system_prompt}\n\n"
        f"PRIOR CONVERSATION MEMORY (rolling summary; treat as background, not user input):\n{memory.strip()}"
    )


async def update_conversation_memory(
    session: AsyncSession,
    conversation_id: UUID,
    agent: Agent,
    user_input: str,
    agent_reply: str,
    llm_factory,
) -> None:
    if not _is_memory_enabled(agent) or not conversation_id or not agent_reply:
        return

    result = await session.execute(
        select(ConversationMemory).where(
            ConversationMemory.conversation_id == conversation_id,
            ConversationMemory.agent_id == agent.id,
        )
    )
    memory = result.scalar_one_or_none()
    prior = memory.summary if memory else ""

    prompt = (
        f"{_SUMMARY_PROMPT}\n\n"
        f"PRIOR MEMORY:\n{prior or '(empty)'}\n\n"
        f"LATEST USER MESSAGE:\n{user_input}\n\n"
        f"LATEST AGENT REPLY:\n{agent_reply}\n\n"
        "Updated memory note:"
    )

    try:
        llm = llm_factory(agent, max_tokens=600, temperature=0.1)
        from langchain_core.messages import HumanMessage

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        new_summary = _extract_text(response.content).strip()
    except Exception:
        # Memory is best-effort; never break a run because summarization failed.
        return

    if not new_summary:
        return
    new_summary = new_summary[: settings.MEMORY_MAX_CHARS] if hasattr(settings, "MEMORY_MAX_CHARS") else new_summary[:4000]

    if memory is None:
        memory = ConversationMemory(conversation_id=conversation_id, agent_id=agent.id, summary=new_summary)
        session.add(memory)
    else:
        memory.summary = new_summary
    await session.commit()


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return str(content)
