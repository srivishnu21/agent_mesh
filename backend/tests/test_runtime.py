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

from app.db import SessionLocal, engine, init_db  # noqa: E402
from app.config import settings  # noqa: E402
from app.models.entities import Agent, Channel, Conversation, Message, Run, RunEvent, Workflow  # noqa: E402
from app.main import app  # noqa: E402
from app.runtime import errors as runtime_errors  # noqa: E402
from app.runtime import event_emitter, graph_builder  # noqa: E402
from app.integrations import telegram_bot  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def dispose_async_engine_between_tests():
    yield
    anyio.run(engine.dispose)


def test_graph_builder_single_source(monkeypatch) -> None:
    async def noop_node(state):
        return {"messages": []}

    monkeypatch.setattr(graph_builder, "make_agent_node", lambda _agent, _session, memory_blurb=None, **_: noop_node)
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

    monkeypatch.setattr(graph_builder, "make_agent_node", lambda _agent, _session, memory_blurb=None, **_: noop_node)
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

    async def fake_execute_run(run_id, workflow_id, user_input, *, conversation_id=None):
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


def test_pii_guardrail_redacts_email_and_phone() -> None:
    from app.runtime.guardrails import apply_input_guardrails

    outcome = apply_input_guardrails(
        "Email me at alice@example.com or call +1 415 555 9012.",
        {"pii": "redact"},
    )
    assert "alice@example.com" not in outcome.text
    assert "[REDACTED_EMAIL]" in outcome.text
    assert "[REDACTED_PHONE]" in outcome.text
    assert set(outcome.triggered) >= {"EMAIL", "PHONE"}


def test_pii_guardrail_noop_when_disabled() -> None:
    from app.runtime.guardrails import apply_input_guardrails

    outcome = apply_input_guardrails("alice@example.com", None)
    assert outcome.text == "alice@example.com"
    assert outcome.triggered == []


def test_extract_route_parses_route_and_category() -> None:
    assert graph_builder._extract_route("ROUTE: billing\nSUMMARY: ...") == "billing"
    assert graph_builder._extract_route("CATEGORY: technical\n") == "technical"
    assert graph_builder._extract_route("no route here") is None


def test_router_picks_conditional_target_then_falls_back() -> None:
    edges = [
        {"from": "triage", "to": "billing", "condition": {"route_equals": "billing"}},
        {"from": "triage", "to": "technical", "condition": {"route_equals": "technical"}},
        {"from": "triage", "to": "general", "condition": {"always": True}},
    ]
    router, targets = graph_builder._make_router(edges, default_target="general")
    assert router({"route": "billing"}) == "billing"
    assert router({"route": "technical"}) == "technical"
    assert router({"route": "weather"}) == "general"
    assert router({}) == "general"
    assert {"billing", "technical", "general"} <= set(targets)


def test_conditional_workflow_compiles(monkeypatch) -> None:
    async def noop_node(state):
        return {"messages": []}

    monkeypatch.setattr(graph_builder, "make_agent_node", lambda _agent, _session, memory_blurb=None, **_: noop_node)
    triage = Agent(id=uuid4(), name="Triage", role="r", system_prompt="p", model="test", tools=[], config={}, channels=[])
    billing = Agent(id=uuid4(), name="Billing", role="r", system_prompt="p", model="test", tools=[], config={}, channels=[])
    technical = Agent(id=uuid4(), name="Tech", role="r", system_prompt="p", model="test", tools=[], config={}, channels=[])
    general = Agent(id=uuid4(), name="General", role="r", system_prompt="p", model="test", tools=[], config={}, channels=[])
    workflow = SimpleNamespace(
        graph={
            "nodes": [
                {"id": "t", "agent_id": str(triage.id)},
                {"id": "b", "agent_id": str(billing.id)},
                {"id": "tech", "agent_id": str(technical.id)},
                {"id": "g", "agent_id": str(general.id)},
            ],
            "edges": [
                {"from": "t", "to": "b", "condition": {"route_equals": "billing"}},
                {"from": "t", "to": "tech", "condition": {"route_equals": "technical"}},
                {"from": "t", "to": "g", "condition": {"always": True}},
            ],
        }
    )
    agents = {a.id: a for a in (triage, billing, technical, general)}
    compiled = anyio.run(graph_builder.build_graph_from_workflow, workflow, agents, None)
    assert compiled is not None


def test_router_resolves_END_alias() -> None:
    from langgraph.graph import END

    edges = [
        {"from": "reviewer", "to": "drafter", "condition": {"route_equals": "revise"}},
        {"from": "reviewer", "to": "END", "condition": {"always": True}},
    ]
    router, routing_map = graph_builder._make_router(edges, default_target="drafter")
    assert router({"route": "revise"}) == "drafter"
    assert router({"route": "approve"}) is END
    assert router({}) is END
    assert routing_map[END] is END
    assert routing_map["drafter"] == "drafter"


def test_feedback_loop_workflow_compiles(monkeypatch) -> None:
    async def noop_node(state):
        return {"messages": []}

    monkeypatch.setattr(graph_builder, "make_agent_node", lambda _agent, _session, memory_blurb=None, **_: noop_node)
    drafter = Agent(id=uuid4(), name="Drafter", role="r", system_prompt="p", model="test", tools=[], config={}, channels=[])
    reviewer = Agent(id=uuid4(), name="Reviewer", role="r", system_prompt="p", model="test", tools=[], config={}, channels=[])
    workflow = SimpleNamespace(
        graph={
            "nodes": [
                {"id": "drafter", "agent_id": str(drafter.id)},
                {"id": "reviewer", "agent_id": str(reviewer.id)},
            ],
            "edges": [
                {"from": "drafter", "to": "reviewer"},
                {"from": "reviewer", "to": "drafter", "condition": {"route_equals": "revise"}},
                {"from": "reviewer", "to": "END", "condition": {"always": True}},
            ],
        }
    )
    agents = {a.id: a for a in (drafter, reviewer)}
    compiled = anyio.run(graph_builder.build_graph_from_workflow, workflow, agents, None)
    assert compiled is not None


def test_workflow_interaction_rules_passed_to_agent_node(monkeypatch) -> None:
    """build_graph_from_workflow forwards graph.config.interaction_rules.max_iterations_per_agent."""
    captured: dict = {}

    async def noop_node(state):
        return {"messages": []}

    def fake_make_agent_node(_agent, _session, memory_blurb=None, *, max_iterations: int = 3):
        captured["max_iterations"] = max_iterations
        return noop_node

    monkeypatch.setattr(graph_builder, "make_agent_node", fake_make_agent_node)
    agent = Agent(id=uuid4(), name="A", role="r", system_prompt="p", model="test", tools=[], config={}, channels=[])
    workflow = SimpleNamespace(
        graph={
            "nodes": [{"id": "n1", "agent_id": str(agent.id)}],
            "edges": [],
            "config": {"interaction_rules": {"max_iterations_per_agent": 7, "max_total_steps": 50}},
        }
    )
    anyio.run(graph_builder.build_graph_from_workflow, workflow, {agent.id: agent}, None)
    assert captured["max_iterations"] == 7


def test_scheduler_extract_schedule_skips_when_disabled() -> None:
    from app.scheduler import _extract_schedule

    wf_off = SimpleNamespace(graph={"config": {"schedule": {"enabled": False, "cron": "0 9 * * *"}}})
    wf_no_cron = SimpleNamespace(graph={"config": {"schedule": {"enabled": True, "cron": ""}}})
    wf_on = SimpleNamespace(graph={"config": {"schedule": {"enabled": True, "cron": "0 9 * * *", "input": "x"}}})

    assert _extract_schedule(wf_off) is None
    assert _extract_schedule(wf_no_cron) is None
    schedule = _extract_schedule(wf_on)
    assert schedule and schedule["cron"] == "0 9 * * *" and schedule["input"] == "x"


def test_memory_injection_appends_summary_to_system_prompt() -> None:
    from app.runtime.memory import inject_memory

    prompt = inject_memory("BASE PROMPT", "user prefers concise replies")
    assert "BASE PROMPT" in prompt
    assert "user prefers concise replies" in prompt
    assert inject_memory("BASE", None) == "BASE"


def test_telegram_per_chat_workflow_selection_overrides_default(monkeypatch) -> None:
    from app.integrations import telegram_bot

    async def scenario() -> None:
        await init_db()
        async with SessionLocal() as session:
            agent = Agent(
                name=f"TG Agent {uuid4()}",
                role="r",
                system_prompt="p",
                model="test",
                tools=[],
                config={},
                channels=["telegram"],
            )
            session.add(agent)
            await session.flush()
            default_wf = Workflow(
                name=f"Default WF {uuid4()}",
                description="default",
                graph={"nodes": [{"id": "a", "agent_id": str(agent.id)}], "edges": []},
                is_template=False,
            )
            chosen_wf = Workflow(
                name=f"Chosen WF {uuid4()}",
                description="chosen",
                graph={"nodes": [{"id": "a", "agent_id": str(agent.id)}], "edges": []},
                is_template=False,
            )
            session.add_all([default_wf, chosen_wf])
            await session.commit()

            object.__setattr__(settings, "TELEGRAM_DEFAULT_WORKFLOW_ID", str(default_wf.id))

            wf_unknown, source_unknown = await telegram_bot.get_current_workflow("unknown-chat")
            assert wf_unknown.id == default_wf.id
            assert source_unknown == "default"

            await telegram_bot.set_workflow_for_chat("chat-xyz", chosen_wf.id)
            wf_chat, source_chat = await telegram_bot.get_current_workflow("chat-xyz")
            assert wf_chat.id == chosen_wf.id
            assert source_chat == "chat"

    anyio.run(scenario)


def test_classify_recursion_limit_via_GraphRecursionError() -> None:
    if runtime_errors.GraphRecursionError is None:
        pytest.skip("langgraph not exposing GraphRecursionError in this version")
    exc = runtime_errors.GraphRecursionError("Recursion limit of 25 reached")
    result = runtime_errors.classify(exc)
    assert result.category == "recursion_limit"
    assert "25" in result.message or "recursion" in result.message.lower()


def test_classify_recursion_limit_via_message() -> None:
    exc = RuntimeError("graph hit recursion limit during execution")
    result = runtime_errors.classify(exc)
    assert result.category == "recursion_limit"


def test_classify_token_limit() -> None:
    exc = Exception("This model's maximum context length is 8192 tokens, however you requested 9000.")
    result = runtime_errors.classify(exc)
    assert result.category == "token_limit"
    assert "context" in result.message.lower()


def test_classify_rate_limit() -> None:
    exc = Exception("429 Too Many Requests: rate_limit_exceeded")
    result = runtime_errors.classify(exc)
    assert result.category == "rate_limit"
    assert result.retriable is True


def test_classify_auth_error_by_name() -> None:
    class AuthenticationError(Exception):
        pass

    exc = AuthenticationError("Invalid credentials")
    result = runtime_errors.classify(exc)
    assert result.category == "auth"


def test_classify_timeout() -> None:
    exc = TimeoutError("Request timed out after 60s")
    result = runtime_errors.classify(exc)
    assert result.category == "timeout"
    assert result.retriable is True


def test_classify_graph_invalid() -> None:
    exc = ValueError("Workflow has no nodes")
    result = runtime_errors.classify(exc)
    assert result.category == "graph_invalid"


def test_classify_unknown_falls_through() -> None:
    exc = Exception("Some unexpected failure")
    result = runtime_errors.classify(exc)
    assert result.category == "unknown"
    assert "Some unexpected failure" in result.message


def test_classified_error_payload_shape() -> None:
    exc = Exception("rate limit hit")
    payload = runtime_errors.classify(exc).to_payload()
    assert set(payload.keys()) == {"category", "message", "hint", "retriable"}


@pytest.mark.integration
def test_run_completes_end_to_end() -> None:
    if os.environ.get("RUN_LIVE_LLM_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_LLM_TESTS=1 to run this integration test")

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
