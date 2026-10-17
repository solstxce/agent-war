"""Recovery endpoints preserving workspace membership for Firestore access."""

import asyncio
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from google.auth.exceptions import DefaultCredentialsError
from pydantic import BaseModel, ConfigDict

from logistics_api.config import get_settings
from logistics_api.firebase import get_firestore_client
from logistics_api.operations import bearer, current_user, member
from logistics_api.recovery import RecoveryService, seed_state
from logistics_api.recovery_agents import run_recovery_agents
from logistics_api.recovery_maps import RouteMatrix
from logistics_api.recovery_store import FirestoreStore, LocalStore

router = APIRouter(prefix="/api", tags=["recovery"])


@lru_cache
def get_recovery_service():
    settings = get_settings()
    local = settings.data_mode == "local_demo"
    if settings.data_mode == "auto":
        local = not (settings.project_id or settings.google_application_credentials)
        if not local and not settings.google_application_credentials and not settings.firestore_emulator_host:
            import google.auth
            try:
                google.auth.default()
            except DefaultCredentialsError:
                local = True
    if local:
        if settings.app_environment != "development":
            raise HTTPException(503, "Local demo storage is only allowed in development")
        store = LocalStore(Path(__file__).resolve().parents[2] / ".local" / "recovery.sqlite3")
        store.mutate(lambda state: seed_state(state, False) if not state["vehicles"] else None)
    else:
        if not settings.project_id:
            raise HTTPException(503, "Configure GOOGLE_CLOUD_PROJECT for Firestore mode")
        store = FirestoreStore(get_firestore_client(), settings.recovery_workspace_id, bool(settings.firestore_emulator_host))
    return RecoveryService(store, RouteMatrix(settings), settings)


def recovery_access(credentials=Depends(bearer), service=Depends(get_recovery_service)):
    if service.store.mode == "firestore":
        user = current_user(credentials)
        member(service.settings.recovery_workspace_id, user, service.store.client)
    return service


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Simulation(RequestModel):
    scenario: Literal["A", "B"] = "A"


class Feedback(RequestModel):
    rating: Literal["good", "needs_improvement"]
    reason: Literal["too_far", "poor_eta", "other"] | None = None


class Reset(RequestModel):
    preserve_policy: bool = True


@router.get("/dashboard")
def dashboard(service=Depends(recovery_access)):
    return service.dashboard()


@router.post("/incidents/simulate", status_code=201)
def simulate(body: Simulation, service=Depends(recovery_access)):
    return service.simulate(body.scenario)


@router.post("/incidents/{incident_id}/resolve")
async def resolve(incident_id: str, service=Depends(recovery_access)):
    state = await asyncio.to_thread(service.store.snapshot)
    await asyncio.to_thread(service.context, state, incident_id)
    try:
        return await run_recovery_agents(service, incident_id)
    except HTTPException:
        raise
    except RuntimeError as exc:
        import logging
        logging.getLogger(__name__).warning("Recovery agents failed for %s: %s", incident_id, type(exc).__name__)
        raise HTTPException(502, "ADK workflow failed or execution conflicted. Refresh dashboard before retrying; check model and API configuration.") from None


@router.post("/recovery-runs/{run_id}/feedback")
def feedback(run_id: str, body: Feedback, service=Depends(recovery_access)):
    return service.feedback(run_id, body.rating, body.reason)


@router.post("/demo/reset")
def reset(body: Reset, service=Depends(recovery_access)):
    return service.reset(body.preserve_policy)
