# Phase 3 Spec: Telegram Integration + Visual Workflow Builder + Polish

## Context

Phases 1 and 2 are done. The platform can:
- Create agents end-to-end via the UI
- Execute workflows with real LangGraph + Claude Sonnet 4.5
- Stream live events to the `/runs/[id]` page via WebSocket
- Show a working "Customer Support Triage" demo from the templates page

This phase delivers the three things still missing from the rubric:

1. **External messaging channel** (Telegram) - a human chats with an agent from Telegram, the message flows through a workflow, the response comes back. This is the hardest single requirement to fake and the most impressive when it works.
2. **Visual workflow builder** (React Flow) - drag agents onto a canvas, draw edges, save. This is what the rubric calls "configurability" and is worth a chunk of the 20% UI/UX score.
3. **Dashboard + polish** - aggregate metrics, status badges, empty states, error toasts. The difference between "looks like a demo" and "looks like a product."

**Out of scope:** Slack, WhatsApp, multi-provider LLM, RAG, auth, scheduling. We're shipping a demo, not a SaaS.

---

## Priority order (do these in sequence)

1. Telegram integration (highest demo impact)
2. Workflow builder (high configurability score)
3. Dashboard + polish (closes the rubric)
4. README + architecture diagram + demo video (the 10% documentation)

If time runs short, ship 1+2+4 and skip the dashboard. Telegram is the showstopper.

---

# PART 1 - Telegram Integration

## Demo behavior

User opens Telegram -> sends a message to `@YunoSupportDemoBot` -> bot replies in chat with an agent-generated response. Internally:

1. Telegram POSTs an update to `/api/v1/telegram/webhook`
2. Backend persists the message in a `conversations` + `messages` row
3. Backend triggers a run of the workflow tagged for Telegram, passing the message text as input
4. When the run completes, backend reads the final agent message and sends it back to the Telegram chat
5. Every step is also visible in the `/runs/[id]` live view AND in the `/conversations` page

## Setup choice: webhook vs polling

**Use polling for local development, webhook for "production-ready" code.**

Why: webhooks require a public HTTPS URL. Locally you'd need ngrok or similar, which is fragile for a demo. Implement BOTH paths in code, but make polling the default in `docker-compose.yml`. Document the webhook path in the README so the reviewer sees you understood the production answer.

## Dependencies

Add to `backend/pyproject.toml`:

```toml
python-telegram-bot = "^21.7"
```

Add to `backend/.env.example`:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_MODE=polling          # polling | webhook
TELEGRAM_WEBHOOK_URL=          # only used if TELEGRAM_MODE=webhook
TELEGRAM_DEFAULT_WORKFLOW_ID=  # uuid of the workflow Telegram messages route to
```

## File: `backend/app/integrations/telegram_bot.py` (new)

The polling loop and the webhook handler share a single `handle_update` function.

## File: `backend/app/api/telegram.py` - webhook handler

Replace the Phase 1 stub with a real webhook route that parses Telegram updates and forwards text messages to `handle_incoming_message`.

## File: `backend/app/main.py` - wire startup

Add Telegram polling to the FastAPI lifespan context manager with `start_polling()` on startup and `stop_polling()` on shutdown.

## File: `backend/app/seed.py` - auto-set the default workflow

At the end of the seed function, find the Customer Support Triage template and write its id to a startup log line. Better: also write the id to `backend/.telegram_workflow_id` so README setup is "run docker compose up, copy this id into `.env`, restart."

## File: `frontend/app/conversations/page.tsx`

List view of all conversations. Each row: channel badge, Telegram username or external id, last message preview, last message timestamp, message count. Click a row -> `/conversations/[id]`.

## File: `frontend/app/conversations/[id]/page.tsx` (new)

A chat-style transcript view. Left-aligned bubbles for `role=user`, right-aligned for `role=agent`. If a message has `meta.run_id`, show a small "View run ->" link that opens `/runs/{run_id}` in a new tab.

---

# PART 2 - Visual Workflow Builder (React Flow)

## Behavior

User goes to `/workflows`, clicks "New workflow" or "Edit" on an existing one. Lands on `/workflows/[id]/edit`. Canvas on the left/center, side panel on the right.

- **Left panel:** list of all agents from `GET /agents`. Drag an agent onto the canvas to add a node.
- **Canvas:** nodes show agent name + role + a small tools chip. Edges drawn by dragging from one node's right handle to another's left handle.
- **Right panel:** when a node is selected, show its agent details (read-only summary) and a "Remove node" button. When the canvas itself is selected, show workflow name + description editor.
- **Top bar:** "Save" button (persists `graph` JSON), "Run" button (opens the run dialog from Phase 2), "Back to workflows".

## Dependencies

```bash
npm install reactflow
```

## File: `frontend/app/workflows/[id]/edit/page.tsx`

Use React Flow's controlled mode. Hydrate nodes and edges from `workflow.graph`, support drag and drop from the agent palette, validate before save, and persist graph JSON to `PATCH /api/v1/workflows/{id}`.

## File: `frontend/components/workflow/agent-node.tsx`

Custom React Flow node component showing agent name, role, tools, and left/right handles.

## File: `frontend/components/workflow/agent-palette.tsx`

Vertical draggable list of agents. Each item sets `application/agent-id` on drag start.

## Validation before save

Before persisting, validate:
- At least one node
- Exactly one source node (no incoming edges)
- No orphan nodes (every non-source node has an incoming edge)

If validation fails, show a toast and don't save.

## "New workflow" flow

From `/workflows`, the "New workflow" button POSTs an empty workflow (`{name: "Untitled", graph: {nodes:[], edges:[]}}`) and navigates to its edit page.

---

# PART 3 - Dashboard & Polish

## Dashboard (`frontend/app/page.tsx`)

Replace the placeholder. Four metric cards across the top:

- **Agents** - count from `GET /agents`
- **Workflows** - count from `GET /workflows`
- **Runs today** - count of runs where `started_at >= today_start`
- **Tokens today** - sum of `total_tokens` over runs today, formatted with commas

Below: a "Recent runs" table (last 10) with workflow name, status badge, started_at, tokens, cost. Clicking a row -> `/runs/{id}`.

Add a new endpoint `GET /api/v1/stats/dashboard` that returns these in one shot.

## Status badges

Create `frontend/components/ui/status-badge.tsx` and use it everywhere status appears.

## Empty states

Every list page (`/agents`, `/workflows`, `/runs`, `/conversations`) needs a friendly empty state when the table has zero rows.

## Error handling

Wrap fetch failures and surface them with `sonner` toasts.

## Loading states

Every page with data fetching shows a skeleton for the first paint. No bare spinners.

---

# PART 4 - README + Architecture + Demo

Update README with:
- Demo
- Architecture diagram
- Why these choices
- Quick start
- What's implemented vs what's stubbed
- Running the demo
- Project structure
- Tests
- Production roadmap

The architecture diagram should only include boxes that exist in code: Telegram/Browser, FastAPI, in-process LangGraph runtime, and PostgreSQL.

## Demo video

Record a 3-4 minute screen recording showing dashboard, agents, workflow editor, live run timeline, Telegram, conversations, and builder save flow.

---

## Acceptance checklist for Phase 3

- [ ] `docker compose up --build` brings up everything including Telegram polling (if token configured)
- [ ] Sending a Telegram message to the configured bot produces a reply within 30 seconds
- [ ] That same message appears as a new conversation in `/conversations`
- [ ] Clicking the conversation shows the chat transcript with a "View run ->" link
- [ ] The linked `/runs/{id}` page shows the full live timeline including the Telegram trigger
- [ ] The workflow editor at `/workflows/{id}/edit` loads the existing graph correctly
- [ ] Dragging an agent onto the canvas adds a node
- [ ] Connecting two nodes via edge handles works
- [ ] Save persists the graph and a freshly-loaded page shows the same graph
- [ ] The "Run" button from the editor still works after editing
- [ ] Dashboard at `/` shows non-zero metrics after running a workflow
- [ ] Empty states display correctly when tables are empty
- [ ] Loading skeletons appear during first paint
- [ ] Errors surface as toasts, not silent failures
- [ ] `pytest backend/tests/` still passes; add at least one test for `handle_incoming_message`
- [ ] README is updated with setup, demo video link, architecture diagram, "what's stubbed" section, production roadmap
- [ ] Demo video is recorded and linked from README

---

## Common pitfalls

- Telegram polling and FastAPI lifespan: call `shutdown()` on stop or restarts can fail.
- `python-telegram-bot` changed substantially after v13. Pin to v21.
- Telegram cannot reach `localhost`; webhook mode needs a public HTTPS URL.
- Seed the default workflow id loudly so the user does not have to grep the database.
- Telegram caps messages at 4096 chars. Chunk responses.
- React Flow `onDragOver` must call `preventDefault()` or drop will not fire.
- Validate graph before save.

---

## Nice-to-haves

- Cost tracking per agent
- Replay run
- Agent versioning tag
- Light/dark mode toggle
