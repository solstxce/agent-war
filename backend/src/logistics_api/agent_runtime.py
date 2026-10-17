"""Bounded ADK execution; no model or telemetry connections at import time."""
import argparse
import asyncio
import json

from google.adk.agents.run_config import RunConfig
from google.adk.apps import App
from google.adk.plugins.reflect_retry_tool_plugin import ReflectAndRetryToolPlugin
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

from logistics_api.agent import create_agent


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore")
    agent_tool_max_retries: int = Field(default=2, ge=0, le=5)
    agent_max_llm_calls: int = Field(default=12, ge=1, le=30)


class LogisticsRecoveryPlugin(ReflectAndRetryToolPlugin):
    """Recognize application errors returned inside successful MCP envelopes."""

    async def extract_error_from_result(self, *, tool, tool_args, tool_context, result):
        def find_error(value):
            if not isinstance(value, dict):
                return None
            if isinstance(value.get("error"), dict) and value["error"].get("retryable") is False:
                return None
            if value.get("error") or value.get("ok") is False or value.get("isError") or value.get("is_error"):
                return value
            for key in ("structuredContent", "structured_content"):
                if error := find_error(value.get(key)):
                    return error
            for block in value.get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    try:
                        if error := find_error(json.loads(block.get("text", ""))):
                            return error
                    except (ValueError, TypeError):
                        pass
            return None
        return find_error(result)


def create_app():
    settings = RuntimeSettings()
    return App(
        name="dispatcher",
        root_agent=create_agent(),
        plugins=[LogisticsRecoveryPlugin(max_retries=settings.agent_tool_max_retries)],
    )


async def run_prompt(prompt: str):
    from logistics_api.observability import configure_observability

    telemetry = configure_observability()
    settings = RuntimeSettings()
    sessions = InMemorySessionService()
    runner = Runner(app=create_app(), session_service=sessions)
    session = await sessions.create_session(app_name="dispatcher", user_id="local-dispatcher")
    response_received = False
    try:
        async for event in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
            run_config=RunConfig(max_llm_calls=settings.agent_max_llm_calls),
        ):
            if event.error_message:
                raise RuntimeError(f"Agent request failed: {event.error_message}")
            if event.is_final_response() and event.content:
                for part in event.content.parts or []:
                    if part.text:
                        response_received = True
                        print(part.text)
        if not response_received:
            raise RuntimeError("Agent ended without a final text response. Inspect tool and model configuration.")
    finally:
        await runner.close()
        if telemetry is not None:
            telemetry.flush()


def run():
    parser = argparse.ArgumentParser(description="Run one local dispatcher request (requires MCP and Gemini credentials).")
    parser.add_argument("prompt")
    args = parser.parse_args()
    asyncio.run(run_prompt(args.prompt))
