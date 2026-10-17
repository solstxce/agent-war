"""Deterministic same-route recovery rules. Agents cannot choose arbitrary IDs."""

import math
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def coordinates_valid(location):
    if not isinstance(location, dict):
        return False
    lat, lon = location.get("latitude"), location.get("longitude")
    return (
        isinstance(lat, (int, float)) and not isinstance(lat, bool)
        and isinstance(lon, (int, float)) and not isinstance(lon, bool)
        and math.isfinite(lat) and math.isfinite(lon)
        and -90 <= lat <= 90 and -180 <= lon <= 180
    )


def pending_for(state, vehicle_id):
    return sorted(s["shipment_id"] for s in state["shipments"].values()
                  if s.get("assigned_vehicle_id") == vehicle_id and s.get("status") in {"pending", "in_transit"})


def audit(state, action, **details):
    key = identifier("audit")
    state["audit_logs"][key] = {"audit_id": key, "action": action, "timestamp": now(), **details}


def default_policy():
    return {"version": 1, "distance_weight": 0.7, "eta_weight": 0.3,
            "explanation": "Shortest distance always wins; ETA breaks distance ties. Preferences refine ETA tie scores only."}


def location_rejection(vehicle, max_age):
    if not coordinates_valid(vehicle.get("current_location")):
        return "Invalid or missing location"
    try:
        stamp = vehicle["last_location_update"]
        stamp = datetime.fromisoformat(stamp.replace("Z", "+00:00")) if isinstance(stamp, str) else stamp
        age = (datetime.now(timezone.utc) - stamp).total_seconds()
        if not 0 <= age <= max_age:
            return "Stale or future location timestamp"
    except (KeyError, ValueError, TypeError, AttributeError):
        return "Missing or invalid location timestamp"
    return None


def fleet_snapshot(state, route_id):
    fields = ("vehicle_id", "route_id", "status", "current_location", "last_location_update",
              "parcel_capacity", "assigned_shipment_ids")
    return {vid: {field: vehicle.get(field) for field in fields}
            for vid, vehicle in state["vehicles"].items() if vehicle.get("route_id") == route_id}


def seed_state(state, preserve_policy=True):
    policy = state["policy_settings"].get("recovery", default_policy()) if preserve_policy else default_policy()
    for collection in state.values():
        collection.clear()
    state["policy_settings"]["recovery"] = policy
    specs = [
        ("V-101", "R-1", 10, "operational", 51.5074, -0.1278, 6),
        ("V-204", "R-1", 12, "operational", 51.509, -0.13, 2),
        ("V-205", "R-1", 16, "operational", 51.53, -0.16, 0),
        ("V-201", "R-2", 18, "operational", 51.52, -0.1, 12),
        ("V-301", "R-2", 6, "operational", 51.521, -0.1, 0),
        ("V-302", "R-2", 30, "unavailable", 51.522, -0.1, 0),
        ("V-303", "R-2", 30, "operational", 51.523, -0.1, 0),
        ("V-999", "R-OTHER", 99, "operational", 51.5074, -0.1278, 0),
    ]
    for vid, route, capacity, status, lat, lon, count in specs:
        ids = [f"S-{vid[2:]}-{n:02d}" for n in range(1, count + 1)]
        state["vehicles"][vid] = {
            "vehicle_id": vid, "status": status, "route_id": route, "parcel_capacity": capacity,
            "current_location": {"latitude": lat, "longitude": lon}, "assigned_shipment_ids": ids,
            "last_location_update": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat() if vid == "V-303" else now(),
        }
        for sid in ids:
            state["shipments"][sid] = {"shipment_id": sid, "status": "pending", "assigned_vehicle_id": vid,
                                        "route_id": route, "delivery_location": {"latitude": lat + 0.01, "longitude": lon}}
    audit(state, "demo_reset", policy_preserved=preserve_policy)


class RecoveryService:
    def __init__(self, store, router, settings):
        self.store, self.router, self.settings = store, router, settings

    def reset(self, preserve_policy=True):
        if self.store.mode != "local_demo" and not getattr(self.store, "emulator", False):
            allowed = (self.settings.app_environment == "development" and self.settings.allow_cloud_demo_reset
                       and self.settings.routing_mode == "synthetic_demo")
            if not allowed or not (self.store.root.get(timeout=10).to_dict() or {}).get("agentwars_demo_workspace"):
                raise HTTPException(403, "Cloud reset requires an explicitly enabled, marked, synthetic-demo workspace.")
        self.store.mutate(lambda state: seed_state(state, preserve_policy))
        return self.dashboard()

    def dashboard(self):
        state = self.store.snapshot()
        return {
            "data_mode": self.store.mode, "storage_notice": self.store.notice,
            "agent_mode": "gemini" if self.settings.google_api_key else "adk_scripted_demo",
            "routing_mode": self.settings.routing_mode,
            "routing_notice": "Synthetic demo distance and ETA; no Maps calls or real driving estimates." if self.settings.routing_mode == "synthetic_demo" else "Google Maps evidence when configured; straight-line fallback is local-demo only.",
            **{kind: list(state[kind].values()) for kind in state if kind != "policy_settings"},
            "policy": state["policy_settings"].get("recovery", default_policy()),
            "counts": {
                "operational_vehicles": sum(v.get("status") == "operational" for v in state["vehicles"].values()),
                "broken_down_vehicles": sum(v.get("status") == "broken_down" for v in state["vehicles"].values()),
                "open_incidents": sum(i.get("status") == "open" for i in state["incidents"].values()),
                "pending_shipments": sum(s.get("status") in {"pending", "in_transit"} for s in state["shipments"].values()),
            },
        }

    def simulate(self, scenario):
        vid = "V-101" if scenario == "A" else "V-201"

        def change(state):
            for incident in state["incidents"].values():
                if incident["broken_vehicle_id"] == vid and incident["status"] == "open":
                    return incident
            vehicle = state["vehicles"].get(vid)
            if not vehicle:
                raise HTTPException(404, "Demo vehicle not found. Reset a local/emulator workspace first.")
            if vehicle["status"] != "operational":
                raise HTTPException(409, "Vehicle is already broken down; reset the demo before repeating this scenario.")
            ids = pending_for(state, vid)
            if not ids or not coordinates_valid(vehicle.get("current_location")):
                raise HTTPException(409, "Breakdown requires pending shipments and a valid stored location.")
            if location_rejection(vehicle, self.settings.location_max_age_seconds):
                raise HTTPException(409, "Breakdown requires a recent stored location; refresh telemetry before reporting.")
            key = identifier("INC")
            incident = {"incident_id": key, "broken_vehicle_id": vid,
                        "breakdown_location": dict(vehicle["current_location"]), "pending_shipment_ids": ids,
                        "reason": "Simulated engine failure", "status": "open", "selected_recovery_vehicle_id": None,
                        "created_at": now(), "resolved_at": None}
            vehicle["status"] = "broken_down"
            state["incidents"][key] = incident
            audit(state, "breakdown_reported", incident_id=key, vehicle_id=vid)
            return incident

        return self.store.mutate(change)

    def context(self, state, incident_id):
        incident = state["incidents"].get(incident_id)
        if not incident:
            raise HTTPException(404, "Incident not found")
        if incident["status"] != "open":
            raise HTTPException(409, "Incident already completed; assignments were not executed again.")
        broken = state["vehicles"].get(incident["broken_vehicle_id"])
        if not broken or broken.get("status") != "broken_down" or not broken.get("route_id"):
            raise HTTPException(409, "Broken vehicle state is inconsistent; dispatcher review required.")
        if broken.get("current_location") != incident["breakdown_location"]:
            raise HTTPException(409, "Breakdown coordinates changed; dispatcher must correct the incident location before recovery.")
        pending = pending_for(state, broken["vehicle_id"])
        if not pending or pending != sorted(incident["pending_shipment_ids"]):
            raise HTTPException(409, "Pending assignments changed; dispatcher must review the incident.")
        if len(set(broken["assigned_shipment_ids"])) != len(broken["assigned_shipment_ids"]) or set(broken["assigned_shipment_ids"]) != set(pending):
            raise HTTPException(409, "Broken vehicle assignment ledger is inconsistent.")
        for sid in pending:
            if state["shipments"][sid].get("route_id") != broken["route_id"]:
                raise HTTPException(409, "Shipment route conflicts with the broken vehicle route.")
            if any(sid in v.get("assigned_shipment_ids", []) for vid, v in state["vehicles"].items() if vid != broken["vehicle_id"]):
                raise HTTPException(409, "Conflicting shipment assignment detected.")
        return incident, broken, pending

    def rejection(self, state, vehicle, broken, count):
        if vehicle.get("vehicle_id") == broken["vehicle_id"]:
            return "Broken vehicle itself"
        if vehicle.get("route_id") != broken["route_id"]:
            return "Different route (never routed)"
        if vehicle.get("status") != "operational":
            return "Vehicle unavailable"
        if reason := location_rejection(vehicle, self.settings.location_max_age_seconds):
            return reason
        assigned = vehicle.get("assigned_shipment_ids", [])
        if (not isinstance(assigned, list) or not all(isinstance(sid, str) for sid in assigned)
                or len(set(assigned)) != len(assigned) or set(assigned) != set(pending_for(state, vehicle["vehicle_id"]))):
            return "Inconsistent vehicle assignment ledger"
        if any(sid in other.get("assigned_shipment_ids", []) for sid in assigned
               for vid, other in state["vehicles"].items() if vid != vehicle["vehicle_id"]):
            return "Conflicting vehicle assignment ledger"
        capacity = vehicle.get("parcel_capacity")
        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity - len(assigned) < count:
            return f"Insufficient spare parcel capacity for all {count} shipments"
        return None

    def analyze(self, incident_id):
        state = self.store.snapshot()
        incident, broken, pending = self.context(state, incident_id)
        evidence, eligible = [], []
        for vid, vehicle in sorted(state["vehicles"].items()):
            reason = self.rejection(state, vehicle, broken, len(pending))
            evidence.append({"vehicle_id": vid, "eligible": reason is None, "rejection_reason": reason})
            if reason is None:
                eligible.append(vehicle)
        # The Routes API never sees rejected vehicles, especially other routes.
        routes = self.router.matrix(eligible, incident["breakdown_location"]) if eligible and coordinates_valid(incident["breakdown_location"]) else {}
        for item in evidence:
            if item["eligible"]:
                item.update(routes.get(item["vehicle_id"], {"route_status": "unavailable", "source": "unavailable"}))
                if self.store.mode != "local_demo" and item.get("source") == "straight_line":
                    item.update(route_status="unavailable", error_reason="Road routing is required for cloud assignments. Straight-line recovery is local-demo only.")
        return {"incident_id": incident_id, "route_id": broken["route_id"], "pending_shipment_ids": pending,
                "breakdown_location": incident["breakdown_location"], "candidates_evaluated": evidence,
                "analyzed_at": now(), "fleet_snapshot": fleet_snapshot(state, broken["route_id"]),
                "policy": state["policy_settings"].get("recovery", default_policy())}

    def plan(self, incident_id, analysis):
        if analysis["incident_id"] != incident_id:
            raise HTTPException(409, "Analysis incident mismatch")
        eligible = [v for v in analysis["candidates_evaluated"] if v["eligible"] and v.get("route_status") == "ok"]
        policy = analysis["policy"]

        def rank(v):
            # Distance is lexicographic, never traded away for a faster ETA.
            # Bounded learned preference weights scale ETA tie scores, not eligibility.
            eta_score = (v.get("duration_seconds") or 0) * policy["eta_weight"] / policy["distance_weight"]
            return v["distance_meters"], eta_score, v["vehicle_id"]

        best = min(eligible, key=rank) if eligible else None
        if best:
            if best["source"] == "google_maps_routes":
                reason = "Shortest eligible same-route driving distance; ETA breaks ties."
            elif best["source"] == "synthetic_demo":
                reason = "Shortest eligible same-route synthetic demo distance; synthetic ETA breaks ties. Mock evidence, not live road routing."
            else:
                reason = "Nearest eligible same-route straight-line estimate (not road distance; no driving ETA available)."
        else:
            reason = "No eligible same-route vehicle can carry all pending shipments, or none has a successful route calculation. Dispatcher notification recorded; no shipments reassigned."
        return {"selected_vehicle_id": best["vehicle_id"] if best else None, "decision_reason": reason,
                "policy_version": policy["version"], "ranking_rule": "distance_then_eta_then_vehicle_id"}

    def execute(self, incident_id, analysis, plan, agent_execution):
        # Plan is recomputed in Python, not accepted from model-generated text.
        if self.plan(incident_id, analysis) != plan:
            raise HTTPException(409, "Recovery plan failed deterministic validation")
        run_id = identifier("RUN")

        def change(state):
            incident, broken, pending = self.context(state, incident_id)
            if (broken["route_id"] != analysis["route_id"] or pending != analysis["pending_shipment_ids"]
                    or incident["breakdown_location"] != analysis["breakdown_location"]):
                raise HTTPException(409, "Incident changed during analysis; run recovery again.")
            if fleet_snapshot(state, broken["route_id"]) != analysis["fleet_snapshot"]:
                raise HTTPException(409, "Same-route fleet changed during analysis; calculate routes again.")
            analyzed_at = datetime.fromisoformat(analysis["analyzed_at"])
            if (datetime.now(timezone.utc) - analyzed_at).total_seconds() > 120:
                raise HTTPException(409, "Routing analysis expired; run recovery again.")
            selected = plan["selected_vehicle_id"]
            evidence = next((v for v in analysis["candidates_evaluated"] if v["vehicle_id"] == selected), {})
            if selected:
                vehicle = state["vehicles"].get(selected)
                reason = self.rejection(state, vehicle, broken, len(pending)) if vehicle else "Vehicle removed"
                if reason:
                    raise HTTPException(409, f"Selected vehicle is no longer eligible: {reason}. Run recovery again.")
                # Recheck origin: road evidence must still refer to the stored vehicle location.
                if vehicle["current_location"] != evidence.get("origin_location"):
                    raise HTTPException(409, "Selected vehicle location changed; calculate routes again.")
                vehicle["assigned_shipment_ids"].extend(pending)
                broken["assigned_shipment_ids"] = []
                for sid in pending:
                    state["shipments"][sid]["assigned_vehicle_id"] = selected
                    audit(state, "shipment_reassigned", shipment_id=sid, from_vehicle_id=broken["vehicle_id"],
                          to_vehicle_id=selected, incident_id=incident_id, run_id=run_id)
                outcome = "resolved"
            else:
                # A newly eligible candidate makes an old escalation proposal stale.
                before_eligible = {v["vehicle_id"] for v in analysis["candidates_evaluated"] if v["eligible"]}
                current_eligible = {vid for vid, v in state["vehicles"].items() if self.rejection(state, v, broken, len(pending)) is None}
                if before_eligible != current_eligible:
                    raise HTTPException(409, "Fleet eligibility changed; calculate recovery again.")
                outcome = "manual_intervention_required"
                audit(state, "dispatcher_notification", incident_id=incident_id, run_id=run_id,
                      notification_type="simulated", reason=plan["decision_reason"])
            incident.update(status=outcome, selected_recovery_vehicle_id=selected, resolved_at=now())
            run = {"run_id": run_id, "incident_id": incident_id, "candidates_evaluated": analysis["candidates_evaluated"],
                   "selected_vehicle_id": selected, "distance_meters": evidence.get("distance_meters"),
                   "duration_seconds": evidence.get("duration_seconds"), "estimate_source": evidence.get("source", "unavailable"),
                   "estimate_notice": evidence.get("notice", "Google Maps driving-route evidence" if selected else "No route selected"),
                   "decision_reason": plan["decision_reason"], "outcome": outcome, "timestamp": now(),
                   "reassigned_shipment_ids": pending if selected else [], "policy_version": analysis["policy"]["version"],
                   "policy_applied": analysis["policy"], "ranking_rule": plan["ranking_rule"], "agent_execution": agent_execution}
            state["recovery_runs"][run_id] = run
            state["policy_settings"].setdefault("recovery", default_policy())
            audit(state, "recovery_execution" if selected else "recovery_escalated", incident_id=incident_id, run_id=run_id, outcome=outcome)
            return run

        result = self.store.mutate(change)
        return {**result, "data_mode": self.store.mode, "storage_notice": self.store.notice}

    def feedback(self, run_id, rating, reason):
        def change(state):
            if run_id not in state["recovery_runs"]:
                raise HTTPException(404, "Recovery run not found")
            if any(f["run_id"] == run_id for f in state["recovery_feedback"].values()):
                raise HTTPException(409, "Feedback already recorded for this recovery run")
            if rating == "good" and reason:
                raise HTTPException(422, "Positive feedback must not include a negative reason")
            policy = state["policy_settings"].setdefault("recovery", default_policy())
            key = identifier("FB")
            feedback = {"feedback_id": key, "run_id": run_id, "rating": rating, "reason": reason, "timestamp": now()}
            state["recovery_feedback"][key] = feedback
            if rating == "needs_improvement" and reason == "too_far" and state["recovery_runs"][run_id]["selected_vehicle_id"]:
                old = policy["distance_weight"]
                policy["distance_weight"] = round(min(0.9, old + 0.05), 2)
                policy["eta_weight"] = round(1 - policy["distance_weight"], 2)
                if policy["distance_weight"] != old:
                    policy["version"] += 1
                    policy["explanation"] = "Dispatcher reported vehicle too far away. Distance preference increased by 0.05 (maximum 0.90). Shortest-distance-first and all safety checks remain mandatory; ETA tie scores use the updated weights."
                    audit(state, "feedback_preference_updated", run_id=run_id, feedback_id=key, policy=dict(policy))
            audit(state, "dispatcher_feedback", run_id=run_id, feedback_id=key, rating=rating)
            return {"feedback": feedback, "policy": policy, "data_mode": self.store.mode, "storage_notice": self.store.notice}

        return self.store.mutate(change)
