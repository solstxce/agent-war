from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google.api_core.exceptions import GoogleAPICallError, RetryError
from google.auth.exceptions import GoogleAuthError

from logistics_api.config import configuration_status, get_settings
from logistics_api.firebase import guard_emulators
from logistics_api.operations import router

guard_emulators()
app = FastAPI(title="Delivery Exception Manager", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)


@app.exception_handler(GoogleAPICallError)
@app.exception_handler(RetryError)
@app.exception_handler(GoogleAuthError)
async def database_failure(request: Request, exc: Exception):
    return JSONResponse(status_code=503, content={"detail": "Database service unavailable; try again later"})


@app.get("/api/health", tags=["setup"])
def health() -> dict:
    """Public process liveness and configuration presence; does not probe cloud services."""
    return {
        "status": "ok", "service": "delivery-exception-api",
        "environment": get_settings().app_environment, "integrations": configuration_status(),
        "features": {"identity": True, "fleet_and_deliveries": True, "dispatch": False, "recovery": False, "feedback_learning": False},
    }


def run() -> None:
    import uvicorn
    uvicorn.run("logistics_api.main:app", host="127.0.0.1", port=8000)
