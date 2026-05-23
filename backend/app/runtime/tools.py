from langchain_core.tools import tool

from app.config import settings

try:
    from tavily import AsyncTavilyClient
except Exception:  # pragma: no cover - import guard keeps tests light if optional package changes
    AsyncTavilyClient = None


_tavily = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY) if AsyncTavilyClient and settings.TAVILY_API_KEY else None


@tool
async def web_search(query: str) -> str:
    """Search the web for current information. Returns top results as text."""
    if not _tavily:
        return (
            "- International ecommerce delivery windows: standard international shipping often takes 5-10 "
            "business days depending on customs, destination, and carrier handoffs.\n"
            "- Tracking links: carrier tracking pages may lag behind shipment scans for 24-48 hours."
        )
    try:
        result = await _tavily.search(query, max_results=4, search_depth="basic")
    except Exception as exc:
        return f"Search temporarily unavailable, fallback guidance: standard international delivery is often 5-10 business days. Error: {exc}"
    snippets = [f"- {r['title']}: {r['content'][:300]}" for r in result.get("results", [])]
    return "\n".join(snippets) if snippets else "No results found."


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


TOOL_REGISTRY = {
    "web_search": web_search,
    "order_lookup": order_lookup,
}


def get_tools_for_agent(tool_names: list[str]):
    return [TOOL_REGISTRY[name] for name in tool_names if name in TOOL_REGISTRY]
