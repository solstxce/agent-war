# Backend setup



Python 3.12, uv, FastAPI, Google ADK, Firebase Admin, Firestore, and the official MCP Python SDK.



Run from `backend/` in PowerShell:



```powershell

uv sync --locked

Copy-Item .env.example .env

uv run logistics-api

```



API: http://127.0.0.1:8000/api/health. OpenAPI: http://127.0.0.1:8000/docs.

For automatic reload use `uv run uvicorn logistics_api.main:app --reload --host 127.0.0.1 --port 8000`.

Health describes configuration presence, not successful Firebase, Gemini, or MCP connections.

It starts without credentials and does not initialize Firestore or the agent.



## Firestore



The example environment selects the local Firestore emulator at `127.0.0.1:8080` with project `demo-agent-war`.

Start Firebase emulators using the root documentation. The lazy `get_firestore_client()` helper uses anonymous credentials only for local emulator development.

For cloud use your Firebase project ID, clear `FIRESTORE_EMULATOR_HOST`, and configure Google Application Default Credentials outside the repository.

Never commit service account keys. Server SDKs bypass Firestore Security Rules; organization membership and user authorization must be implemented before adding operational endpoints.



## MCP and ADK



In a separate terminal, from this directory:



```powershell

uv run logistics-mcp

```



The MCP endpoint is `http://127.0.0.1:8001/mcp` using Streamable HTTP.

The tools are `get_service_status`, `geocode_address`, and `compute_route`. They inspect setup, resolve addresses, and compute point-to-point driving routes. They cannot mutate deliveries.

This unauthenticated setup server binds to loopback; add authentication before exposing it remotely.



`logistics_api.agent.create_agent()` creates an ADK agent connected to that endpoint using `McpToolset` and `StreamableHTTPConnectionParams`.

Set `GOOGLE_API_KEY` and optionally `GEMINI_MODEL` in `.env` before construction.

The local `logistics-agent` CLI manages an ADK App, runner, session, and MCP cleanup; see below. No public chat endpoint is exposed.

Dispatch, reassignment, durable incident recovery, and automatic feedback learning remain future work.



## References



- [ADK MCP tools](https://github.com/google/adk-docs/blob/main/docs/tools-custom/mcp-tools.md)

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

- [Firestore emulator client setup](https://firebase.google.com/docs/emulator-suite/connect_firestore)

- [Firebase Admin setup](https://firebase.google.com/docs/admin/setup)



## Agent runtime, recovery, evaluation, and feedback



Start `uv run logistics-mcp`, set `GOOGLE_API_KEY`, then run:



```powershell

uv run logistics-agent "Check which services are configured"

# Optional ADK development UI (loopback only)

uv run adk web agents --host 127.0.0.1 --port 8002

```



The local CLI creates an ADK `App` and `Runner`, starts an in-memory session, and closes

MCP connections after the request. Sessions are not durable and no public chat endpoint is added.

The web UI is a local developer tool, not an authenticated dispatcher product.



`LogisticsRecoveryPlugin` extends ADK's `ReflectAndRetryToolPlugin` to detect structured

application errors inside MCP results, as well as tool exceptions. It allows two retries

per tool per invocation and raises when exhausted. `AGENT_TOOL_MAX_RETRIES` can be 0–5.

The CLI also limits each invocation to `AGENT_MAX_LLM_CALLS` (default 12, maximum 30).

Set `ADK_MAX_LLM_CALLS=12` when using ADK's CLI/web runners to apply their global limit.

Errors marked `retryable=false` are passed through unchanged; agent instructions require

escalation rather than repeated requests. This is tool-call recovery, not shipment recovery

or permanent learning. Backend business constraints and durable workflows remain future work.



### Evaluation and instruction optimization



Install optional dependencies with `uv sync --extra eval` (or `--all-extras` for telemetry too).

Run these commands from `backend/` with MCP running and Gemini configured:



```powershell

uv run --extra eval adk eval agents/dispatcher agents/dispatcher/train.evalset.json --config_file_path evaluation/test_config.json

uv run --extra eval adk eval agents/dispatcher agents/dispatcher/heldout.evalset.json --config_file_path evaluation/test_config.json

uv run --extra eval adk optimize agents/dispatcher --sampler_config_file_path evaluation/sampler.json --optimizer_config_file_path evaluation/optimizer.json --print_detailed_results

```



These make paid model calls; route cases can also make Maps calls. They are not executed at

startup. Train and validation sets cover setup inspection, missing route inputs, unsupported

dispatch, and route-tool selection. The heldout set is reserved for review after optimization.

The initial criterion checks expected tool trajectories only. It does not certify factual

answers, route accuracy, safety, or actual recovery. Expand with recorded tool failures and

human-reviewed response rubrics before treating scores as production readiness.



ADK's GEPA command optimizes root-agent instructions against the train/validation sets and

prints a candidate; intermediate artifacts go to `artifacts/optimization`. It does not edit

our source or activate a candidate. Review its output, evaluate on heldout scenarios, and

version an accepted prompt through normal code review. The optimizer operates on the root

agent; App runtime plugins are not themselves optimized. Twelve metric calls is an initial

budget cap, not a guaranteed dollar-cost limit.



### Optional Langfuse



`uv sync --extra observability` installs Langfuse and Google ADK OpenInference instrumentation.

Set the following in `backend/.env` only when trace export is desired:



```dotenv

LANGFUSE_ENABLED=false

LANGFUSE_PUBLIC_KEY=

LANGFUSE_SECRET_KEY=

LANGFUSE_BASE_URL=

AGENT_TOOL_MAX_RETRIES=2

AGENT_MAX_LLM_CALLS=12

```



When enabled, the local agent runner and ADK app initialize instrumentation before executing

requests. Trace content can include prompts and tool arguments, including addresses; use

synthetic data until your telemetry retention and access policies are established. No export

or Langfuse connection is initialized while disabled. To attach a correction to an existing

trace from an operator terminal:



```powershell

uv run --extra observability logistics-feedback YOUR_TRACE_ID --score 0 --comment "The destination needs clarification."

```



The command needs Langfuse credentials; no unauthenticated HTTP feedback endpoint is exposed.

Feedback annotates a trace. It does not update prompts or train the agent automatically.



References: [ADK recovery plugin](https://github.com/google/adk-python/blob/main/src/google/adk/plugins/reflect_retry_tool_plugin.py),

[ADK evaluation](https://google.github.io/adk-docs/evaluate/),

[Langfuse ADK integration](https://langfuse.com/integrations/frameworks/google-adk).


Current Windows sandbox setup note: base and observability dependencies installed successfully.
Installing the eval extra is blocked here while building `rouge-score==0.1.2`: setuptools
cannot access its temporary wheel metadata directory (`WinError 5`). A retry with workspace
`TEMP`/`TMP` had the same result. The extra is resolved in `uv.lock`, but evaluation/GEPA
execution has not been verified. Retry `uv sync --all-extras` in a normal local terminal.


## P0: authenticated fleet and delivery foundation

All operational API requests require `Authorization: Bearer <Firebase ID token>`.
`/api/health` remains public and reports configuration presence only. Enable Email/Password
sign-in in Firebase Authentication. The browser obtains tokens; backend Firebase Admin
verifies them and checks stored workspace membership on every operational request.

Cloud mode uses Application Default Credentials and `FIREBASE_PROJECT_ID`, or an explicit
`GOOGLE_APPLICATION_CREDENTIALS` service-account path in `backend/.env`. From the repository
root, `bun run setup:firebase-admin "C:/path/to/service-account.json"` validates the file
type/project and saves only its path. Restart the backend after configuration. For local
emulators set `APP_ENVIRONMENT=development`, `FIRESTORE_EMULATOR_HOST=127.0.0.1:8080`,
and `FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099`. Both emulator overrides are rejected
outside development. Never use emulator mode for an exposed production backend.

- `GET /api/me`: identity and memberships.
- `POST /api/workspaces` with `{ "name": "My depot" }`: idempotently create the signed-in
  user's owner workspace. Repeated requests return its original name and ID.
- `GET /api/organizations/{org_id}/deliveries` and `/vehicles`: paginated `{items,next_cursor}`;
  query `limit` (1–100) and optional `cursor` from the previous response.
- `POST` either collection: create an unassigned operational record.
- `PUT /api/organizations/{org_id}/{deliveries|vehicles}/{id}`: full replacement fields
  plus current `version`. Stale writes return 409.
- `DELETE` the same record path with `?expected_version=1`: stale deletes return 409.

Delivery fields: `customer_name`, `address`, `load_kg`, optional paired `latitude` and
`longitude`, optional paired timezone-aware `window_start` and `window_end`, and
`status` (only `pending` in P0). Vehicle fields: `registration`, `driver_name`,
`capacity_kg`, `available`, optional paired coordinates. Backend owns IDs, organization,
versions, timestamps, and roles. Unexpected input fields are rejected. Owners and
dispatchers may manage these records; drivers have no operational API access until P1.
Registration uniqueness is not enforced in P0; shipment assignment and dispatch are P1.

Firestore paths: `organizations/{org}/members/{uid}`, `organizations/{org}/deliveries/{id}`,
`organizations/{org}/vehicles/{id}`, and private membership index `users/{uid}`.
There is deliberately no operational MCP tool access yet: agent execution needs a
scoped authenticated identity before it can safely mutate this data.

