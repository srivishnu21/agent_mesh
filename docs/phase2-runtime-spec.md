# Phase 2 Runtime Spec

Phase 2 turns the Phase 1 contract scaffold into a runnable multi-agent demo.

## Demo

The main demo is `Customer Support Triage`:

1. `Triage Agent` classifies the customer request.
2. `Support Specialist` uses `order_lookup` and `web_search`.
3. Each meaningful step is persisted as a `run_event`.
4. `/runs/{id}` streams the event timeline over WebSocket and replays prior history for late joiners.

Hero input:

> Hi, I placed order ORD-1042 three days ago and the tracking link isn't working. Can you check the status and tell me what the standard delivery window is for international orders?

## Implemented

- `POST /api/v1/workflows/{id}/run` accepts `{ "input": "..." }`, creates a run, and starts `asyncio.create_task(...)`.
- `backend/app/runtime/` owns graph building, tools, event emission, and workflow execution.
- `web_search` calls Tavily when configured and falls back to deterministic snippets when unavailable.
- `order_lookup` uses mock order data for `ORD-1042` and `ORD-2055`.
- WebSocket manager broadcasts persisted events and replays history on connect.
- `/workflows` can launch seeded templates.
- `/runs/[id]` renders a live event timeline with token/cost totals.

## Deferred

- Telegram routing into workflows.
- React Flow workflow builder.
- Auth and multi-provider model selection.
- Redis-backed WebSocket fanout.
