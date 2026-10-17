import json
import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx

from logistics_api.recovery_maps import RouteMatrix


class RouteMatrixTests(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(maps_key="secret-maps-key", maps_request_timeout_seconds=3.5, routing_mode="auto")
        self.vehicles = [
            {"vehicle_id": "V-1", "current_location": {"latitude": 51.5, "longitude": -0.1}},
            {"vehicle_id": "V-2", "current_location": {"latitude": 51.6, "longitude": -0.2}},
        ]
        self.destination = {"latitude": 51.7, "longitude": -0.3}

    def element(self, index=0, **changes):
        return {"originIndex": index, "destinationIndex": 0, "condition": "ROUTE_EXISTS",
                "status": {}, "distanceMeters": 1234, "duration": "98.5s", **changes}

    def route(self, payload, vehicles=None):
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as client:
            return RouteMatrix(self.settings, client).matrix(
                self.vehicles if vehicles is None else vehicles, self.destination)

    def assert_unavailable(self, result):
        self.assertEqual(result["route_status"], "unavailable")
        self.assertEqual(result["source"], "google_maps_routes")
        self.assertTrue(result["error_reason"])
        self.assertNotIn(self.settings.maps_key, repr(result))
        self.assertNotIn("distance_meters", result)
        self.assertNotIn("duration_seconds", result)

    def test_unordered_success_request_and_independent_distance_eta(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, json=[
                self.element(1, distanceMeters=9000, duration="1s", status={"code": 0}),
                self.element(0, distanceMeters=100, duration="999.25s"),
            ])

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            results = RouteMatrix(self.settings, client).matrix(self.vehicles, self.destination)
            self.assertFalse(client.is_closed)
        self.assertEqual(set(results), {"V-1", "V-2"})
        self.assertEqual(results["V-1"]["distance_meters"], 100)
        self.assertEqual(results["V-1"]["duration_seconds"], 999.25)
        self.assertEqual(results["V-2"]["distance_meters"], 9000)
        self.assertEqual(results["V-2"]["duration_seconds"], 1)
        for vehicle in self.vehicles:
            result = results[vehicle["vehicle_id"]]
            self.assertEqual(result["route_status"], "ok")
            self.assertEqual(result["source"], "google_maps_routes")
            self.assertNotIn("error_reason", result)
            self.assertEqual(result["origin_location"], vehicle["current_location"])
            self.assertIsNot(result["origin_location"], vehicle["current_location"])
        request, = requests
        self.assertEqual(request.method, "POST")
        self.assertEqual(str(request.url), "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix")
        self.assertEqual(request.headers["X-Goog-Api-Key"], self.settings.maps_key)
        self.assertEqual(request.headers["X-Goog-FieldMask"],
                         "originIndex,destinationIndex,distanceMeters,duration,status,condition")
        self.assertEqual(json.loads(request.content), {
            "origins": [{"waypoint": {"location": {"latLng": v["current_location"]}}} for v in self.vehicles],
            "destinations": [{"waypoint": {"location": {"latLng": self.destination}}}],
            "travelMode": "DRIVE",
        })
        self.assertEqual(request.extensions["timeout"]["read"], 3.5)

    def test_zero_metrics_and_absent_status_are_valid(self):
        element = self.element(distanceMeters=0, duration="0.0s")
        del element["status"]
        result = self.route([element])["V-1"]
        self.assertEqual(result["route_status"], "ok")
        self.assertEqual(result["distance_meters"], 0)
        self.assertEqual(result["duration_seconds"], 0)

    def test_missing_and_duplicate_elements_are_unavailable(self):
        for elements in ([], [self.element(1)], [self.element(), self.element()],
                         [self.element(), self.element(destinationIndex=1)]):
            with self.subTest(elements=elements):
                self.assert_unavailable(self.route(elements)["V-1"])
        results = self.route([self.element(), self.element(), self.element(1)])
        self.assertEqual(results["V-2"]["route_status"], "ok")

    def test_malformed_elements_do_not_become_zero_routes(self):
        invalid = [None, "bad", 0, {}, self.element(originIndex=True), self.element(originIndex=-1),
                   self.element(originIndex=2), self.element(originIndex="0")]
        changes = [
            {"destinationIndex": None}, {"destinationIndex": False}, {"destinationIndex": 1},
            {"condition": "ROUTE_NOT_FOUND"}, {"condition": None},
            {"status": {"code": 7, "message": self.settings.maps_key}},
            {"status": None}, {"status": []}, {"status": {"code": "0"}}, {"status": {"code": False}},
        ]
        changes += [{"distanceMeters": value} for value in
                    (None, True, -1, "123", math.nan, math.inf, -math.inf)]
        changes += [{"duration": value} for value in
                    (None, 0, "", "-1s", "+1s", "1", ".5s", "1.s", "1e3s", "NaNs", "infs", "1s\n", "9" * 400 + "s")]
        invalid += [self.element(**change) for change in changes]
        for field in ("originIndex", "destinationIndex", "condition", "distanceMeters", "duration"):
            element = self.element()
            del element[field]
            invalid.append(element)
        for element in invalid:
            with self.subTest(element=element):
                # JSON can carry nonstandard NaN/Infinity from a broken provider.
                with httpx.Client(transport=httpx.MockTransport(
                        lambda request: httpx.Response(200, content=json.dumps([element])))) as client:
                    results = RouteMatrix(self.settings, client).matrix(self.vehicles, self.destination)
                for result in results.values():
                    self.assert_unavailable(result)

    def test_http_network_and_invalid_response_failures_are_sanitized(self):
        def timeout(request):
            raise httpx.ReadTimeout(self.settings.maps_key, request=request)

        def network(request):
            raise httpx.ConnectError(self.settings.maps_key, request=request)

        handlers = [timeout, network]
        handlers += [lambda request, code=code: httpx.Response(code, text=self.settings.maps_key)
                     for code in (400, 403, 429, 500)]
        handlers += [lambda request: httpx.Response(200, text=self.settings.maps_key)]
        handlers += [lambda request, payload=payload: httpx.Response(200, json=payload)
                     for payload in ({"error": self.settings.maps_key}, None, "bad")]
        for handler in handlers:
            with self.subTest(handler=handler):
                with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                    results = RouteMatrix(self.settings, client).matrix(self.vehicles, self.destination)
                for vehicle in self.vehicles:
                    result = results[vehicle["vehicle_id"]]
                    self.assert_unavailable(result)
                    self.assertEqual(result["origin_location"], vehicle["current_location"])
                    self.assertIsNot(result["origin_location"], vehicle["current_location"])

    def test_batches_use_local_indices_and_continue_after_failure(self):
        vehicles = [{**self.vehicles[0], "vehicle_id": f"V-{index}"} for index in range(201)]
        sizes = []

        def handler(request):
            size = len(json.loads(request.content)["origins"])
            sizes.append(size)
            if len(sizes) == 2:
                return httpx.Response(503)
            return httpx.Response(200, json=[self.element(index, distanceMeters=index)
                                            for index in reversed(range(size))])

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            results = RouteMatrix(self.settings, client).matrix(vehicles, self.destination)
        self.assertEqual(sizes, [100, 100, 1])
        self.assertEqual(len(results), 201)
        for index in range(201):
            if 100 <= index < 200:
                self.assert_unavailable(results[f"V-{index}"])
            else:
                self.assertEqual(results[f"V-{index}"]["distance_meters"], index % 100)

    def test_no_key_haversine_fallback_without_http(self):
        self.settings.maps_key = ""
        vehicles = [{"vehicle_id": "near", "current_location": {"latitude": 0, "longitude": 0}},
                    {"vehicle_id": "same", "current_location": {"latitude": 0, "longitude": 1}},
                    {"vehicle_id": "opposite", "current_location": {"latitude": 0, "longitude": -179}}]
        with patch("logistics_api.recovery_maps.httpx.Client") as client:
            results = RouteMatrix(self.settings).matrix(vehicles, {"latitude": 0, "longitude": 1})
            client.assert_not_called()
        self.assertEqual(results["near"]["distance_meters"], 111195)
        self.assertEqual(results["same"]["distance_meters"], 0)
        self.assertEqual(results["opposite"]["distance_meters"], 20015087)
        for vehicle in vehicles:
            result = results[vehicle["vehicle_id"]]
            self.assertEqual(result["source"], "straight_line")
            self.assertEqual(result["route_status"], "ok")
            self.assertIsNone(result["duration_seconds"])
            self.assertIn("not road distance", result["notice"])
            self.assertIn("no driving ETA", result["notice"])
            self.assertEqual(result["origin_location"], vehicle["current_location"])
            self.assertIsNot(result["origin_location"], vehicle["current_location"])

    def test_empty_candidates_do_not_create_client(self):
        with patch("logistics_api.recovery_maps.httpx.Client") as client:
            self.assertEqual(RouteMatrix(self.settings).matrix([], self.destination), {})
            client.assert_not_called()

    def test_synthetic_demo_with_maps_key_bypasses_owned_and_injected_http_clients(self):
        self.settings.routing_mode = "synthetic_demo"
        vehicles = [
            {"vehicle_id": "same", "current_location": {"latitude": 0, "longitude": 1}},
            {"vehicle_id": "near", "current_location": {"latitude": 0, "longitude": 0}},
        ]
        destination = {"latitude": 0, "longitude": 1}
        injected = Mock(spec=httpx.Client)
        with patch("logistics_api.recovery_maps.httpx.Client") as owned:
            results = RouteMatrix(self.settings).matrix(vehicles, destination)
            repeated = RouteMatrix(self.settings, injected).matrix(list(reversed(vehicles)), destination)
            owned.assert_not_called()
        self.assertEqual(injected.mock_calls, [])
        self.assertEqual(results, repeated)
        self.assertEqual(results["same"]["distance_meters"], 500)
        self.assertEqual(results["same"]["duration_seconds"], 131)
        self.assertEqual(results["near"]["distance_meters"], 150613)
        self.assertEqual(results["near"]["duration_seconds"], 21576)
        for vehicle in vehicles:
            result = results[vehicle["vehicle_id"]]
            self.assertEqual(result["source"], "synthetic_demo")
            self.assertEqual(result["route_status"], "ok")
            self.assertIn("Synthetic demo distance and ETA", result["notice"])
            self.assertIn("NOT Google Maps", result["notice"])
            self.assertNotIn("error_reason", result)
            self.assertNotIn(self.settings.maps_key, repr(result))
            self.assertEqual(result["origin_location"], vehicle["current_location"])
            self.assertIsNot(result["origin_location"], vehicle["current_location"])

    def test_google_maps_without_key_is_unavailable_not_straight_line(self):
        self.settings.routing_mode = "google_maps"
        self.settings.maps_key = ""
        injected = Mock(spec=httpx.Client)
        with patch("logistics_api.recovery_maps.httpx.Client") as owned:
            results = RouteMatrix(self.settings).matrix(self.vehicles, self.destination)
            self.assertEqual(RouteMatrix(self.settings, injected).matrix(self.vehicles, self.destination), results)
            owned.assert_not_called()
        self.assertEqual(injected.mock_calls, [])
        self.assertEqual(set(results), {"V-1", "V-2"})
        for result in results.values():
            self.assertEqual(result["source"], "google_maps_routes")
            self.assertEqual(result["route_status"], "unavailable")
            self.assertTrue(result["error_reason"])
            self.assertNotIn("distance_meters", result)
            self.assertNotIn("duration_seconds", result)

    def test_owned_client_is_closed(self):
        client = httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=[self.element()])))
        with patch("logistics_api.recovery_maps.httpx.Client", return_value=client):
            result = RouteMatrix(self.settings).matrix(self.vehicles, self.destination)
        self.assertTrue(client.is_closed)
        self.assertEqual(result["V-1"]["route_status"], "ok")


if __name__ == "__main__":
    unittest.main()
