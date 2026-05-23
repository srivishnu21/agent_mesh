"""Classify exceptions raised during run execution into user-friendly error events.

Categories cover the realistic failure modes we have seen so far:
- recursion_limit: feedback loop or fan-out exceeded LangGraph's recursion budget.
- token_limit:     prompt + planned completion exceeded the model's context window.
- rate_limit:      provider returned 429 (quota / RPM exhausted).
- auth:            invalid API key or missing permission scope.
- timeout:         network/LLM request exceeded the client timeout.
- model_error:     other provider-side failure (5xx, bad request, etc).
- tool_unavailable: a tool referenced by the workflow can't run (missing key, network).
- graph_invalid:   workflow topology cannot be compiled (no nodes, dangling source, etc).
- unknown:         catch-all for anything we have not characterized yet.
"""

from __future__ import annotations

from dataclasses import dataclass

try:  # langgraph 0.2+
    from langgraph.errors import GraphRecursionError  # type: ignore
except Exception:  # pragma: no cover - older versions raised plain RuntimeError
    GraphRecursionError = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ClassifiedError:
    category: str
    message: str
    hint: str
    retriable: bool = False

    def to_payload(self) -> dict:
        return {
            "category": self.category,
            "message": self.message,
            "hint": self.hint,
            "retriable": self.retriable,
        }


_TOKEN_LIMIT_MARKERS = (
    "context_length_exceeded",
    "maximum context length",
    "context length of only",
    "too many tokens",
    "prompt is too long",
    "max_tokens_to_sample",
)
_RATE_LIMIT_MARKERS = (
    "rate_limit",
    "rate limit",
    "ratelimit",
    "quota",
    "429",
    "too many requests",
)
_AUTH_MARKERS = (
    "invalid_api_key",
    "incorrect api key",
    "authentication",
    "unauthorized",
    "401",
    "permission denied",
)
_TIMEOUT_MARKERS = (
    "timeout",
    "timed out",
    "request timeout",
)
_GRAPH_MARKERS = (
    "workflow has no nodes",
    "workflow must have exactly one source",
    "every non-source node",
    "agent_id",
)
_TOOL_MARKERS = (
    "tavily",
    "ddg",
    "duckduckgo",
    "tool error",
    "missing api key",
)


def _name(exc: BaseException) -> str:
    return exc.__class__.__name__


def classify(exc: BaseException) -> ClassifiedError:
    """Translate an exception into a user-facing category + message."""
    if exc is None:  # type: ignore[unreachable]
        return ClassifiedError("unknown", "Unknown error", "")

    name = _name(exc)
    text = str(exc) or name
    lower = text.lower()

    # 1) Recursion / loop bound.
    if GraphRecursionError is not None and isinstance(exc, GraphRecursionError):  # type: ignore[arg-type]
        return ClassifiedError(
            category="recursion_limit",
            message="Workflow exceeded the 25-step recursion limit.",
            hint=(
                "A feedback loop or fan-out kept firing without converging. "
                "Tighten the routing condition, lower the per-agent revision cap, "
                "or add a catch-all edge to END so the run can terminate."
            ),
        )
    if "recursion" in lower and "limit" in lower:
        return ClassifiedError(
            category="recursion_limit",
            message="Workflow exceeded the recursion limit.",
            hint="Add a terminal edge (target: END) or tighten the loop condition so the cycle exits.",
        )

    # 2) Token / context-length issues.
    if any(marker in lower for marker in _TOKEN_LIMIT_MARKERS):
        return ClassifiedError(
            category="token_limit",
            message="Model context window exceeded.",
            hint=(
                "Shorten the system prompt, trim conversation memory, or switch the agent to a model "
                "with a larger context window. Memory summarisation also helps if memory_enabled=true."
            ),
        )

    # 3) Rate limit / quota.
    if any(marker in lower for marker in _RATE_LIMIT_MARKERS) or name in {"RateLimitError"}:
        return ClassifiedError(
            category="rate_limit",
            message="Model provider rate-limited the request.",
            hint="Wait and retry, lower request frequency, or rotate to a higher-tier API key.",
            retriable=True,
        )

    # 4) Auth.
    if any(marker in lower for marker in _AUTH_MARKERS) or name in {"AuthenticationError", "PermissionDeniedError"}:
        return ClassifiedError(
            category="auth",
            message="Model provider rejected the API key.",
            hint="Check OPENAI_COMPATIBLE_API_KEY / ANTHROPIC_API_KEY in backend/.env and restart the backend.",
        )

    # 5) Timeout.
    if any(marker in lower for marker in _TIMEOUT_MARKERS) or name in {"APITimeoutError", "TimeoutError"}:
        return ClassifiedError(
            category="timeout",
            message="LLM request timed out.",
            hint="Network or provider was slow. Retry the run; if it persists, raise the client timeout in graph_builder.make_chat_model.",
            retriable=True,
        )

    # 6) Graph build failures.
    if isinstance(exc, ValueError) and any(marker in lower for marker in _GRAPH_MARKERS):
        return ClassifiedError(
            category="graph_invalid",
            message=text,
            hint="Open the workflow editor and check that the graph has a single entry point and every non-source node has an incoming edge.",
        )

    # 7) Tool-specific failures (best-effort heuristic).
    if any(marker in lower for marker in _TOOL_MARKERS):
        return ClassifiedError(
            category="tool_unavailable",
            message=text,
            hint="Check the relevant tool's credentials/network. web_search falls back to DuckDuckGo if Tavily is missing.",
            retriable=True,
        )

    # 8) Generic model / SDK errors.
    if name in {"BadRequestError", "APIError", "APIConnectionError", "InternalServerError"}:
        return ClassifiedError(
            category="model_error",
            message=text,
            hint="Provider returned an error. Inspect backend logs for the full trace.",
            retriable=name in {"APIConnectionError", "InternalServerError"},
        )

    # 9) Unknown.
    return ClassifiedError(
        category="unknown",
        message=text,
        hint="Check backend logs for the full stack trace.",
    )
