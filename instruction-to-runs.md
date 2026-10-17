# AgentWars Recovery Demo: Run Instructions

This guide runs the backend vehicle-breakdown recovery demo from a clean checkout.

The demo uses:

- Python 3.12 managed by `uv`
- FastAPI
- Google ADK multi-agent orchestration
- Gemini `gemini-3.8-flash` when an API key is configured
- Persistent local SQLite demo storage by default
- Optional Firebase Cloud Firestore persistence
- Deterministic synthetic distance and ETA values by default

Synthetic routing is intentional. It makes no Google Maps API calls and must not be described as live road distance or driving ETA.

## 1. Prerequisites

Install:

- Git
- Python 3.12+
- `uv`

Verify:

```powershell
git --version
uv --version
```

Clone the repository:

```powershell
Set-Location agent-war
```

## 2. Install Backend

From the repository root:

```powershell
uv sync --directory backend --locked
```

Create a local environment file from the example:

```powershell
Copy-Item backend/.env.example backend/.env
```

For the easiest no-credential demo, edit `backend/.env` and use:

```dotenv
APP_ENVIRONMENT=development
DATA_MODE=local_demo
ROUTING_MODE=synthetic_demo
GOOGLE_API_KEY=
GEMINI_MODEL=gemini-3.8-flash
```

`backend/.env` is ignored by Git. Never commit API keys, Firebase service-account files, or Firebase ID tokens.

## 3. Run The API

Start the backend in one terminal:

```powershell
uv run --directory backend logistics-api
```

The API is available at:

- Health: http://127.0.0.1:8000/api/health
- OpenAPI: http://127.0.0.1:8000/docs

Check health from a second terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health | ConvertTo-Json -Depth 5
```

## 4. Run The Local Demo

The administrator CLI is the quickest way to test without authentication.

Seed the repeatable demo data:

```powershell
uv run --directory backend logistics-demo seed
```

Run the successful recovery scenario:

```powershell
uv run --directory backend logistics-demo run --scenario A
```

Expected result:

- Outcome: `resolved`
- Broken vehicle: `V-101`
- Pending shipments: 6
- Selected vehicle: `V-204`
- All 6 shipments reassigned to `V-204`
- Evidence source: `synthetic_demo`
- Distance and ETA are explicitly mock values

Reset and run the escalation scenario:

```powershell
uv run --directory backend logistics-demo reset
uv run --directory backend logistics-demo run --scenario B
```

Expected result:

- Outcome: `manual_intervention_required`
- Broken vehicle: `V-201`
- Pending shipments: 12
- No replacement vehicle selected
- Shipment assignments remain unchanged
- A simulated dispatcher notification is recorded

The local database is stored at `backend/.local/recovery.sqlite3`. It is ignored by Git and is labelled as local demo storage in API responses.

## 5. Test The API Directly

With `DATA_MODE=local_demo`, no Firebase token is required.

Reset the local data:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/demo/reset `
  -ContentType "application/json" `
  -Body '{"preserve_policy":false}'
```

Create a breakdown:

```powershell
$incident = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/incidents/simulate `
  -ContentType "application/json" `
  -Body '{"scenario":"A"}'
$incident | ConvertTo-Json -Depth 6
```

Resolve it through the ADK workflow:

```powershell
$run = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/incidents/$($incident.incident_id)/resolve"
$run | ConvertTo-Json -Depth 10
```

Submit positive feedback:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/recovery-runs/$($run.run_id)/feedback" `
  -ContentType "application/json" `
  -Body '{"rating":"good"}' | ConvertTo-Json -Depth 6
```

Submit negative distance feedback instead:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/recovery-runs/$($run.run_id)/feedback" `
  -ContentType "application/json" `
  -Body '{"rating":"needs_improvement","reason":"too_far"}' | ConvertTo-Json -Depth 6
```

The bounded policy update is stored in `policy_settings`. It cannot override same-route, availability, freshness, capacity, or single-vehicle safety checks.

Inspect the complete dashboard:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/dashboard | ConvertTo-Json -Depth 12
```

## 6. Understand The Agent Workflow

The workflow is request-driven. There is no polling loop, driver mobile endpoint, or background agent in this MVP.

```text
Dispatcher
  -> simulate incident
  -> IncidentCommander (Google ADK LlmAgent)
       -> AgentTool: FleetAnalyst
            -> analyze_fleet Python tool
       -> AgentTool: RecoveryPlanner
            -> plan_recovery Python tool
       -> execute_recovery Python tool
            -> transactionally revalidate and assign or escalate
```

The LLM coordinates the roles. Python owns all safety decisions and Firestore/SQLite mutations. The model cannot invent a vehicle ID, split shipments, search another route, bypass capacity, or write directly to the database.

The Mermaid versions of this graph are in:

- `README.md`
- `backend/README.md`

## 7. Run Tests

Run all backend tests:

```powershell
uv run --directory backend python -m unittest discover -s tests -v
```

The suite covers:

- Successful six-shipment recovery
- Twelve-shipment escalation
- Same-route filtering
- Capacity validation
- Location freshness and invalid coordinates
- Synthetic routing and Maps response validation
- Distance-first ranking and ETA tie-breaks
- Duplicate and concurrent execution protection
- Transaction rollback on stale fleet changes
- Feedback policy persistence and bounds
- Actual credential-free ADK delegation
- API validation and authentication boundaries

## 8. Use Gemini ADK

With a Gemini key, set this in `backend/.env`:

```dotenv
GOOGLE_API_KEY=your_backend_only_key
GEMINI_MODEL=gemini-3.8-flash
```

Check that the model is available without making an inference call:

```powershell
uv run --directory backend logistics-models --check gemini-3.8-flash
```

The ADK workflow will report `agent_mode: gemini` when it uses Gemini. Without the key, it reports `adk_scripted_demo`; this still exercises the real ADK delegation graph but does not claim Gemini inference.

Gemini quota, billing, and model availability are controlled by the Google account. A model-list success does not guarantee that an inference request will have quota.

## 9. Optional Firestore Mode

Cloud mode is optional. Use a dedicated recovery workspace because this MVP ledger uses parcel counts and `assigned_shipment_ids`, while the existing CRUD API uses kg-based delivery records.

Required backend settings:

```dotenv
APP_ENVIRONMENT=development
DATA_MODE=firestore
ROUTING_MODE=synthetic_demo
GOOGLE_CLOUD_PROJECT=your_project_id
FIREBASE_PROJECT_ID=your_project_id
GOOGLE_APPLICATION_CREDENTIALS=C:/secure/path/service-account.json
RECOVERY_WORKSPACE_ID=agentwars-recovery-demo
```

Seed only a new, dedicated, empty workspace:

```powershell
uv run --directory backend logistics-demo seed `
  --confirm-project your_project_id `
  --dispatcher-uid existing_firebase_user_uid
```

Cloud HTTP endpoints require a Firebase ID token and `owner` or `dispatcher` membership in the configured recovery workspace:

```powershell
$headers = @{ Authorization = "Bearer $env:FIREBASE_ID_TOKEN" }
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/dashboard -Headers $headers
```

Do not put a service-account key, Firebase ID token, or Gemini key in this repository. Do not use an operational business workspace for the demo seed.

## 10. Routing Modes

Default demo mode:

```dotenv
ROUTING_MODE=synthetic_demo
```

This uses deterministic coordinate math and produces clearly labelled synthetic distance/ETA values. It does not call Maps.

Optional live mode:

```dotenv
ROUTING_MODE=google_maps
GOOGLE_MAPS_API_KEY=your_backend_only_routes_key
```

Live mode sends only already-eligible same-route vehicle origins to Routes API `computeRouteMatrix`. If the provider fails or returns incomplete route evidence, the candidate is unavailable and the workflow escalates. It does not silently use synthetic or straight-line values in cloud mode.

## 11. Troubleshooting

### `ModuleNotFoundError` or wrong Python version

Run commands through `uv`, not the system Python:

```powershell
uv sync --directory backend --locked
uv run --directory backend logistics-api
```

### Local demo says Firestore is unavailable

Set `DATA_MODE=local_demo` and restart the backend. Local mode is intentionally separate from Firestore.

### Cloud requests return `401` or `403`

The Firebase ID token must be valid and its UID must have `owner` or `dispatcher` membership in `RECOVERY_WORKSPACE_ID`.

### Gemini returns `429 RESOURCE_EXHAUSTED`

The account has exceeded its current model quota. Wait for the provider retry window, check billing/rate limits, or temporarily clear `GOOGLE_API_KEY` to use the scripted ADK demo. Do not change the deterministic safety workflow to work around quota.

### A repeated resolve returns `409`

This is expected. Completed incidents cannot be executed twice. Reset the local demo or create a new incident.

### Frontend is not available

Frontend work is intentionally paused. Use the API, OpenAPI page, or `logistics-demo` CLI for this backend MVP.

## 12. Stop And Reset

Stop the API with `Ctrl+C`.

For local data, reset the scenario:

```powershell
uv run --directory backend logistics-demo reset
```

For cloud data, reset is disabled unless the workspace is explicitly marked as a demo, the environment is development, `ALLOW_CLOUD_DEMO_RESET=true`, and `ROUTING_MODE=synthetic_demo`. Cloud reset is destructive to that dedicated demo workspace.
