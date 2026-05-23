from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from langchain_core.messages import HumanMessage
from sqlalchemy import select

from app.db import async_session_factory
from app.models.entities import Agent, Run, RunEvent, RunStatus, Workflow
from app.runtime.event_emitter import emit
from app.runtime.graph_builder import build_graph_from_workflow


async def execute_run(run_id: UUID, workflow_id: UUID, user_input: str) -> None:
    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        workflow = await session.get(Workflow, workflow_id)
        if not run or not workflow:
            return

        try:
            agent_ids = [UUID(node["agent_id"]) for node in workflow.graph.get("nodes", [])]
            result = await session.execute(select(Agent).where(Agent.id.in_(agent_ids)))
            agents_by_id = {agent.id: agent for agent in result.scalars().all()}

            run.status = RunStatus.running
            run.started_at = datetime.now(timezone.utc)
            await session.commit()

            await emit(session, run_id, "run_started", {"workflow_name": workflow.name, "input": user_input})
            graph = await build_graph_from_workflow(workflow, agents_by_id, session)
            final_state = await graph.ainvoke(
                {
                    "messages": [HumanMessage(content=user_input)],
                    "scratchpad": {},
                    "run_id": str(run_id),
                    "workflow_id": str(workflow_id),
                },
                {"recursion_limit": 25},
            )

            events = (
                await session.execute(select(RunEvent).where(RunEvent.run_id == run_id))
            ).scalars().all()
            run.total_tokens = sum(event.tokens for event in events)
            run.total_cost_usd = sum((event.cost_usd for event in events), Decimal("0"))
            run.status = RunStatus.completed
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()

            final_message = final_state["messages"][-1].content if final_state.get("messages") else ""
            await emit(session, run_id, "run_completed", {"final_message": str(final_message)[:2000]})
        except Exception as exc:
            run.status = RunStatus.failed
            run.error = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            await emit(session, run_id, "error", {"message": str(exc)})
