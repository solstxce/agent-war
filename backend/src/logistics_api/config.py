from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore")

    app_environment: str = "development"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    firebase_project_id: str = ""
    google_application_credentials: str = ""
    firestore_emulator_host: str = ""
    firebase_auth_emulator_host: str = ""
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    logistics_mcp_url: str = "http://127.0.0.1:8001/mcp"
    google_maps_server_api_key: str = ""
    maps_request_timeout_seconds: float = Field(default=10.0, gt=0, le=60)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def configuration_status() -> dict:
    settings = get_settings()
    return {
        "firebase": {
            "project_configured": bool(settings.firebase_project_id),
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
            "server_key_configured": bool(settings.google_maps_server_api_key),
            "connection_verified": False,
            "capabilities": ["geocoding", "point_to_point_driving_route"],
        },
    }

