from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from langchain_core.messages import HumanMessage
from sqlalchemy import select

from app.db import async_session_factory
from app.models.entities import Agent, Run, RunEvent, RunEventType, RunStatus, Workflow
from app.runtime.errors import classify
from app.runtime.event_emitter import emit
from app.runtime.graph_builder import build_graph_from_workflow, make_chat_model
from app.runtime.memory import update_conversation_memory


def _message_content_text(content) -> str:
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
                elif isinstance(text, dict) and isinstance(text.get("value"), str):
                    parts.append(text["value"])
        return "\n".join(part for part in parts if part).strip()
    if isinstance(content, dict):
        text = content.get("text") or content.get("content")
        if isinstance(text, str):
            return text
    return str(content)


async def execute_run(
    run_id: UUID,
    workflow_id: UUID,
    user_input: str,
    *,
    conversation_id: UUID | None = None,
) -> None:
    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        workflow = await session.get(Workflow, workflow_id)
        if not run or not workflow:
            return

        if conversation_id is None:
            trigger_conv = (run.trigger or {}).get("payload", {}).get("conversation_id")
            if trigger_conv:
                try:
                    conversation_id = UUID(trigger_conv)
                except (ValueError, TypeError):
                    conversation_id = None

        try:
            agent_ids = [UUID(node["agent_id"]) for node in workflow.graph.get("nodes", [])]
            result = await session.execute(select(Agent).where(Agent.id.in_(agent_ids)))
            agents_by_id = {agent.id: agent for agent in result.scalars().all()}

            run.status = RunStatus.running
            run.started_at = datetime.now(timezone.utc)
            await session.commit()

            await emit(session, run_id, "run_started", {"workflow_name": workflow.name, "input": user_input})
            graph = await build_graph_from_workflow(
                workflow, agents_by_id, session, conversation_id=conversation_id
            )
            invocation_state = {
                "messages": [HumanMessage(content=user_input)],
                "scratchpad": {},
                "run_id": str(run_id),
                "workflow_id": str(workflow_id),
            }
            if conversation_id is not None:
                invocation_state["conversation_id"] = str(conversation_id)
            final_state = await graph.ainvoke(invocation_state, {"recursion_limit": 25})

            events = (
                await session.execute(select(RunEvent).where(RunEvent.run_id == run_id))
            ).scalars().all()
            run.total_tokens = sum(event.tokens for event in events)
            run.total_cost_usd = sum((event.cost_usd for event in events), Decimal("0"))
            run.status = RunStatus.completed
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()

            final_message = _message_content_text(final_state["messages"][-1].content) if final_state.get("messages") else ""
            await emit(session, run_id, "run_completed", {"final_message": final_message[:2000]})

            if conversation_id is not None and final_message:
                last_agent = await _last_speaking_agent(session, run_id, agents_by_id)
                if last_agent is not None:
                    await update_conversation_memory(
                        session,
                        conversation_id,
                        last_agent,
                        user_input,
                        final_message,
                        make_chat_model,
                    )
                    await emit(
                        session,
                        run_id,
                        "memory_updated",
                        {"agent_name": last_agent.name, "conversation_id": str(conversation_id)},
                        agent_id=last_agent.id,
                    )
        except Exception as exc:
            classified = classify(exc)
            run.status = RunStatus.failed
            run.error = f"[{classified.category}] {classified.message}"
            run.completed_at = datetime.now(timezone.utc)
            # Best-effort: tally tokens accumulated before the failure so the run page still shows usage.
            try:
                partial_events = (
                    await session.execute(select(RunEvent).where(RunEvent.run_id == run_id))
                ).scalars().all()
                run.total_tokens = sum(event.tokens for event in partial_events)
                run.total_cost_usd = sum((event.cost_usd for event in partial_events), Decimal("0"))
            except Exception:
                pass
            await session.commit()
            await emit(session, run_id, "error", classified.to_payload())


async def _last_speaking_agent(session, run_id: UUID, agents_by_id: dict[UUID, Agent]) -> Agent | None:
    result = await session.execute(
        select(RunEvent)
        .where(RunEvent.run_id == run_id, RunEvent.event_type == RunEventType.agent_message)
        .order_by(RunEvent.created_at.desc())
        .limit(1)
    )
    event = result.scalar_one_or_none()
    if event and event.agent_id and event.agent_id in agents_by_id:
        return agents_by_id[event.agent_id]
    return None
