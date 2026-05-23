import asyncio
import ast
import logging
import operator
import re

from langchain_core.tools import tool

from app.config import settings

logger = logging.getLogger(__name__)

try:
    from tavily import AsyncTavilyClient
except Exception:  # pragma: no cover - import guard keeps tests light if optional package changes
    AsyncTavilyClient = None

try:
    from ddgs import DDGS
except Exception:  # pragma: no cover - optional search dependency
    try:
        from duckduckgo_search import DDGS  # legacy fallback
    except Exception:
        DDGS = None


_tavily = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY) if AsyncTavilyClient and settings.TAVILY_API_KEY else None

_DDG_BACKENDS = ("auto", "lite", "html")


def _fallback_search_result() -> str:
    return (
        "- International ecommerce delivery windows: standard international shipping often takes 5-10 "
        "business days depending on customs, destination, and carrier handoffs.\n"
        "- Tracking links: carrier tracking pages may lag behind shipment scans for 24-48 hours."
    )


def _format_ddg_results(results: list[dict]) -> str:
    snippets = []
    for result in results:
        title = result.get("title") or result.get("href") or "DuckDuckGo result"
        body = result.get("body") or ""
        href = result.get("href") or ""
        snippets.append(f"- {title}: {body[:300]} ({href})")
    return "\n".join(snippets)


def _duckduckgo_search(query: str) -> str:
    if DDGS is None:
        logger.warning("ddgs package missing; using fallback search result")
        return _fallback_search_result()
    for backend in _DDG_BACKENDS:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=4, backend=backend))
        except TypeError:
            # legacy duckduckgo_search may not accept backend kwarg
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=4))
        except Exception as exc:
            logger.warning("DDG backend=%s failed for query=%r: %s", backend, query, exc)
            continue
        if results:
            return _format_ddg_results(results)
    logger.info("DDG returned no results across backends for query=%r; using fallback", query)
    return _fallback_search_result()


@tool
async def web_search(query: str) -> str:
    """Search the web for current information. Returns top results as text."""
    if _tavily:
        try:
            result = await _tavily.search(query, max_results=4, search_depth="basic")
            snippets = [f"- {r['title']}: {r['content'][:300]}" for r in result.get("results", [])]
            if snippets:
                return "\n".join(snippets)
            logger.info("Tavily returned no results for query=%r; trying DDG", query)
        except Exception as exc:
            logger.warning("Tavily search failed for query=%r: %s", query, exc)
    try:
        return await asyncio.to_thread(_duckduckgo_search, query)
    except Exception as exc:
        logger.exception("DDG search crashed for query=%r", query)
        return f"Search temporarily unavailable. Fallback guidance:\n{_fallback_search_result()}\nError: {exc}"


_MOCK_ORDERS = {
    "ORD-1042": {
        "status": "in_transit",
        "carrier": "DHL",
        "tracking_number": "DHL-7782-9123",
        "estimated_delivery": "2026-05-28",
        "destination": "Coimbatore, IN",
        "items": [{"name": "Wireless Headphones", "qty": 1}],
    },
    "ORD-2055": {
        "status": "delivered",
        "carrier": "FedEx",
        "tracking_number": "FX-1129-4471",
        "delivered_at": "2026-05-19",
        "destination": "Bangalore, IN",
        "items": [{"name": "Mechanical Keyboard", "qty": 1}],
    },
}


@tool
async def order_lookup(order_id: str) -> str:
    """Look up an order by its ID. Returns status, carrier, tracking, items."""
    normalized = order_id.strip().upper()
    order = _MOCK_ORDERS.get(normalized)
    if not order:
        return f"No order found with ID {order_id}."
    return f"Order {normalized}: {order}"


@tool
async def sql_query(query: str) -> str:
    """Run a safe read-only SQL query against demo business tables."""
    normalized = " ".join(query.lower().split())
    if not normalized.startswith("select"):
        return "Only read-only SELECT queries are allowed in the demo SQL tool."
    if "orders" in normalized:
        return (
            "orders rows: "
            "[{id: 'ORD-1042', status: 'in_transit', carrier: 'DHL', destination: 'Coimbatore, IN'}, "
            "{id: 'ORD-2055', status: 'delivered', carrier: 'FedEx', destination: 'Bangalore, IN'}]"
        )
    if "customers" in normalized:
        return "customers rows: [{id: 'CUS-88', tier: 'gold', open_tickets: 1}, {id: 'CUS-41', tier: 'standard', open_tickets: 0}]"
    return "Available demo tables: orders, customers."


_CALCULATOR_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_numeric_expression(node):
    if isinstance(node, ast.Expression):
        return _eval_numeric_expression(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _CALCULATOR_OPERATORS:
        return _CALCULATOR_OPERATORS[type(node.op)](_eval_numeric_expression(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _CALCULATOR_OPERATORS:
        left = _eval_numeric_expression(node.left)
        right = _eval_numeric_expression(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 12:
            raise ValueError("Exponent too large for demo calculator.")
        return _CALCULATOR_OPERATORS[type(node.op)](left, right)
    raise ValueError("Only numeric arithmetic is allowed.")


@tool
async def calculator(expression: str) -> str:
    """Evaluate a safe arithmetic expression with +, -, *, /, %, //, **, and parentheses."""
    if not expression or len(expression) > 200:
        return "Calculator expression must be between 1 and 200 characters."
    try:
        parsed = ast.parse(expression, mode="eval")
        result = _eval_numeric_expression(parsed)
    except Exception as exc:
        return f"Calculator error: {exc}"
    return f"{expression} = {result}"


@tool
async def send_email(to: str, subject: str, body: str) -> str:
    """Prepare a demo outbound email. This does not send real email."""
    email_pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    if not re.match(email_pattern, to):
        return f"Email draft rejected: '{to}' is not a valid email address."
    if not subject.strip():
        return "Email draft rejected: subject is required."
    if not body.strip():
        return "Email draft rejected: body is required."
    return (
        "Demo email prepared but not sent. "
        f"To: {to}. Subject: {subject.strip()[:120]}. Body preview: {body.strip()[:240]}"
    )


TOOL_REGISTRY = {
    "web_search": web_search,
    "order_lookup": order_lookup,
    "sql_query": sql_query,
    "send_email": send_email,
    "calculator": calculator,
}


def get_tools_for_agent(tool_names: list[str]):
    return [TOOL_REGISTRY[name] for name in tool_names if name in TOOL_REGISTRY]
