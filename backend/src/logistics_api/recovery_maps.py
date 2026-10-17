"""Route evidence for already-filtered recovery candidates."""

import math
import re
from contextlib import nullcontext

import httpx


def _nonnegative_number(value):
    try:
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) and value >= 0)
    except OverflowError:
        return False


class RouteMatrix:
    def __init__(self, settings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client

    def matrix(self, vehicles: list[dict], destination: dict) -> dict:
        key = self.settings.maps_key
        mode = getattr(self.settings, "routing_mode", "auto")
        synthetic = mode == "synthetic_demo"
        results = {
            vehicle["vehicle_id"]: {
                "origin_location": dict(vehicle["current_location"]),
                "source": "synthetic_demo" if synthetic else "google_maps_routes" if key or mode == "google_maps" else "straight_line",
                "route_status": "unavailable",
                "error_reason": "Driving route unavailable; dispatcher review required.",
            }
            for vehicle in vehicles
        }
        if not vehicles:
            return results

        if synthetic or (not key and mode == "auto"):
            for result in results.values():
                origin = result["origin_location"]
                lat1, lat2 = map(math.radians, (origin["latitude"], destination["latitude"]))
                delta_lat = lat2 - lat1
                delta_lon = math.radians(destination["longitude"] - origin["longitude"])
                haversine = (math.sin(delta_lat / 2) ** 2
                             + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2)
                distance = 2 * 6_371_000 * math.asin(math.sqrt(max(0, min(1, haversine))))
                result.pop("error_reason")
                if synthetic:
                    # Fixed arithmetic over stored coordinates: repeatable demo evidence,
                    # not a claim about road access, current traffic, or driving time.
                    distance = round(distance * 1.35 + 500)
                    result.update(route_status="ok", distance_meters=distance,
                                  duration_seconds=round(distance / 7 + 60),
                                  notice="Synthetic demo distance and ETA; NOT Google Maps road distance or driving ETA.")
                else:
                    result.update(
                        route_status="ok", distance_meters=round(distance), duration_seconds=None,
                        notice="Straight-line estimate only, not road distance; no driving ETA available.",
                    )
            return results

        if not key:
            return results

        context = (nullcontext(self.client) if self.client is not None
                   else httpx.Client(timeout=self.settings.maps_request_timeout_seconds))
        with context as client:
            for start in range(0, len(vehicles), 100):
                batch = vehicles[start:start + 100]
                try:
                    response = client.post(
                        "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix",
                        headers={
                            "X-Goog-Api-Key": key,
                            "X-Goog-FieldMask": "originIndex,destinationIndex,distanceMeters,duration,status,condition",
                        },
                        json={
                            "origins": [{"waypoint": {"location": {"latLng": vehicle["current_location"]}}}
                                        for vehicle in batch],
                            "destinations": [{"waypoint": {"location": {"latLng": destination}}}],
                            "travelMode": "DRIVE",
                        },
                        timeout=self.settings.maps_request_timeout_seconds,
                    )
                    response.raise_for_status()
                    elements = response.json()
                except (httpx.HTTPError, ValueError):
                    # Never include provider bodies or exceptions, which can contain credentials.
                    continue
                if not isinstance(elements, list):
                    continue

                indexed = {}
                duplicates = set()
                for element in elements:
                    if not isinstance(element, dict):
                        continue
                    index = element.get("originIndex")
                    if type(index) is not int or not 0 <= index < len(batch):
                        continue
                    if index in indexed:
                        duplicates.add(index)
                    indexed[index] = element

                for index, element in indexed.items():
                    if index in duplicates:
                        continue
                    destination_index = element.get("destinationIndex")
                    status = element.get("status", {})
                    distance = element.get("distanceMeters")
                    duration = element.get("duration")
                    if (type(destination_index) is not int or destination_index != 0
                            or element.get("condition") != "ROUTE_EXISTS"
                            or not isinstance(status, dict)
                            or type(status.get("code", 0)) is not int or status.get("code", 0) != 0
                            or not _nonnegative_number(distance)
                            or not isinstance(duration, str)
                            or re.fullmatch(r"[0-9]+(?:\.[0-9]+)?s", duration) is None):
                        continue
                    seconds = float(duration[:-1])
                    if not _nonnegative_number(seconds):
                        continue
                    result = results[batch[index]["vehicle_id"]]
                    result.pop("error_reason")
                    result.update(route_status="ok", distance_meters=distance, duration_seconds=seconds)
        return results
