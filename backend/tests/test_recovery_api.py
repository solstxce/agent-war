import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from logistics_api.config import Settings
from logistics_api.operations import current_user
from logistics_api.recovery import RecoveryService
from logistics_api.recovery_api import get_recovery_service, router
from logistics_api.recovery_maps import RouteMatrix
from logistics_api.recovery_store import LocalStore


class RecoveryApiTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.settings = Settings(
            _env_file=None, google_api_key="", data_mode="local_demo",
            google_maps_api_key="", google_maps_server_api_key="",
            routing_mode="auto", location_max_age_seconds=900,
        )
        self.store = LocalStore(Path(directory.name) / "recovery.sqlite3")
        self.service = RecoveryService(self.store, RouteMatrix(self.settings), self.settings)
        self.service.reset(False)
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_recovery_service] = lambda: self.service
        self.client = self.enterContext(TestClient(app))
        self.enterContext(patch("logistics_api.recovery_agents.get_settings", return_value=self.settings))

    def resolve_a(self):
        response = self.client.post("/api/incidents/simulate", json={"scenario": "A"})
        self.assertEqual(response.status_code, 201, response.text)
        incident = response.json()
        duplicate = self.client.post("/api/incidents/simulate", json={"scenario": "A"})
        self.assertEqual(duplicate.status_code, 201)
        self.assertEqual(duplicate.json()["incident_id"], incident["incident_id"])
        response = self.client.post(f"/api/incidents/{incident['incident_id']}/resolve")
        self.assertEqual(response.status_code, 200, response.text)
        run = response.json()
        self.assertEqual(run["selected_vehicle_id"], "V-204")
        self.assertEqual(run["outcome"], "resolved")
        self.assertEqual(run["reassigned_shipment_ids"], incident["pending_shipment_ids"])
        self.assertEqual(len(run["reassigned_shipment_ids"]), 6)
        self.assertEqual(run["agent_execution"]["mode"], "adk_scripted_demo")
        calls = [name for event in run["agent_execution"]["events"] for name in event["tool_calls"]]
        self.assertEqual(calls, ["fleet_analyst", "analyze_fleet", "recovery_planner", "plan_recovery", "execute_recovery"])
        self.assertEqual(run["estimate_source"], "straight_line")
        self.assertIsNone(run["duration_seconds"])
        return incident, run

    def test_dashboard_simulate_actual_adk_feedback_preserving_reset_and_repeat(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        dashboard = response.json()
        self.assertEqual(dashboard["data_mode"], "local_demo")
        self.assertEqual(dashboard["agent_mode"], "adk_scripted_demo")
        self.assertEqual(len(dashboard["vehicles"]), 8)
        self.assertEqual(dashboard["counts"]["pending_shipments"], 20)
        incident, run = self.resolve_a()
        before = self.store.snapshot()
        duplicate = self.client.post(f"/api/incidents/{incident['incident_id']}/resolve")
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(self.store.snapshot(), before)
        response = self.client.post(f"/api/recovery-runs/{run['run_id']}/feedback", json={
            "rating": "needs_improvement", "reason": "too_far",
        })
        self.assertEqual(response.status_code, 200, response.text)
        policy = response.json()["policy"]
        self.assertEqual(policy["version"], 2)
        self.assertEqual(policy["distance_weight"], 0.75)
        before = self.store.snapshot()
        duplicate = self.client.post(f"/api/recovery-runs/{run['run_id']}/feedback", json={"rating": "good"})
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(self.store.snapshot(), before)
        response = self.client.post("/api/demo/reset", json={"preserve_policy": True})
        self.assertEqual(response.status_code, 200)
        reset = response.json()
        self.assertEqual(reset["policy"], policy)
        for kind in ("incidents", "recovery_runs", "recovery_feedback"):
            self.assertEqual(reset[kind], [])
        self.assertEqual(reset["counts"]["broken_down_vehicles"], 0)
        new_incident, new_run = self.resolve_a()
        self.assertNotEqual(new_incident["incident_id"], incident["incident_id"])
        self.assertNotEqual(new_run["run_id"], run["run_id"])
        self.assertEqual(new_run["policy_version"], 2)
        self.assertEqual(new_run["policy_applied"], policy)
        response = self.client.post(f"/api/recovery-runs/{new_run['run_id']}/feedback", json={"rating": "good"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["policy"], policy)
        dashboard = self.client.get("/api/dashboard").json()
        self.assertEqual(dashboard["policy"], policy)
        self.assertEqual(len(dashboard["recovery_runs"]), 1)
        self.assertEqual(len(dashboard["recovery_feedback"]), 1)

    def test_scenario_b_escalates_and_preserves_assignments(self):
        response = self.client.post("/api/incidents/simulate", json={"scenario": "B"})
        self.assertEqual(response.status_code, 201)
        key = response.json()["incident_id"]
        before = self.store.snapshot()
        response = self.client.post(f"/api/incidents/{key}/resolve")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["outcome"], "manual_intervention_required")
        after = self.store.snapshot()
        self.assertEqual(after["shipments"], before["shipments"])
        self.assertEqual(after["vehicles"], before["vehicles"])
        self.assertEqual(self.client.post(f"/api/incidents/{key}/resolve").status_code, 409)

    def test_invalid_requests_do_not_mutate_storage(self):
        cases = [
            ("/api/incidents/simulate", {"scenario": "C"}, 422),
            ("/api/incidents/simulate", {"scenario": "A", "vehicle_id": "V-999"}, 422),
            ("/api/incidents/simulate", None, 422),
            ("/api/recovery-runs/missing/feedback", {"rating": "bad"}, 422),
            ("/api/recovery-runs/missing/feedback", {"rating": "needs_improvement", "reason": "invalid"}, 422),
            ("/api/recovery-runs/missing/feedback", {"reason": "too_far"}, 422),
            ("/api/recovery-runs/missing/feedback", {"rating": "good", "extra": True}, 422),
            ("/api/recovery-runs/missing/feedback", {"rating": "good"}, 404),
            ("/api/incidents/missing/resolve", None, 404),
            ("/api/demo/reset", {"preserve_policy": "invalid"}, 422),
            ("/api/demo/reset", {"extra": True}, 422),
        ]
        before = self.store.snapshot()
        for path, body, expected in cases:
            with self.subTest(path=path, body=body):
                response = self.client.post(path, json=body)
                self.assertEqual(response.status_code, expected, response.text)
                self.assertIn("detail", response.json())
                self.assertEqual(self.store.snapshot(), before)

    def test_positive_feedback_with_negative_reason_is_rejected_atomically(self):
        _, run = self.resolve_a()
        before = self.store.snapshot()
        response = self.client.post(f"/api/recovery-runs/{run['run_id']}/feedback", json={
            "rating": "good", "reason": "too_far",
        })
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.store.snapshot(), before)

    def test_execute_conflict_survives_actual_scripted_adk_after_preflight(self):
        response = self.client.post("/api/incidents/simulate", json={"scenario": "A"})
        self.assertEqual(response.status_code, 201, response.text)
        key = response.json()["incident_id"]
        before = self.store.snapshot()
        with patch.object(self.service, "execute", side_effect=HTTPException(409, "Fleet changed during execution")) as execute:
            response = self.client.post(f"/api/incidents/{key}/resolve")
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json(), {"detail": "Fleet changed during execution"})
        execute.assert_called_once()
        incident_id, analysis, plan, metadata = execute.call_args.args
        self.assertEqual(incident_id, key)
        self.assertEqual(analysis["incident_id"], key)
        self.assertEqual(plan["selected_vehicle_id"], "V-204")
        self.assertEqual(metadata["mode"], "adk_scripted_demo")
        calls = [name for event in metadata["events"] for name in event["tool_calls"]]
        self.assertEqual(calls, ["fleet_analyst", "analyze_fleet", "recovery_planner", "plan_recovery", "execute_recovery"])
        self.assertEqual(self.store.snapshot(), before)

    def test_cloud_access_without_token_returns_401_without_database_access(self):
        before = self.store.snapshot()
        with patch.object(self.store, "mode", "firestore"), patch(
            "logistics_api.recovery_api.current_user", wraps=current_user
        ) as user, patch("logistics_api.recovery_api.member") as member:
            response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 401, response.text)
        user.assert_called_once_with(None)
        member.assert_not_called()
        self.assertEqual(self.store.snapshot(), before)

    def test_cloud_access_with_invalid_membership_returns_403_without_database(self):
        before = self.store.snapshot()
        user = {"uid": "nonmember"}
        database = object()
        with patch.object(self.store, "mode", "firestore"), patch.object(
            self.store, "client", database, create=True
        ), patch("logistics_api.recovery_api.current_user", return_value=user) as authenticate, patch(
            "logistics_api.recovery_api.member",
            side_effect=HTTPException(403, "Dispatcher workspace membership required"),
        ) as member:
            response = self.client.get("/api/dashboard", headers={"Authorization": "Bearer fake-token"})
        self.assertEqual(response.status_code, 403, response.text)
        authenticate.assert_called_once()
        self.assertEqual(authenticate.call_args.args[0].credentials, "fake-token")
        member.assert_called_once_with(self.settings.recovery_workspace_id, user, database)
        self.assertEqual(self.store.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
