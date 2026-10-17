from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore")

    app_environment: str = "development"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    firebase_project_id: str = ""
    google_cloud_project: str = ""
    data_mode: Literal["auto", "local_demo", "firestore"] = "auto"
    recovery_workspace_id: str = "agentwars-demo"
    location_max_age_seconds: int = Field(default=900, ge=30, le=86400)
    google_application_credentials: str = ""
    firestore_emulator_host: str = ""
    firebase_auth_emulator_host: str = ""
    google_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    logistics_mcp_url: str = "http://127.0.0.1:8001/mcp"
    google_maps_server_api_key: str = ""
    google_maps_api_key: str = ""
    routing_mode: Literal["auto", "google_maps", "synthetic_demo"] = "auto"
    allow_cloud_demo_reset: bool = False
    maps_request_timeout_seconds: float = Field(default=10.0, gt=0, le=60)

    @property
    def project_id(self) -> str:
        return self.google_cloud_project or self.firebase_project_id

    @property
    def maps_key(self) -> str:
        return self.google_maps_api_key or self.google_maps_server_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()


def configuration_status() -> dict:
    settings = get_settings()
    return {
        "firebase": {
            "project_configured": bool(settings.project_id),
            "mode": "emulator" if settings.firestore_emulator_host else "cloud",
            "connection_verified": False,
        },
        "agent": {
            "api_key_configured": bool(settings.google_api_key),
            "model": settings.gemini_model,
            "connection_verified": False,
        },
        "mcp": {"url": settings.logistics_mcp_url, "connection_verified": False},
        "maps": {
            "routing_mode": settings.routing_mode,
            "server_key_configured": bool(settings.maps_key),
            "connection_verified": False,
            "capabilities": ["geocoding", "point_to_point_driving_route", "compute_route_matrix"],
        },
    }

