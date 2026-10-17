"""Agent factory. Construction does not invoke a model or connect to MCP."""

from logistics_api.config import get_settings


def create_agent():
    from google.adk.agents import Agent
    from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
    from google.adk.models.google_llm import Gemini
    from google import genai
    from google.genai import types

    settings = get_settings()
    if not settings.google_api_key:
        raise RuntimeError("Set GOOGLE_API_KEY before creating the Gemini agent.")
    return Agent(
        name="delivery_exception_agent",
        description="Delivery exception assistant setup scaffold",
        model=Gemini(
            model=settings.gemini_model,
            client=genai.Client(
                api_key=settings.google_api_key,
                http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=2)),
            ),
        ),
        instruction=(
            "You assist a delivery dispatcher. Only report facts returned by tools. "
            "Use get_service_status for setup questions, geocode_address for addresses, "
            "and compute_route for travel estimates. Ask for missing or ambiguous locations. "
            "Read errors carefully: correct invalid arguments, but do not repeatedly retry "
            "missing credentials, disabled services, or denied permissions. Report blockers. "
            "If an error has retryable=false, stop and explain the needed correction to the user. "
            "Never invent coordinates, route results, delivery records, assignments, or success. "
            "A successful route lookup does not mean a delivery was dispatched. "
            "Shipment management, reassignment, and learning are not implemented yet."
        ),
        tools=[McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=settings.logistics_mcp_url),
            tool_filter=["get_service_status", "geocode_address", "compute_route"],
        )],
    )
