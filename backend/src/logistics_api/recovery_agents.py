"""ADK recovery orchestration; all decisions and mutations remain in the service."""

import asyncio
import copy
import json

from fastapi import HTTPException

from google import genai
from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig
from google.adk.apps import App
from google.adk.models import BaseLlm
from google.adk.models.google_llm import Gemini
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

from logistics_api.config import get_settings


class _ScriptedModel(BaseLlm):
    """Emit actual ADK calls, without claiming to perform Gemini inference."""

    role: str

    async def generate_content_async(self, llm_request, stream=False):
        scripts = {
            "commander": ["fleet_analyst", "recovery_planner", "execute_recovery"],
            "analyst": ["analyze_fleet"],
            "planner": ["plan_recovery"],
        }
        responses = [
            part.function_response
            for content in llm_request.contents
            for part in (content.parts or [])
            if part.function_response is not None
        ]
        completed = {response.name for response in responses}
        next_call = next(
            (name for name in scripts[self.role] if name not in completed), None
        )
        if next_call:
            args = (
                {"request": "Run your recovery tool for the bound incident."}
                if next_call in {"fleet_analyst", "recovery_planner"}
                else {}
            )
            part = types.Part.from_function_call(name=next_call, args=args)
        else:
            text = (
                "Scripted ADK demo completed; use the persisted execution result."
                if self.role == "commander"
                else json.dumps(responses[-1].response)
            )
            part = types.Part.from_text(text=text)
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


class _FallbackGemini(BaseLlm):
    """Try fallback models only for quota or temporary availability failures."""

    def __init__(self, model_names, api_key):
        super().__init__(model=model_names[0])
        self.model_names = list(dict.fromkeys(model_names))
        self.api_key = api_key
        self.models_attempted = []

    @staticmethod
    def _is_available_error(exc):
        text = f"{type(exc).__name__} {exc}".upper()
        status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        return status in {404, 429, 449, 500, 502, 503, 504} or any(
            marker in text for marker in ("RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE_EXCEEDED", "RATE_LIMIT")
        )

    async def generate_content_async(self, llm_request, stream=False):
        for model_name in self.model_names:
            self.models_attempted.append(model_name)
            client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
            )
            model = Gemini(model=model_name, client=client)
            yielded = False
            try:
                async for response in model.generate_content_async(llm_request, stream=stream):
                    yielded = True
                    yield response
                return
            except Exception as exc:
                if yielded or not self._is_available_error(exc) or model_name == self.model_names[-1]:
                    raise


async def run_recovery_agents(service, incident_id: str) -> dict:
    """Run three ADK roles and return only the service's persisted execution."""
    settings = get_settings()
    mode = "gemini" if settings.google_api_key else "adk_scripted_demo"
    metadata = {
        "mode": mode,
        "model": settings.gemini_model if mode == "gemini" else "adk-scripted-demo",
        "model_fallbacks": settings.gemini_model_fallbacks if mode == "gemini" else [],
        "label": "Gemini recovery agents" if mode == "gemini" else "Scripted ADK demo (not Gemini)",
        "events": [],
    }
    tasks = {}
    results = {}

    class EventRecorder(BasePlugin):
        async def on_event_callback(self, *, invocation_context, event):
            metadata["events"].append({
                "author": event.author,
                "tool_calls": [call.name for call in event.get_function_calls()],
            })
            if event.error_message:
                raise RuntimeError(f"ADK {event.author}: {event.error_message}")

    def model(role):
        if mode == "adk_scripted_demo":
            return _ScriptedModel(model="adk-scripted-demo", role=role)
        try:
            return _FallbackGemini(
                [settings.gemini_model, *settings.gemini_model_fallbacks], settings.google_api_key
            )
        except Exception as exc:
            raise RuntimeError(f"Gemini recovery model initialization failed: {exc}") from exc

    async def call_service(phase):
        if phase not in tasks:
            if phase == "plan" and "analyze" not in results:
                raise RuntimeError("Recovery order violation: analyze must complete before plan.")
            if phase == "execute" and "plan" not in results:
                raise RuntimeError("Recovery order violation: plan must complete before execute.")

            async def invoke():
                if phase == "analyze":
                    result = await asyncio.to_thread(service.analyze, incident_id)
                elif phase == "plan":
                    result = await asyncio.to_thread(
                        service.plan, incident_id, results["analyze"]
                    )
                else:
                    result = await asyncio.to_thread(
                        service.execute, incident_id, results["analyze"],
                        results["plan"], copy.deepcopy(metadata),
                    )
                results[phase] = result
                return result

            # Cache tasks, including failures, before yielding to concurrent tool calls.
            tasks[phase] = asyncio.create_task(invoke())
        return await asyncio.shield(tasks[phase])

    async def analyze_fleet() -> dict:
        """Analyze the bound incident using deterministic fleet filtering and maps."""
        return await call_service("analyze")

    async def plan_recovery() -> dict:
        """Rank recovery options from the completed server-side analysis."""
        return await call_service("plan")

    async def execute_recovery() -> dict:
        """Transactionally revalidate and execute the server-side recovery plan."""
        return await call_service("execute")

    model_instances = {}
    analyst = LlmAgent(
        name="fleet_analyst",
        description="FleetAnalyst: deterministic fleet analysis and maps evidence.",
        model=model_instances.setdefault("analyst", model("analyst")),
        instruction="You are FleetAnalyst. Call analyze_fleet, then return its result as JSON. Do not invent candidates or evidence.",
        tools=[analyze_fleet],
    )
    planner = LlmAgent(
        name="recovery_planner",
        description="RecoveryPlanner: deterministic recovery ranking.",
        model=model_instances.setdefault("planner", model("planner")),
        instruction="You are RecoveryPlanner. Call plan_recovery, then return its result as JSON. The service owns ranking; do not supply candidate IDs.",
        tools=[plan_recovery],
    )
    commander = LlmAgent(
        name="IncidentCommander",
        model=model_instances.setdefault("commander", model("commander")),
        instruction=(
            "Call fleet_analyst first and wait for completion. Then call "
            "recovery_planner and wait for completion. Then call execute_recovery. "
            "Never parallelize these stages. All tools are bound to the incident "
            "server-side. Never invent IDs, rankings, or success. Report only tool results."
        ),
        tools=[AgentTool(agent=analyst), AgentTool(agent=planner), execute_recovery],
    )
    sessions = InMemorySessionService()
    runner = Runner(app=App(name="recovery", root_agent=commander,
                           plugins=[EventRecorder(name="recovery_events")]), session_service=sessions)
    try:
        try:
            async with asyncio.timeout(90):
                session = await sessions.create_session(app_name="recovery", user_id="dispatcher")
                async for event in runner.run_async(
                    user_id=session.user_id,
                    session_id=session.id,
                    new_message=types.Content(
                        role="user",
                        parts=[types.Part.from_text(text="Recover the server-bound incident now.")],
                    ),
                    run_config=RunConfig(max_llm_calls=16),
                ):
                    if event.error_message:
                        raise RuntimeError(event.error_message)
                if "execute" not in results:
                    raise RuntimeError("Agent ended without calling execute_recovery.")
        finally:
            await runner.close()
    except Exception as exc:
        # A cancelled await does not stop a transaction running in a worker thread.
        # Settle any started execution before claiming that recovery failed.
        if "execute" in tasks:
            try:
                await asyncio.shield(tasks["execute"])
            except Exception as execution_error:
                if isinstance(execution_error, HTTPException):
                    raise execution_error
                raise RuntimeError(f"Recovery execution failed ({mode}): {execution_error}") from execution_error
        if "execute" in results:
            result = dict(results["execute"])
            result["warnings"] = [
                *result.get("warnings", []),
                "Recovery was persisted, but the ADK final response failed. Use this persisted result; do not repeat assignments.",
            ]
            return result
        for task in tasks.values():
            if task.done() and not task.cancelled() and isinstance(task.exception(), HTTPException):
                raise task.exception()
        raise RuntimeError(f"Recovery agents failed ({mode}): {type(exc).__name__}: {exc}") from exc
    return results["execute"]
