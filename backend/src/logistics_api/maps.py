"""Read-only Google Maps adapters. Never expose provider responses containing keys."""

import httpx
from pydantic import BaseModel, Field, ValidationError

from logistics_api.config import get_settings


class Coordinate(BaseModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


def error(code: str, message: str, retryable: bool = False) -> dict:
    return {"status": "error", "error": {"code": code, "message": message, "retryable": retryable}}


async def _request(method: str, url: str, **kwargs) -> dict:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=settings.maps_request_timeout_seconds) as client:
            response = await client.request(method, url, **kwargs)
        if response.status_code >= 400:
            return error(
                f"PROVIDER_HTTP_{response.status_code}",
                "Google Maps rejected the request. Check enabled APIs, credentials and quotas.",
                response.status_code == 429 or response.status_code >= 500,
            )
        data = response.json()
        if not isinstance(data, dict):
            return error("INVALID_RESPONSE", "Google Maps returned an unexpected response shape.")
        return {"status": "ok", "data": data}
    except httpx.TimeoutException:
        return error("TIMEOUT", "Google Maps request timed out.", True)
    except httpx.RequestError:
        return error("NETWORK_ERROR", "Google Maps could not be reached.", True)
    except ValueError:
        return error("INVALID_RESPONSE", "Google Maps returned an unreadable response.")


async def geocode_address(address: str) -> dict:
    """Resolve an address; return candidates rather than silently accepting an ambiguous match."""
    address = address.strip()
    if not address or len(address) > 500:
        return error("INVALID_ADDRESS", "Provide an address between 1 and 500 characters.")
    key = get_settings().google_maps_server_api_key
    if not key:
        return error("NOT_CONFIGURED", "Set GOOGLE_MAPS_SERVER_API_KEY in the backend environment.")
    result = await _request(
        "GET", "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": address, "key": key},
    )
    if result["status"] != "ok":
        return result
    data = result["data"]
    status = data.get("status")
    if status == "ZERO_RESULTS":
        return error("ADDRESS_NOT_FOUND", "No address matched. Ask for a more precise address.")
    if status != "OK":
        return error("GEOCODING_REJECTED", "Address lookup failed. Check API configuration or quota.", status == "UNKNOWN_ERROR")
    candidates = [{
        "formatted_address": item.get("formatted_address"),
        "place_id": item.get("place_id"),
        "location": item.get("geometry", {}).get("location"),
        "location_type": item.get("geometry", {}).get("location_type"),
        "partial_match": item.get("partial_match", False),
    } for item in data.get("results", [])[:5]]
    return {"status": "ok", "candidates": candidates,
            "requires_confirmation": len(candidates) != 1 or any(c["partial_match"] for c in candidates)}


async def compute_route(origin_latitude: float, origin_longitude: float,
                        destination_latitude: float, destination_longitude: float) -> dict:
    """Compute a driving route. Does not optimize fleets or validate truck restrictions."""
    try:
        origin = Coordinate(latitude=origin_latitude, longitude=origin_longitude)
        destination = Coordinate(latitude=destination_latitude, longitude=destination_longitude)
    except ValidationError:
        return error("INVALID_COORDINATES", "Latitude must be -90..90 and longitude -180..180; values must be finite.")
    key = get_settings().google_maps_server_api_key
    if not key:
        return error("NOT_CONFIGURED", "Set GOOGLE_MAPS_SERVER_API_KEY in the backend environment.")
    result = await _request(
        "POST", "https://routes.googleapis.com/directions/v2:computeRoutes",
        headers={"X-Goog-Api-Key": key,
                 "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline"},
        json={"origin": {"location": {"latLng": origin.model_dump()}},
              "destination": {"location": {"latLng": destination.model_dump()}},
              "travelMode": "DRIVE", "routingPreference": "TRAFFIC_AWARE",
              "computeAlternativeRoutes": False},
    )
    if result["status"] != "ok":
        return result
    routes = result["data"].get("routes", [])
    if not routes:
        return error("NO_ROUTE", "No driving route is available between these locations.")
    route = routes[0]
    return {"status": "ok", "distance_meters": route.get("distanceMeters"),
            "duration": route.get("duration"),
            "encoded_polyline": route.get("polyline", {}).get("encodedPolyline"),
            "fleet_optimized": False}
