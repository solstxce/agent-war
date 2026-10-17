from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from logistics_api.config import configuration_status, get_settings

app = FastAPI(title="Delivery Exception Manager", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/api/health", tags=["setup"])
def health() -> dict:
    """Process liveness and configuration presence; does not probe cloud services."""
    return {
        "status": "ok",
        "service": "delivery-exception-api",
        "environment": get_settings().app_environment,
        "integrations": configuration_status(),
        "features": {"dispatch": False, "recovery": False, "feedback_learning": False},
    }


def run() -> None:
    import uvicorn

    uvicorn.run("logistics_api.main:app", host="127.0.0.1", port=8000)
