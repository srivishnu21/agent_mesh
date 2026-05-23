import os
import time
from types import SimpleNamespace
from uuid import uuid4

import anyio
import pytest
from sqlalchemy import select

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("REQUIRE_ANTHROPIC_ON_STARTUP", "false")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "")
os.environ.setdefault("TELEGRAM_MODE", "polling")

from app.db import SessionLocal, init_db  # noqa: E402
from app.config import settings  # noqa: E402
from app.models.entities import Agent, Channel, Conversation, Message, Run, RunEvent, Workflow  # noqa: E402
from app.main import app  # noqa: E402
from app.runtime import event_emitter, graph_builder  # noqa: E402
from app.integrations import telegram_bot  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def test_graph_builder_single_source(monkeypatch) -> None:
    async def noop_node(state):
        return {"messages": []}

    monkeypatch.setattr(graph_builder, "make_agent_node", lambda _agent, _session: noop_node)
    first = Agent(id=uuid4(), name="A", role="A", system_prompt="A", model="test", tools=[], config={}, channels=[])
    second = Agent(id=uuid4(), name="B", role="B", system_prompt="B", model="test", tools=[], config={}, channels=[])
    workflow = SimpleNamespace(
        graph={
            "nodes": [{"id": "a", "agent_id": str(first.id)}, {"id": "b", "agent_id": str(second.id)}],
            "edges": [{"from": "a", "to": "b"}],
        }
    )
    compiled = anyio.run(graph_builder.build_graph_from_workflow, workflow, {first.id: first, second.id: second}, None)
    assert compiled is not None


def test_graph_builder_rejects_multiple_sources(monkeypatch) -> None:
    async def noop_node(state):
        return {"messages": []}

    monkeypatch.setattr(graph_builder, "make_agent_node", lambda _agent, _session: noop_node)
    first = Agent(id=uuid4(), name="A", role="A", system_prompt="A", model="test", tools=[], config={}, channels=[])
    second = Agent(id=uuid4(), name="B", role="B", system_prompt="B", model="test", tools=[], config={}, channels=[])
    workflow = SimpleNamespace(
        graph={
            "nodes": [{"id": "a", "agent_id": str(first.id)}, {"id": "b", "agent_id": str(second.id)}],
            "edges": [],
        }
    )
    with pytest.raises(ValueError):
        anyio.run(graph_builder.build_graph_from_workflow, workflow, {first.id: first, second.id: second}, None)


def test_event_emitter_writes_row_and_broadcasts(monkeypatch) -> None:
    calls = []

    async def fake_broadcast(run_id: str, message: dict) -> None:
        calls.append((run_id, message))

    monkeypatch.setattr(event_emitter.ws_manager, "broadcast", fake_broadcast)

    async def scenario() -> None:
        await init_db()
        async with SessionLocal() as session:
            workflow = Workflow(name=f"Emitter {uuid4()}", description="Emitter test", graph={"nodes": [], "edges": []})
            session.add(workflow)
            await session.flush()
            run = Run(workflow_id=workflow.id, trigger={"source": "test"})
            session.add(run)
            await session.commit()
            await session.refresh(run)

            await event_emitter.emit(session, run.id, "run_started", {"ok": True})
            rows = (await session.execute(select(RunEvent).where(RunEvent.run_id == run.id))).scalars().all()
            assert len(rows) == 1
            assert calls
            assert calls[0][0] == str(run.id)
            assert calls[0][1]["event_type"] == "run_started"

    anyio.run(scenario)


def test_telegram_incoming_message_creates_conversation_run_and_reply(monkeypatch) -> None:
    sent_messages = []

    class FakeBot:
        async def send_message(self, chat_id: str, text: str) -> None:
            sent_messages.append((chat_id, text))

        async def send_chat_action(self, chat_id: str, action: str) -> None:
            sent_messages.append((chat_id, action))

    async def fake_execute_run(run_id, workflow_id, user_input):
        async with SessionLocal() as session:
            await event_emitter.emit(session, run_id, "agent_message", {"agent_name": "Test", "content": "Hello from agent"})

    async def scenario() -> None:
        await init_db()
        async with SessionLocal() as session:
            agent = Agent(
                name=f"Telegram Agent {uuid4()}",
                role="Telegram test agent",
                system_prompt="Reply",
                model="test",
                tools=[],
                config={},
                channels=["telegram"],
            )
            session.add(agent)
            await session.flush()
            workflow = Workflow(
                name=f"Telegram Workflow {uuid4()}",
                description="Telegram test workflow",
                graph={"nodes": [{"id": "agent", "agent_id": str(agent.id)}], "edges": []},
                is_template=False,
            )
            session.add(workflow)
            await session.commit()

            object.__setattr__(settings, "TELEGRAM_DEFAULT_WORKFLOW_ID", str(workflow.id))
            monkeypatch.setattr(telegram_bot, "get_bot", lambda: FakeBot())
            monkeypatch.setattr(telegram_bot, "execute_run", fake_execute_run)

            await telegram_bot.handle_incoming_message("chat-42", "hello", {"username": "tester"})

            conversations = (
                await session.execute(select(Conversation).where(Conversation.channel == Channel.telegram, Conversation.external_id == "chat-42"))
            ).scalars().all()
            assert len(conversations) == 1
            messages = (
                await session.execute(select(Message).where(Message.conversation_id == conversations[0].id).order_by(Message.created_at))
            ).scalars().all()
            assert [message.role for message in messages] == ["user", "agent"]
            runs = (await session.execute(select(Run).where(Run.workflow_id == workflow.id))).scalars().all()
            assert len(runs) == 1
            assert sent_messages[-1] == ("chat-42", "Hello from agent")

    anyio.run(scenario)


@pytest.mark.integration
def test_run_completes_end_to_end() -> None:
    if os.environ.get("ANTHROPIC_API_KEY", "").startswith("test"):
        pytest.skip("Set a real ANTHROPIC_API_KEY to run this integration test")

    with TestClient(app) as client:
        workflows = client.get("/api/v1/workflows?is_template=true").json()
        workflow = next(item for item in workflows if "Triage" in item["name"])
        response = client.post(
            f"/api/v1/workflows/{workflow['id']}/run",
            json={"input": "Where is my order ORD-1042?"},
        )
        run_id = response.json()["run_id"]

        run = None
        for _ in range(60):
            run = client.get(f"/api/v1/runs/{run_id}").json()
            if run["status"] in ("completed", "failed"):
                break
            time.sleep(1)

        assert run is not None
        assert run["status"] == "completed"
        events = client.get(f"/api/v1/runs/{run_id}/events").json()
        event_types = {event["event_type"] for event in events}
        assert "run_started" in event_types
        assert "node_started" in event_types
        assert "tool_call" in event_types
        assert "tool_result" in event_types
        assert "agent_message" in event_types
        assert "run_completed" in event_types
        assert run["total_tokens"] > 0
        assert float(run["total_cost_usd"]) > 0
