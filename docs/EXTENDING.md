# Extending Agent Mesh

This is the practical "how do I add X" guide. Source paths are absolute from repo root.

## Add a new tool

A tool is any async function decorated with `@tool` from `langchain_core.tools`. The runtime invokes tools either by the LLM via `bind_tools` or, when the agent's `config.force_tool` is set, deterministically from `_required_tool_plan` in `backend/app/runtime/graph_builder.py`.

1. Add the function in `backend/app/runtime/tools.py`:

   ```python
   @tool
   async def my_tool(arg1: str, arg2: int = 1) -> str:
       """One-line description shown to the LLM."""
       return "result"
   ```

2. Register it in the `TOOL_REGISTRY` dict at the bottom of the same file.
3. Surface it in the agents API so the UI/agent config can reference it. Add an entry to the `TOOLS` list in `backend/app/api/agents.py` with `name`, `description`, and `params_schema`.
4. (Optional) If the tool should be **forced** by the runtime (not LLM-decided), extend `_required_tool_plan` in `graph_builder.py` to produce a plan entry from the user input.
5. Add a deterministic test in `backend/tests/test_runtime.py` that calls `my_tool.ainvoke({...})`.

## Add a new workflow template

Templates are seeded rows in the `workflows` table with `is_template=True`. Edit `backend/app/seed.py`:

1. Define the agents you need with `_upsert_agent(...)`. Each agent needs `name`, `role`, `system_prompt`, `model`, `tools`, `config`, `channels`.
2. Define the workflow with `_upsert_workflow(name, description, is_template=True, graph={...})`. The graph schema:

   ```jsonc
   {
     "nodes": [
       {"id": "step1", "agent_id": "<uuid>", "position": {"x": 100, "y": 100}}
     ],
     "edges": [
       // straight edge
       {"from": "step1", "to": "step2"},
       // conditional edge — selected when prior agent emits `ROUTE: billing`
       {"from": "triage", "to": "billing", "condition": {"route_equals": "billing"}, "label": "billing"},
       // catch-all
       {"from": "triage", "to": "general", "condition": {"always": true}, "label": "default"}
     ]
   }
   ```

3. The Smart Router template is the canonical conditional-edge example — copy its structure.
4. Restart the backend (`docker compose restart backend`); seed runs idempotently and `_upsert_*` updates rows in place.

## Add a new messaging channel

The Telegram integration is the reference. Adapter pattern: a channel module owns inbound message → run trigger → outbound reply.

1. Create `backend/app/integrations/<channel>_bot.py` exposing:
   - `async def handle_incoming_message(external_id, user_text, sender_metadata)` — creates or finds a `Conversation` row scoped by `(Channel.<x>, external_id)`, inserts a `Message`, creates a `Run`, calls `execute_run(run_id, workflow_id, user_text, conversation_id=conversation_id)`, then sends the agent reply back through the channel's SDK.
   - `async def start_polling()` and `async def stop_polling()` if the channel uses polling; otherwise expose a FastAPI router for the webhook.
2. Add the channel to the `Channel` enum in `backend/app/models/entities.py`. Write an alembic migration in `backend/alembic/versions/` to extend the Postgres enum.
3. Wire startup/shutdown in `backend/app/main.py` alongside the Telegram lifecycle hooks.
4. Add channel-specific settings (token, mode, webhook URL) to `backend/app/config.py`.
5. Add a contract test in `backend/tests/test_contract.py` that mocks the channel SDK and asserts a run is created.

The runtime already accepts a `conversation_id` for rolling memory, so passing it in step 1 enables per-user memory automatically.

## Add a new guardrail

Guardrails are applied per-message inside `make_agent_node` in `backend/app/runtime/graph_builder.py`. The dispatcher is `apply_input_guardrails` in `backend/app/runtime/guardrails.py`.

1. Extend `apply_input_guardrails` with a new mode handler (e.g. `if guardrails.get("toxicity") == "block": ...`).
2. Return a `GuardrailOutcome(text, triggered, counts)`. The runtime emits a `guardrail_triggered` event automatically when `triggered` is non-empty.
3. Reflect the new mode in seeded agent configs (`backend/app/seed.py`) under `config["guardrails"]`.

## Add a new agent configuration dimension

Agent `config` is a free-form JSON column. To make a new field meaningful at runtime, read it inside `make_chat_model` or `make_agent_node` in `backend/app/runtime/graph_builder.py`.

Existing recognized keys: `temperature`, `max_tokens`, `memory_enabled`, `force_tool`, `guardrails`, `reasoning_effort`, `verbosity`.

## Run the test suite

```bash
cd backend
pytest                  # contract + runtime
pytest -m integration   # also exercises real LLM (needs an API key)
```
