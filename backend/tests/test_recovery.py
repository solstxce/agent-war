import asyncio
import copy
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

import httpx
from fastapi import HTTPException

from logistics_api.config import Settings
from logistics_api.recovery import RecoveryService, default_policy
from logistics_api.recovery_agents import run_recovery_agents
from logistics_api.recovery_maps import RouteMatrix
from logistics_api.recovery_store import LocalStore


class RecordingRoutes:
    def __init__(self):
        self.calls = []

    def matrix(self, vehicles, destination):
        self.calls.append((copy.deepcopy(vehicles), dict(destination)))
        return {
            vehicle["vehicle_id"]: {
                "origin_location": dict(vehicle["current_location"]),
                "source": "google_maps_routes", "route_status": "ok",
                "distance_meters": 100 if vehicle["vehicle_id"] == "V-204" else 1000,
                "duration_seconds": 60,
            }
            for vehicle in vehicles
        }


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "recovery.sqlite3"
        self.settings = Settings(
            _env_file=None, google_api_key="", data_mode="local_demo",
            google_maps_api_key="", google_maps_server_api_key="",
            routing_mode="auto", location_max_age_seconds=900,
        )
        self.store = LocalStore(self.path)
        self.routes = RecordingRoutes()
        self.service = RecoveryService(self.store, self.routes, self.settings)
        self.service.reset(False)

    def prepare(self, scenario="A"):
        incident = self.service.simulate(scenario)
        key = incident["incident_id"]
        analysis = self.service.analyze(key)
        return key, analysis, self.service.plan(key, analysis)

    def execute(self, scenario="A"):
        return self.service.execute(*self.prepare(scenario), {"mode": "test"})

    def assert_conflict_unchanged(self, operation):
        before = self.store.snapshot()
        with self.assertRaises(HTTPException) as raised:
            operation()
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(self.store.snapshot(), before)

    def assert_single_execution(self, incident, run):
        state = self.store.snapshot()
        pending = incident["pending_shipment_ids"]
        self.assertEqual(len(pending), 6)
        self.assertEqual(sorted(run["reassigned_shipment_ids"]), sorted(pending))
        self.assertEqual(run["selected_vehicle_id"], "V-204")
        self.assertEqual(run["outcome"], "resolved")
        self.assertEqual(state["vehicles"]["V-101"]["assigned_shipment_ids"], [])
        self.assertEqual(len(state["vehicles"]["V-204"]["assigned_shipment_ids"]), 8)
        for sid in pending:
            self.assertEqual(state["shipments"][sid]["assigned_vehicle_id"], "V-204")
            owners = [vid for vid, vehicle in state["vehicles"].items()
                      if sid in vehicle["assigned_shipment_ids"]]
            self.assertEqual(owners, ["V-204"])
        self.assertEqual(len(state["recovery_runs"]), 1)
        audits = [entry for entry in state["audit_logs"].values()
                  if entry["action"] == "shipment_reassigned"]
        self.assertCountEqual([entry["shipment_id"] for entry in audits], pending)
        self.assertTrue(all(entry["run_id"] == run["run_id"] for entry in audits))
        for vehicle in state["vehicles"].values():
            ids = vehicle["assigned_shipment_ids"]
            self.assertEqual(len(ids), len(set(ids)))

    def assert_adk_delegation(self, run):
        execution = run["agent_execution"]
        self.assertEqual(execution["mode"], "adk_scripted_demo")
        self.assertEqual(execution["model"], "adk-scripted-demo")
        calls = [(event["author"], name) for event in execution["events"]
                 for name in event["tool_calls"]]
        self.assertEqual(calls, [
            ("IncidentCommander", "fleet_analyst"),
            ("fleet_analyst", "analyze_fleet"),
            ("IncidentCommander", "recovery_planner"),
            ("recovery_planner", "plan_recovery"),
            ("IncidentCommander", "execute_recovery"),
        ])

    def test_actual_adk_scenario_a_moves_all_six_and_routes_only_same_route(self):
        incident = self.service.simulate("A")
        before = self.store.snapshot()
        with patch("logistics_api.recovery_agents.get_settings", return_value=self.settings):
            run = asyncio.run(run_recovery_agents(self.service, incident["incident_id"]))
        self.assert_adk_delegation(run)
        self.assert_single_execution(incident, run)
        vehicles, destination = self.routes.calls[0]
        self.assertEqual(len(self.routes.calls), 1)
        self.assertEqual([v["vehicle_id"] for v in vehicles], ["V-204", "V-205"])
        self.assertTrue(all(v["route_id"] == "R-1" for v in vehicles))
        self.assertEqual(destination, incident["breakdown_location"])
        evidence = {v["vehicle_id"]: v for v in run["candidates_evaluated"]}
        for vehicle in vehicles:
            self.assertEqual(evidence[vehicle["vehicle_id"]]["origin_location"],
                             before["vehicles"][vehicle["vehicle_id"]]["current_location"])
        self.assertFalse(evidence["V-999"]["eligible"])
        self.assertEqual(self.store.snapshot()["vehicles"]["V-999"], before["vehicles"]["V-999"])

    def test_actual_adk_scenario_b_escalates_without_assignment_changes(self):
        incident = self.service.simulate("B")
        before = self.store.snapshot()
        with patch("logistics_api.recovery_agents.get_settings", return_value=self.settings):
            run = asyncio.run(run_recovery_agents(self.service, incident["incident_id"]))
        self.assert_adk_delegation(run)
        self.assertEqual(run["outcome"], "manual_intervention_required")
        self.assertIsNone(run["selected_vehicle_id"])
        self.assertEqual(run["reassigned_shipment_ids"], [])
        self.assertEqual(self.routes.calls, [])
        state = self.store.snapshot()
        for kind in ("vehicles", "shipments"):
            self.assertEqual(state[kind], before[kind])
        notifications = [entry for entry in state["audit_logs"].values()
                         if entry["action"] == "dispatcher_notification"]
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["notification_type"], "simulated")
        self.assertEqual(notifications[0]["incident_id"], incident["incident_id"])
        self.assertEqual(notifications[0]["run_id"], run["run_id"])
        self.assertFalse(any(a["action"] == "shipment_reassigned" for a in state["audit_logs"].values()))

    def test_insufficient_spare_capacity_is_rejected_before_routing(self):
        self.store.mutate(lambda state: state["vehicles"]["V-204"].update(parcel_capacity=7))
        key, analysis, plan = self.prepare()
        evidence = {v["vehicle_id"]: v for v in analysis["candidates_evaluated"]}
        self.assertIn("Insufficient spare", evidence["V-204"]["rejection_reason"])
        self.assertEqual([v["vehicle_id"] for v in self.routes.calls[0][0]], ["V-205"])
        self.assertEqual(plan["selected_vehicle_id"], "V-205")
        self.assertEqual(self.service.execute(key, analysis, plan, {})["outcome"], "resolved")

    def test_stale_invalid_and_unavailable_candidates_never_reach_routing(self):
        def change(state):
            state["vehicles"]["V-301"].update(current_location={"latitude": 91, "longitude": 0})
        self.store.mutate(change)
        _, analysis, plan = self.prepare("B")
        evidence = {v["vehicle_id"]: v for v in analysis["candidates_evaluated"]}
        self.assertIn("Invalid", evidence["V-301"]["rejection_reason"])
        self.assertEqual(evidence["V-302"]["rejection_reason"], "Vehicle unavailable")
        self.assertIn("Stale", evidence["V-303"]["rejection_reason"])
        self.assertIsNone(plan["selected_vehicle_id"])
        self.assertEqual(self.routes.calls, [])

    def test_completed_incident_rejects_duplicate_execution_and_analysis(self):
        key, analysis, plan = self.prepare()
        self.service.execute(key, analysis, plan, {})
        self.assert_conflict_unchanged(lambda: self.service.execute(key, analysis, plan, {}))
        self.assert_conflict_unchanged(lambda: self.service.analyze(key))

    def test_capacity_revalidation_conflict_rolls_back_every_collection(self):
        key, analysis, plan = self.prepare()
        self.store.mutate(lambda state: state["vehicles"]["V-204"].update(parcel_capacity=2))
        self.assert_conflict_unchanged(lambda: self.service.execute(key, analysis, plan, {}))
        self.assertEqual(self.store.snapshot()["incidents"][key]["status"], "open")

    def test_changed_origin_conflicts_without_partial_assignment(self):
        key, analysis, plan = self.prepare()
        self.store.mutate(lambda state: state["vehicles"]["V-204"].update(
            current_location={"latitude": 51.6, "longitude": -0.1}))
        self.assert_conflict_unchanged(lambda: self.service.execute(key, analysis, plan, {}))

    def test_nonwinner_moving_closer_invalidates_execution(self):
        key, analysis, plan = self.prepare()
        self.assertEqual(plan["selected_vehicle_id"], "V-204")
        self.store.mutate(lambda state: state["vehicles"]["V-205"].update(
            current_location=dict(analysis["breakdown_location"])))
        self.assert_conflict_unchanged(lambda: self.service.execute(key, analysis, plan, {}))

    def test_previously_rejected_vehicle_becoming_eligible_invalidates_execution(self):
        for scenario, vehicle_id, changes in (
            ("A", "V-205", {"parcel_capacity": 16}),
            ("B", "V-302", {"status": "operational"}),
        ):
            with self.subTest(scenario=scenario):
                self.service.reset(False)
                if scenario == "A":
                    self.store.mutate(lambda state: state["vehicles"][vehicle_id].update(parcel_capacity=0))
                key, analysis, plan = self.prepare(scenario)
                candidate = next(v for v in analysis["candidates_evaluated"] if v["vehicle_id"] == vehicle_id)
                self.assertFalse(candidate["eligible"])
                self.assertEqual(plan["selected_vehicle_id"], "V-204" if scenario == "A" else None)
                self.store.mutate(lambda state: state["vehicles"][vehicle_id].update(changes))
                self.assert_conflict_unchanged(lambda: self.service.execute(key, analysis, plan, {}))

    def test_invalid_broken_vehicle_telemetry_rejects_simulation_atomically(self):
        stamp = datetime.now(timezone.utc)
        cases = {
            "stale": {"last_location_update": (stamp - timedelta(hours=2)).isoformat()},
            "future": {"last_location_update": (stamp + timedelta(hours=1)).isoformat()},
            "missing_timestamp": {"last_location_update": None},
            "malformed_timestamp": {"last_location_update": "not-a-timestamp"},
            "naive_timestamp": {"last_location_update": stamp.replace(tzinfo=None).isoformat()},
            "missing_location": {"current_location": None},
            "invalid_location": {"current_location": {"latitude": 91, "longitude": 0}},
        }
        for name, changes in cases.items():
            with self.subTest(telemetry=name):
                self.service.reset(False)
                def change(state):
                    state["vehicles"]["V-101"].update(changes)
                    if name == "missing_timestamp":
                        state["vehicles"]["V-101"].pop("last_location_update")
                    if name == "missing_location":
                        state["vehicles"]["V-101"].pop("current_location")
                self.store.mutate(change)
                self.assert_conflict_unchanged(lambda: self.service.simulate("A"))
        self.assertEqual(self.routes.calls, [])

    def test_broken_location_changed_after_incident_rejects_context_and_execution(self):
        key, analysis, plan = self.prepare()
        self.store.mutate(lambda state: state["vehicles"]["V-101"].update(
            current_location={"latitude": 51.6, "longitude": -0.1}))
        self.assert_conflict_unchanged(lambda: self.service.context(self.store.snapshot(), key))
        self.assert_conflict_unchanged(lambda: self.service.analyze(key))
        self.assert_conflict_unchanged(lambda: self.service.execute(key, analysis, plan, {}))

    def test_selected_timestamp_ages_out_after_analysis_without_fleet_change(self):
        stamp = datetime.now(timezone.utc)
        self.store.mutate(lambda state: state["vehicles"]["V-204"].update(
            last_location_update=(stamp - timedelta(seconds=890)).isoformat()))
        with patch("logistics_api.recovery.datetime", wraps=datetime) as clock:
            clock.now.return_value = stamp
            key, analysis, plan = self.prepare()
            self.assertEqual(plan["selected_vehicle_id"], "V-204")
            clock.now.return_value = stamp + timedelta(seconds=20)
            self.assert_conflict_unchanged(lambda: self.service.execute(key, analysis, plan, {}))

    def test_cloud_synthetic_routes_allowed_but_straight_line_rejected(self):
        for mode in ("synthetic_demo", "auto"):
            with self.subTest(routing_mode=mode):
                self.service.reset(False)
                settings = self.settings.model_copy(update={"routing_mode": mode})
                service = RecoveryService(self.store, RouteMatrix(settings), settings)
                # Seed locally before enabling cloud-only checks; no Firestore root exists.
                with patch.object(self.store, "mode", "firestore"):
                    incident = service.simulate("A")
                    key = incident["incident_id"]
                    analysis = service.analyze(key)
                    candidates = [v for v in analysis["candidates_evaluated"] if v["eligible"]]
                    self.assertEqual(len(candidates), 2)
                    for candidate in candidates:
                        self.assertEqual(candidate["source"], "synthetic_demo" if mode == "synthetic_demo" else "straight_line")
                        self.assertEqual(candidate["route_status"], "ok" if mode == "synthetic_demo" else "unavailable")
                    plan = service.plan(key, analysis)
                    before = self.store.snapshot()
                    run = service.execute(key, analysis, plan, {})
                    self.assertEqual(run["data_mode"], "firestore")
                    if mode == "synthetic_demo":
                        self.assert_single_execution(incident, run)
                        self.assertEqual(run["estimate_source"], "synthetic_demo")
                        self.assertIn("Synthetic", run["estimate_notice"])
                        self.assertGreater(run["duration_seconds"], 0)
                    else:
                        self.assertIsNone(plan["selected_vehicle_id"])
                        self.assertEqual(run["outcome"], "manual_intervention_required")
                        self.assertEqual(run["reassigned_shipment_ids"], [])
                        after = self.store.snapshot()
                        for kind in ("vehicles", "shipments"):
                            self.assertEqual(after[kind], before[kind])

    def test_configured_maps_all_failed_escalates_without_assignment_changes(self):
        settings = self.settings.model_copy(update={
            "routing_mode": "google_maps", "google_maps_api_key": "fake-maps-key",
        })
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(503)
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            self.service.router = RouteMatrix(settings, client)
            key, analysis, plan = self.prepare()
            self.assertIsNone(plan["selected_vehicle_id"])
            candidates = [v for v in analysis["candidates_evaluated"] if v["eligible"]]
            self.assertEqual(len(candidates), 2)
            for candidate in candidates:
                self.assertEqual(candidate["source"], "google_maps_routes")
                self.assertEqual(candidate["route_status"], "unavailable")
                self.assertNotIn("distance_meters", candidate)
                self.assertNotIn("duration_seconds", candidate)
            before = self.store.snapshot()
            run = self.service.execute(key, analysis, plan, {})
        self.assertEqual(len(requests), 1)
        self.assertEqual(run["outcome"], "manual_intervention_required")
        self.assertEqual(run["reassigned_shipment_ids"], [])
        after = self.store.snapshot()
        for kind in ("vehicles", "shipments"):
            self.assertEqual(after[kind], before[kind])
        self.assertFalse(any(a["action"] == "shipment_reassigned" for a in after["audit_logs"].values()))

    def test_duplicate_or_conflicting_broken_assignment_ledger_is_rejected(self):
        for conflicting in (False, True):
            with self.subTest(conflicting=conflicting):
                self.service.reset(False)
                incident = self.service.simulate("A")
                def corrupt(state):
                    sid = incident["pending_shipment_ids"][0]
                    vid = "V-999" if conflicting else "V-101"
                    state["vehicles"][vid]["assigned_shipment_ids"].append(sid)
                self.store.mutate(corrupt)
                self.assert_conflict_unchanged(lambda: self.service.analyze(incident["incident_id"]))
        self.assertEqual(self.routes.calls, [])

    def test_candidate_duplicate_and_conflicting_ledgers_are_excluded(self):
        for conflicting in (False, True):
            with self.subTest(conflicting=conflicting):
                self.service.reset(False)
                def corrupt(state):
                    sid = state["vehicles"]["V-204"]["assigned_shipment_ids"][0]
                    state["vehicles"]["V-999" if conflicting else "V-204"]["assigned_shipment_ids"].append(sid)
                self.store.mutate(corrupt)
                _, analysis, plan = self.prepare()
                candidate = next(v for v in analysis["candidates_evaluated"] if v["vehicle_id"] == "V-204")
                self.assertFalse(candidate["eligible"])
                self.assertIn("ledger", candidate["rejection_reason"])
                self.assertEqual(plan["selected_vehicle_id"], "V-205")

    def test_road_distance_wins_over_eta_and_eta_breaks_distance_ties(self):
        for distances, durations, expected in (
            ((100, 200), (900, 1), "V-204"),
            ((100, 100), (900, 1), "V-205"),
            ((100, 100), (1, 1), "V-204"),
        ):
            with self.subTest(distances=distances, durations=durations):
                self.service.reset(False)
                requests = []
                def handler(request):
                    requests.append(json.loads(request.content))
                    return httpx.Response(200, json=[
                        {"originIndex": i, "destinationIndex": 0, "condition": "ROUTE_EXISTS",
                         "status": {}, "distanceMeters": distances[i], "duration": f"{durations[i]}s"}
                        for i in (1, 0)
                    ])
                settings = self.settings.model_copy(update={"google_maps_api_key": "fake-maps-key"})
                with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                    self.service.router = RouteMatrix(settings, client)
                    key, analysis, plan = self.prepare()
                    run = self.service.execute(key, analysis, plan, {})
                self.assertEqual(run["selected_vehicle_id"], expected)
                self.assertEqual(run["estimate_source"], "google_maps_routes")
                self.assertEqual(run["ranking_rule"], "distance_then_eta_then_vehicle_id")
                self.assertEqual(len(requests), 1)
                state = self.store.snapshot()
                self.assertEqual(requests[0]["origins"], [
                    {"waypoint": {"location": {"latLng": state["vehicles"][vid]["current_location"]}}}
                    for vid in ("V-204", "V-205")
                ])

    def test_too_far_feedback_is_versioned_bounded_and_used_by_later_decisions(self):
        for index in range(6):
            run = self.execute()
            policy_before = self.store.snapshot()["policy_settings"]["recovery"]
            self.assertEqual(run["policy_version"], policy_before["version"])
            self.assertEqual(run["policy_applied"], policy_before)
            result = self.service.feedback(run["run_id"], "needs_improvement", "too_far")
            expected_weight = round(min(0.9, 0.7 + (index + 1) * 0.05), 2)
            self.assertEqual(result["policy"]["distance_weight"], expected_weight)
            self.assertAlmostEqual(result["policy"]["eta_weight"], 1 - expected_weight)
            self.assertEqual(result["policy"]["version"], min(index + 2, 5))
            self.assertEqual(self.store.snapshot()["recovery_runs"][run["run_id"]]["policy_applied"], policy_before)
            reopened = RecoveryService(LocalStore(self.path), self.routes, self.settings)
            self.assertEqual(reopened.dashboard()["policy"], result["policy"])
            reopened.reset(True)
            self.service = reopened
        run = self.execute()
        self.assertEqual(run["policy_version"], 5)
        self.assertEqual(run["policy_applied"]["distance_weight"], 0.9)

    def test_positive_feedback_keeps_policy_unchanged_and_duplicate_is_conflict(self):
        run = self.execute()
        before = self.store.snapshot()["policy_settings"]["recovery"]
        result = self.service.feedback(run["run_id"], "good", None)
        self.assertEqual(result["policy"], before)
        self.assertEqual(before, default_policy())
        self.assert_conflict_unchanged(lambda: self.service.feedback(run["run_id"], "needs_improvement", "too_far"))
        self.assertEqual(len(self.store.snapshot()["recovery_feedback"]), 1)

    def test_sqlite_persists_all_collections_across_new_store(self):
        run = self.execute()
        self.service.feedback(run["run_id"], "needs_improvement", "too_far")
        before = self.store.snapshot()
        reopened = LocalStore(self.path)
        self.assertEqual(reopened.snapshot(), before)
        dashboard = RecoveryService(reopened, self.routes, self.settings).dashboard()
        self.assertEqual(dashboard["policy"]["version"], 2)
        self.assertEqual(dashboard["recovery_runs"][0]["run_id"], run["run_id"])
        self.assertEqual(dashboard["data_mode"], "local_demo")

    def test_concurrent_execution_has_one_winner_and_no_duplicate_assignments(self):
        key, analysis, plan = self.prepare()
        incident = self.store.snapshot()["incidents"][key]
        barrier = Barrier(2)
        def execute():
            service = RecoveryService(LocalStore(self.path), self.routes, self.settings)
            barrier.wait(timeout=10)
            try:
                return service.execute(key, analysis, plan, {})
            except HTTPException as exc:
                return exc
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: execute(), range(2)))
        winners = [result for result in results if isinstance(result, dict)]
        losers = [result for result in results if isinstance(result, HTTPException)]
        self.assertEqual(len(winners), 1)
        self.assertEqual(len(losers), 1)
        self.assertEqual(losers[0].status_code, 409)
        self.assert_single_execution(incident, winners[0])


if __name__ == "__main__":
    unittest.main()
