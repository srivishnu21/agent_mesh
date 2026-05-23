from uuid import UUID

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entities import Agent
from app.runtime.event_emitter import emit
from app.runtime.state import WorkflowState
from app.runtime.tools import get_tools_for_agent


def _message_content_text(content) -> str:
    if isinstance(content, str):
        return content
    return str(content)


def make_agent_node(agent: Agent, session: AsyncSession):
    tools = get_tools_for_agent(agent.tools or [])
    llm = ChatAnthropic(
        model=agent.model or settings.DEFAULT_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        temperature=(agent.config or {}).get("temperature", 0.2),
        max_tokens=(agent.config or {}).get("max_tokens", 1024),
    )
    if tools:
        llm = llm.bind_tools(tools)
    tool_map = {tool.name: tool for tool in tools}

    async def node(state: WorkflowState) -> dict:
        run_id = UUID(state["run_id"])
        await emit(
            session,
            run_id,
            "node_started",
            {"agent_name": agent.name, "role": agent.role},
            agent_id=agent.id,
        )

        messages = [SystemMessage(content=agent.system_prompt)] + state["messages"]
        new_messages = []

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
            cost = (input_tokens * 3 + output_tokens * 15) / 1_000_000

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
                await emit(
                    session,
                    run_id,
                    "tool_call",
                    {"tool": tool_name, "args": tool_args},
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
                await emit(
                    session,
                    run_id,
                    "tool_result",
                    {"tool": tool_name, "result": str(result)[:1500]},
                    agent_id=agent.id,
                )
                tool_message = ToolMessage(content=str(result), tool_call_id=tool_call["id"])
                messages.append(tool_message)
                new_messages.append(tool_message)

        await emit(session, run_id, "node_completed", {"agent_name": agent.name}, agent_id=agent.id)
        return {"messages": new_messages}

    return node


async def build_graph_from_workflow(workflow, agents_by_id: dict[UUID, Agent], session: AsyncSession):
    builder = StateGraph(WorkflowState)
    nodes = workflow.graph.get("nodes", [])
    edges = workflow.graph.get("edges", [])

    if not nodes:
        raise ValueError("Workflow has no nodes")

    for node in nodes:
        agent = agents_by_id[UUID(node["agent_id"])]
        builder.add_node(node["id"], make_agent_node(agent, session))

    incoming = {edge["to"] for edge in edges}
    sources = [node["id"] for node in nodes if node["id"] not in incoming]
    outgoing = {edge["from"] for edge in edges}
    sinks = [node["id"] for node in nodes if node["id"] not in outgoing]

    if len(sources) != 1:
        raise ValueError(f"Workflow must have exactly one source node, found {len(sources)}")

    builder.add_edge(START, sources[0])
    for edge in edges:
        builder.add_edge(edge["from"], edge["to"])
    for sink in sinks:
        builder.add_edge(sink, END)

    return builder.compile()
