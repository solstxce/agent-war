"""Explicit administrator setup and smoke test for a dedicated demo workspace."""

import argparse
import asyncio
import json

from fastapi import HTTPException
from google.cloud import firestore

from logistics_api.recovery import now, seed_state
from logistics_api.recovery_agents import run_recovery_agents
from logistics_api.recovery_api import get_recovery_service


def seed_demo(service, confirm_project=None, dispatcher_uid=None):
    store = service.store
    if store.mode == "firestore":
        if confirm_project != store.client.project:
            raise ValueError("Cloud seed requires --confirm-project matching the configured project.")
        root = store.root.get(timeout=10)
        if root.exists and not root.to_dict().get("agentwars_demo_workspace"):
            raise ValueError("Refusing to seed an existing unmarked workspace. Use a new dedicated demo workspace.")
        if any(store.snapshot()[kind] for kind in ("vehicles", "shipments", "incidents", "recovery_runs")):
            raise ValueError("Workspace already has data. Use an explicitly enabled demo reset instead.")
        if dispatcher_uid:
            if "/" in dispatcher_uid:
                raise ValueError("Invalid dispatcher UID")
            from firebase_admin import auth
            from logistics_api.firebase import get_firebase_app
            auth.get_user(dispatcher_uid, app=get_firebase_app())
        if not root.exists:
            store.root.create({"name": "AgentWars Recovery Demo", "agentwars_demo_workspace": True, "created_at": now()}, timeout=10)

    def change(state):
        if any(state[kind] for kind in state):
            raise ValueError("Refusing to overwrite existing data. Use demo reset explicitly.")
        seed_state(state, False)

    store.mutate(change)
    if dispatcher_uid and store.mode == "firestore":
        batch = store.client.batch()
        batch.set(store.root.collection("members").document(dispatcher_uid), {"role": "dispatcher", "created_at": now()})
        batch.set(store.client.collection("users").document(dispatcher_uid),
                  {"workspace_ids": firestore.ArrayUnion([store.root.id])}, merge=True)
        batch.commit(timeout=10)
    return {"seeded": True, "data_mode": store.mode, "storage_notice": store.notice,
            "vehicles": 8, "pending_shipments": 20}


def run():
    parser = argparse.ArgumentParser(description="Admin-only demo setup and ADK recovery smoke test")
    commands = parser.add_subparsers(dest="command", required=True)
    seed = commands.add_parser("seed", help="Seed only a new, empty dedicated workspace")
    seed.add_argument("--confirm-project")
    seed.add_argument("--dispatcher-uid", help="Optional existing Firebase user to grant demo dispatcher access")
    reset = commands.add_parser("reset", help="Reset only an explicitly enabled dedicated demo workspace")
    reset.add_argument("--confirm-project")
    reset.add_argument("--fresh-policy", action="store_true")
    recovery = commands.add_parser("run", help="Simulate and resolve using the configured agents and storage")
    recovery.add_argument("--scenario", choices=["A", "B"], required=True)
    args = parser.parse_args()
    try:
        service = get_recovery_service()
        if args.command == "seed":
            result = seed_demo(service, args.confirm_project, args.dispatcher_uid)
        elif args.command == "reset":
            if service.store.mode == "firestore" and args.confirm_project != service.store.client.project:
                raise ValueError("Cloud reset requires --confirm-project matching the configured project.")
            dashboard = service.reset(not args.fresh_policy)
            result = {"reset": True, "data_mode": dashboard["data_mode"], "storage_notice": dashboard["storage_notice"],
                      "policy": dashboard["policy"]}
        else:
            incident = service.simulate(args.scenario)
            before = service.store.snapshot()
            run_result = asyncio.run(run_recovery_agents(service, incident["incident_id"]))
            after = service.store.snapshot()
            ids = incident["pending_shipment_ids"]
            selected = run_result["selected_vehicle_id"]
            if selected:
                if (sorted(run_result["reassigned_shipment_ids"]) != sorted(ids)
                        or any(after["shipments"][sid]["assigned_vehicle_id"] != selected for sid in ids)):
                    raise RuntimeError("Read-after-write verification failed")
            elif before["shipments"] != after["shipments"]:
                raise RuntimeError("Escalation unexpectedly changed shipment assignments")
            result = {key: run_result[key] for key in (
                "run_id", "incident_id", "outcome", "selected_vehicle_id", "distance_meters", "duration_seconds",
                "estimate_source", "estimate_notice", "reassigned_shipment_ids", "decision_reason", "policy_version",
                "data_mode", "storage_notice")}
            result["agent_mode"] = run_result["agent_execution"]["mode"]
            result["model"] = run_result["agent_execution"]["model"]
            result["assignments_read_back_verified"] = True
        print(json.dumps(result, indent=2))
    except (ValueError, HTTPException) as exc:
        parser.exit(1, f"Demo command rejected: {exc.detail if isinstance(exc, HTTPException) else exc}\n")
    except Exception as exc:
        # Provider exceptions may include secrets; never print request bodies or raw URLs.
        parser.exit(1, f"Demo command failed ({type(exc).__name__}). Check backend credentials and service availability.\n")


if __name__ == "__main__":
    run()
