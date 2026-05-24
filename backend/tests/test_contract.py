import os
from pathlib import Path
from uuid import uuid4

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_contract.db"
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["REQUIRE_ANTHROPIC_ON_STARTUP"] = "false"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_MODE"] = "polling"
os.environ["AUTH_USERNAME"] = ""
os.environ["AUTH_PASSWORD"] = ""
os.environ["AUTH_SECRET"] = ""
Path("test_contract.db").unlink(missing_ok=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_health_and_seed_data_exist() -> None:
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        agents = client.get("/api/v1/agents").json()
        workflows = client.get("/api/v1/workflows?is_template=true").json()
        assert len(agents) >= 2
        assert len(workflows) >= 2


def test_agent_round_trip_and_static_registries() -> None:
    with TestClient(app) as client:
        payload = {
            "name": f"Contract Agent {uuid4()}",
            "role": "Contract smoke tester",
            "system_prompt": "Return deterministic contract test responses.",
            "model": "gpt-4o",
            "tools": ["calculator"],
            "config": {"temperature": 0},
            "channels": ["internal"],
        }
        created = client.post("/api/v1/agents", json=payload)
        assert created.status_code == 201
        agent_id = created.json()["id"]
        fetched = client.get(f"/api/v1/agents/{agent_id}")
        assert fetched.status_code == 200
        assert fetched.json()["name"] == payload["name"]
        assert client.get("/api/v1/agents/tools").status_code == 200
        assert client.get("/api/v1/agents/models").status_code == 200
        assert client.patch(f"/api/v1/agents/{agent_id}", json={"role": "Updated"}).status_code == 200
        assert client.delete(f"/api/v1/agents/{agent_id}").status_code == 204


def test_workflow_round_trip_and_run_creation() -> None:
    with TestClient(app) as client:
        payload = {
            "name": f"Contract Workflow {uuid4()}",
            "description": "Smoke test workflow",
            "graph": {"nodes": [], "edges": []},
            "is_template": False,
        }
        created = client.post("/api/v1/workflows", json=payload)
        assert created.status_code == 201
        workflow_id = created.json()["id"]
        fetched = client.get(f"/api/v1/workflows/{workflow_id}")
        assert fetched.status_code == 200
        assert fetched.json()["name"] == payload["name"]

        run = client.post(f"/api/v1/workflows/{workflow_id}/run", json={"input": "Contract smoke input"})
        assert run.status_code == 201
        run_id = run.json()["run_id"]
        assert client.get(f"/api/v1/runs/{run_id}").status_code == 200
        assert client.get(f"/api/v1/runs/{run_id}/events").status_code == 200


def test_conversation_and_telegram_polling_contract() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/telegram/webhook",
            json={"update_id": 123, "message": {"text": "hello", "chat": {"id": "chat-1"}}},
        )
        assert response.status_code == 503
        assert client.get("/api/v1/conversations?channel=telegram").status_code == 200
        assert client.get("/api/v1/stats/dashboard").status_code == 200


def test_run_websocket_replays_runtime_events() -> None:
    with TestClient(app) as client:
        workflow = client.post(
            "/api/v1/workflows",
            json={
                "name": f"Replay Workflow {uuid4()}",
                "description": "Empty graph emits run_started then error without LLM calls.",
                "graph": {"nodes": [], "edges": []},
                "is_template": False,
            },
        ).json()
        run_id = client.post(f"/api/v1/workflows/{workflow['id']}/run", json={"input": "Replay smoke"}).json()["run_id"]
        with client.websocket_connect(f"/ws/runs/{run_id}") as websocket:
            event = websocket.receive_json()
            assert event["event_type"] in {"run_started", "error"}
