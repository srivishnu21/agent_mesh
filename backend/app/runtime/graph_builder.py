import re
from uuid import UUID

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entities import Agent
from app.runtime.event_emitter import emit
from app.runtime.guardrails import apply_input_guardrails
from app.runtime.memory import inject_memory, load_memory_blurbs
from app.runtime.state import WorkflowState
from app.runtime.tools import get_tools_for_agent


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


def _model_for_provider(agent: Agent) -> str:
    model = agent.model or settings.DEFAULT_MODEL
    if settings.LLM_PROVIDER == "openai_compatible" and model.startswith("claude-"):
        return settings.OPENAI_COMPATIBLE_MODEL
    return model


def make_chat_model(agent: Agent, *, temperature: float | None = None, max_tokens: int | None = None):
    config = agent.config or {}
    model = _model_for_provider(agent)
    resolved_temperature = config.get("temperature", 0.2) if temperature is None else temperature
    resolved_max_tokens = config.get("max_tokens", 1024) if max_tokens is None else max_tokens

    if settings.LLM_PROVIDER == "openai_compatible":
        kwargs = {
            "model": model,
            "api_key": settings.OPENAI_COMPATIBLE_API_KEY,
            "base_url": settings.OPENAI_COMPATIBLE_BASE_URL,
        }
        if model.startswith("gpt-5"):
            kwargs["max_completion_tokens"] = max(int(resolved_max_tokens), 2500)
            kwargs["reasoning_effort"] = config.get("reasoning_effort", "minimal")
            kwargs["verbosity"] = config.get("verbosity", "medium")
        else:
            kwargs["temperature"] = resolved_temperature
            kwargs["max_completion_tokens"] = resolved_max_tokens
        return ChatOpenAI(**kwargs)

    return ChatAnthropic(
        model=model,
        api_key=settings.ANTHROPIC_API_KEY,
        temperature=resolved_temperature,
        max_tokens=resolved_max_tokens,
    )


def _make_chat_model(agent: Agent):  # legacy alias retained for tests
    return make_chat_model(agent)


def _usage_cost(input_tokens: int, output_tokens: int) -> float:
    if settings.LLM_PROVIDER == "openai_compatible":
        return (input_tokens * settings.INPUT_COST_PER_1K + output_tokens * settings.OUTPUT_COST_PER_1K) / 1000
    return (input_tokens * 3 + output_tokens * 15) / 1_000_000


_EMPTY_RESULT_MARKERS = ("no results found", "no order found", "search temporarily unavailable")


def _classify_tool_result(tool_name: str, result_str: str) -> str:
    lowered = result_str.strip().lower()
    if lowered.startswith("tool error:") or lowered.startswith("unknown tool:"):
        return "error"
    if any(marker in lowered for marker in _EMPTY_RESULT_MARKERS):
        return "empty"
    return "ok"


async def _invoke_tool(session: AsyncSession, run_id: UUID, agent: Agent, tool_map: dict, tool_name: str, tool_args: dict) -> str:
    await emit(
        session,
        run_id,
        "tool_call",
        {"tool": tool_name, "args": tool_args, "source": "runtime_required"},
        agent_id=agent.id,
    )
    tool_fn = tool_map.get(tool_name)
    if tool_fn is None:
        result = f"Unknown tool: {tool_name}"
    else:
        try:
            result = await tool_fn.ainvoke(tool_args)
        except Exception as exc:
            result = f"Tool error: {exc}"
    result_str = str(result)
    await emit(
        session,
        run_id,
        "tool_result",
        {
            "tool": tool_name,
            "result": result_str[:1500],
            "source": "runtime_required",
            "status": _classify_tool_result(tool_name, result_str),
        },
        agent_id=agent.id,
    )
    return result_str


def _latest_user_text(state: WorkflowState) -> str:
    for message in reversed(state["messages"]):
        if getattr(message, "type", None) == "human":
            return _message_content_text(message.content)
    return _message_content_text(state["messages"][-1].content) if state.get("messages") else ""


_SEARCH_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "is", "are",
    "was", "were", "be", "been", "being", "do", "does", "did", "have", "has", "had",
    "i", "you", "we", "they", "it", "this", "that", "these", "those", "me", "my",
    "use", "using", "please", "can", "could", "would", "should", "summarize",
    "summary", "search", "find", "list", "give", "tell", "show", "explain", "about",
    "what", "which", "who", "whom", "where", "when", "why", "how", "current", "currently",
}


def _build_search_query(text: str, max_words: int = 8, max_chars: int = 120) -> str:
    cleaned = re.sub(r"[^\w\s\-]", " ", text)
    words = [w for w in cleaned.split() if w]
    filtered = [w for w in words if w.lower() not in _SEARCH_STOPWORDS]
    if not filtered:
        filtered = words
    query = " ".join(filtered[:max_words])[:max_chars].strip()
    return query or text[:max_chars]


def _required_tool_plan(agent: Agent, state: WorkflowState, tool_map: dict) -> list[tuple[str, dict]]:
    text = _latest_user_text(state)
    configured = agent.config or {}
    plan = []

    force_tool = configured.get("force_tool")
    if isinstance(force_tool, str) and force_tool in tool_map:
        if force_tool == "web_search":
            plan.append(("web_search", {"query": _build_search_query(text)}))
        elif force_tool == "sql_query":
            plan.append(("sql_query", {"query": text}))

    if "order_lookup" in tool_map:
        for order_id in sorted(set(re.findall(r"\bORD-\d+\b", text, flags=re.IGNORECASE))):
            plan.append(("order_lookup", {"order_id": order_id.upper()}))

    if "calculator" in tool_map and re.search(r"\d+\s*[+\-*/%]", text):
        expression = re.sub(r"[^0-9+\-*/%(). ]", "", text).strip()
        if expression:
            plan.append(("calculator", {"expression": expression}))

    seen = set()
    unique_plan = []
    for tool_name, tool_args in plan:
        key = (tool_name, tuple(sorted(tool_args.items())))
        if key not in seen:
            seen.add(key)
            unique_plan.append((tool_name, tool_args))
    return unique_plan


def _apply_guardrails_to_messages(messages, agent, session, run_id):
    guardrails = (agent.config or {}).get("guardrails") or {}
    if not guardrails:
        return messages, []

    scrubbed = []
    triggered_events = []
    for message in messages:
        if getattr(message, "type", None) != "human":
            scrubbed.append(message)
            continue
        original = _message_content_text(message.content)
        outcome = apply_input_guardrails(original, guardrails)
        if outcome.triggered:
            triggered_events.append({"types": outcome.triggered, "counts": outcome.counts})
            scrubbed.append(HumanMessage(content=outcome.text))
        else:
            scrubbed.append(message)
    return scrubbed, triggered_events


def make_agent_node(agent: Agent, session: AsyncSession, memory_blurb: str | None = None):
    tools = get_tools_for_agent(agent.tools or [])
    llm = make_chat_model(agent)
    if tools:
        llm = llm.bind_tools(tools)
    tool_map = {tool.name: tool for tool in tools}
    effective_system_prompt = inject_memory(agent.system_prompt, memory_blurb)

    async def node(state: WorkflowState) -> dict:
        run_id = UUID(state["run_id"])
        await emit(
            session,
            run_id,
            "node_started",
            {"agent_name": agent.name, "role": agent.role},
            agent_id=agent.id,
        )

        incoming_messages, guardrail_events = _apply_guardrails_to_messages(
            list(state["messages"]), agent, session, run_id
        )
        for event in guardrail_events:
            await emit(
                session,
                run_id,
                "guardrail_triggered",
                {"agent_name": agent.name, "guardrail": "pii_redact", **event},
                agent_id=agent.id,
            )

        messages = [SystemMessage(content=effective_system_prompt)] + incoming_messages
        new_messages = []
        required_results = []

        scrubbed_state: WorkflowState = {**state, "messages": incoming_messages}
        for tool_name, tool_args in _required_tool_plan(agent, scrubbed_state, tool_map):
            result = await _invoke_tool(session, run_id, agent, tool_map, tool_name, tool_args)
            required_results.append(f"{tool_name}({tool_args}) -> {result}")

        if required_results:
            tool_context = (
                "Runtime-required tool results are verified context for this agent. "
                "Use them in your answer and cite the relevant facts:\n"
                + "\n\n".join(required_results)
            )
            messages.append(HumanMessage(content=tool_context))

        for iteration in range(1, 4):
            await emit(
                session,
                run_id,
                "llm_call",
                {"agent_name": agent.name, "iteration": iteration, "message_count": len(messages)},
                agent_id=agent.id,
            )
            response = await llm.ainvoke(messages)
            messages.append(response)
            new_messages.append(response)

            usage = getattr(response, "usage_metadata", {}) or {}
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            cost = _usage_cost(input_tokens, output_tokens)

            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                await emit(
                    session,
                    run_id,
                    "agent_message",
                    {"agent_name": agent.name, "content": _message_content_text(response.content)},
                    agent_id=agent.id,
                    tokens=input_tokens + output_tokens,
                    cost_usd=cost,
                )
                break

            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                result = await _invoke_tool(session, run_id, agent, tool_map, tool_name, tool_args)
                tool_message = ToolMessage(content=str(result), tool_call_id=tool_call["id"])
                messages.append(tool_message)
                new_messages.append(tool_message)

        await emit(session, run_id, "node_completed", {"agent_name": agent.name}, agent_id=agent.id)

        update: dict = {"messages": new_messages}
        last_text = next(
            (
                _message_content_text(m.content)
                for m in reversed(new_messages)
                if getattr(m, "type", None) in {"ai", "AIMessage"} or m.__class__.__name__ == "AIMessage"
            ),
            "",
        )
        route = _extract_route(last_text)
        if route:
            update["route"] = route
        return update

    return node


_ROUTE_PATTERNS = (
    re.compile(r"^\s*ROUTE\s*:\s*([A-Za-z0-9_\- ]+)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*CATEGORY\s*:\s*([A-Za-z0-9_\- ]+)", re.IGNORECASE | re.MULTILINE),
)


def _extract_route(text: str) -> str | None:
    if not text:
        return None
    for pattern in _ROUTE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip().lower().replace(" ", "_")
    return None


_END_ALIASES = {"end", "__end__", "exit", "finish", "done"}


def _resolve_target(name: str):
    """Map JSON edge target to a langgraph node id or END constant."""
    if isinstance(name, str) and name.strip().lower() in _END_ALIASES:
        return END
    return name


def _make_router(edges: list[dict], default_target: str):
    """Return a callable used by langgraph add_conditional_edges.

    Edges with a ``condition`` dict like ``{"route_equals": "billing"}`` are matched
    against ``state["route"]``. Edges with ``condition: {"always": True}`` or no condition
    act as the catch-all fallback in declared order. ``to: "END"`` exits the graph.
    """
    typed_edges = []
    fallback = None
    for edge in edges:
        target = _resolve_target(edge["to"])
        condition = edge.get("condition") or {}
        if not condition or condition.get("always"):
            if fallback is None:
                fallback = target
            continue
        match_value = condition.get("route_equals") or condition.get("equals")
        if match_value is None:
            continue
        typed_edges.append((str(match_value).lower(), target))

    if fallback is None:
        fallback = _resolve_target(default_target)
    targets = {target for _, target in typed_edges}
    targets.add(fallback)

    def _router(state: WorkflowState) -> str:
        route = (state.get("route") or "").lower()
        for value, target in typed_edges:
            if route == value:
                return target
        return fallback

    # path_map keys must match what the router returns. langgraph's END is the literal "__end__".
    routing_map = {t: t for t in targets}
    return _router, routing_map


async def build_graph_from_workflow(
    workflow,
    agents_by_id: dict[UUID, Agent],
    session: AsyncSession,
    *,
    conversation_id: UUID | None = None,
):
    builder = StateGraph(WorkflowState)
    nodes = workflow.graph.get("nodes", [])
    edges = workflow.graph.get("edges", [])

    if not nodes:
        raise ValueError("Workflow has no nodes")

    memory_blurbs: dict[UUID, str] = {}
    if conversation_id is not None:
        agent_ids = [UUID(node["agent_id"]) for node in nodes]
        memory_blurbs = await load_memory_blurbs(session, conversation_id, agent_ids)

    for node in nodes:
        agent = agents_by_id[UUID(node["agent_id"])]
        builder.add_node(
            node["id"],
            make_agent_node(agent, session, memory_blurb=memory_blurbs.get(agent.id)),
        )

    # Sources = nodes with no incoming edge from another real node (ignoring END targets).
    node_ids = [node["id"] for node in nodes]
    node_id_set = set(node_ids)
    incoming = {edge["to"] for edge in edges if edge["to"] in node_id_set}
    sources = [node_id for node_id in node_ids if node_id not in incoming]
    # Sinks = nodes whose only outgoing targets are END, or that have no outgoing edge.
    has_real_outgoing: dict[str, bool] = {node_id: False for node_id in node_ids}
    for edge in edges:
        if edge["from"] in node_id_set and edge["to"] in node_id_set:
            has_real_outgoing[edge["from"]] = True
    sinks = [node_id for node_id, has_out in has_real_outgoing.items() if not has_out]

    if not sources:
        # Every node has incoming = workflow contains a feedback loop. Use the first declared node
        # as the entry point so the graph still has a START.
        sources = [node_ids[0]]
    if len(sources) > 1:
        raise ValueError(f"Workflow must have exactly one source node, found {len(sources)}")

    builder.add_edge(START, sources[0])

    edges_by_source: dict[str, list[dict]] = {}
    for edge in edges:
        edges_by_source.setdefault(edge["from"], []).append(edge)

    for source, source_edges in edges_by_source.items():
        if any(edge.get("condition") for edge in source_edges):
            router, routing_map = _make_router(source_edges, default_target=source_edges[0]["to"])
            builder.add_conditional_edges(source, router, routing_map)
        else:
            for edge in source_edges:
                builder.add_edge(edge["from"], _resolve_target(edge["to"]))
    for sink in sinks:
        if sink not in edges_by_source:  # genuinely terminal node, wire to END
            builder.add_edge(sink, END)

    return builder.compile()
