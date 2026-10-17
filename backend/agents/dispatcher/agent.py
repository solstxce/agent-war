"""ADK CLI entrypoint. Start MCP before using this agent."""
from logistics_api.agent_runtime import create_app
from logistics_api.observability import configure_observability

telemetry = configure_observability()
app = create_app()
root_agent = app.root_agent
