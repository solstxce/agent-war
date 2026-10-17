"""Optional trace export and an operator-only feedback command."""
import argparse
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ObservabilitySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore")
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = ""


def configure_observability():
    settings = ObservabilitySettings()
    if not settings.langfuse_enabled:
        return None
    if not all((settings.langfuse_public_key, settings.langfuse_secret_key, settings.langfuse_base_url)):
        raise RuntimeError("Langfuse enabled: configure public key, secret key, and base URL.")
    from langfuse import Langfuse
    from openinference.instrumentation.google_adk import GoogleADKInstrumentor

    # ADK instrumentation uses the provider configured by Langfuse.
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_BASE_URL", settings.langfuse_base_url)
    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_base_url,
    )
    GoogleADKInstrumentor().instrument()
    return client


def feedback():
    parser = argparse.ArgumentParser(description="Attach operator feedback to an existing Langfuse trace.")
    parser.add_argument("trace_id")
    parser.add_argument("--score", type=int, choices=[0, 1], required=True)
    parser.add_argument("--comment", required=True)
    args = parser.parse_args()
    client = configure_observability()
    if client is None:
        parser.error("Enable and configure Langfuse before recording feedback.")
    try:
        client.create_score(trace_id=args.trace_id, name="dispatcher_review", value=args.score,
                            data_type="BOOLEAN", comment=args.comment)
    finally:
        client.flush()
