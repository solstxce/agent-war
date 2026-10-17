"""Local-only MCP setup tools over Streamable HTTP."""

from mcp.server.fastmcp import FastMCP

from logistics_api.config import configuration_status
from logistics_api.maps import compute_route, geocode_address

mcp = FastMCP("delivery-logistics", host="127.0.0.1", port=8001)
mcp.tool()(geocode_address)
mcp.tool()(compute_route)


@mcp.tool()
def get_service_status() -> dict:
    """Read configuration presence without exposing secrets or calling cloud services."""
    return {"stage": "setup", "integrations": configuration_status(), "operations_available": False}


def run() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    run()
