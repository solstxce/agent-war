# Handoff

## Objective and decisions
Build a real delivery exception manager, starting with vehicle breakdown recovery at one depot. Firestore is the database. Frontend uses Bun + Vite + React + TypeScript + shadcn/ui; Python uses uv + FastAPI, Google ADK and MCP. Dispatcher approval is required before changing assignments. Setup was split into concurrent frontend/backend work at the user's request.

## Current source
- frontend/: dashboard shell, empty operational states, backend health connectivity, Firebase client configuration, Tailwind/shadcn foundations, Google Maps loader and live-map component with loading/error states.
- backend/: FastAPI health endpoint, environment configuration, lazy Firestore initialization, ADK runner with bounded tool correction, read-only MCP status/geocoding/Routes tools, evaluation/optimization configurations, optional Langfuse tracing and operator feedback CLI.
- Root: Bun development scripts, Firebase emulator config, deny-by-default client rules, empty index definitions, plan.md and todo.md.

## Validation and environment boundaries
- Bun 1.4.2, Node 26.10.0 and uv 0.12.18 are available.
- System Python is 3.14; uv installed Python 3.12.14 and created backend/.venv.
- Six backend Python source files passed AST syntax parsing with existing Python. Four root JSON files parsed successfully.
- Initial package downloads failed with ConnectionRefused through the environment proxy. Per-process proxy overrides allowed downloads. Backend dependencies installed and backend/uv.lock was generated (75 packages).
- Backend API, MCP and ADK factory imports passed. FastAPI TestClient returned HTTP 200 from /api/health with emulator configuration present and all live integrations explicitly unverified. MCP transport and live model calls are not verified.
- Earlier ADK factory construction passed with a placeholder key (no live request). Updated MCP discovery returned get_service_status, geocode_address and compute_route. Invalid address/coordinates and absent-key responses were checked without network calls. Root Firebase CLI version probe stalled and was stopped, so CLI startup remains unverified.
- Frontend dependencies installed and frontend/bun.lock generated. Root dependencies and bun.lock generated with `bun install --ignore-scripts` after a lifecycle script hit EPERM. Root tool lifecycle scripts have not been run.
- Frontend `bun run typecheck` and root `bun run lint` passed. Production build passed TypeScript then failed with spawn EPERM in esbuild config loading. An alternative Bun/native config loader also failed on a denied cmd.exe child process in Vite. Build output and browser behavior are unverified in this restricted environment.
- Java was not found on PATH; Firestore emulator needs Java 21+.
- No live Firebase, Gemini or Maps credentials were supplied. No cloud provisioning/deployment was performed.

## Resume setup
1. Dependency locks now exist at bun.lock, frontend/bun.lock and backend/uv.lock. On a normal terminal run `bun install --frozen-lockfile`, `bun install --cwd frontend --frozen-lockfile`, and `uv sync --directory backend --locked`.
2. Run root dependency lifecycle scripts as needed and repeat the Vite production build outside the restricted process environment.
3. Copy environment examples as described in README.md. Install Java 21+ to run local Firebase emulators.
4. Run frontend build/lint and backend import/health/MCP checks; fix any issues revealed by installed dependency versions.
5. Run `bun run setup:env` to add missing settings without replacing existing values. `bun run dev` starts frontend, backend and MCP concurrently. Optionally run `bun run emulators` in another terminal.
6. Verify configured services before marking integration setup complete.

## Next product work
Implement identity and organization membership first, then delivery/fleet CRUD, transactional assignments, incident reporting and recovery proposals. Apply organization authorization inside backend/MCP tools; server Firestore SDK bypasses client rules. Current tool correction is bounded and sessions are in memory. Add durable job execution and outcome verification before dispatch recovery. GEPA produces offline candidate instructions; Langfuse feedback does not automatically modify the agent. Current source does not implement delivery management, authentication flows, dispatch, autonomous shipment recovery or learned policies. Point-to-point driving routes do not implement fleet optimization.

## Integration activation
See docs/integrations.md and both application READMEs. Populate separate Maps browser/server keys, Firebase settings and Gemini credentials. Optional Langfuse requires an existing project/host and keys. No live provider requests or paid evaluation/optimization runs have been performed. No secrets should be committed. Setup-env merges example field defaults while preserving local values.

## Latest dependency status
Backend base and observability extras installed; uv.lock includes evaluation and GEPA optional dependencies. Installing the eval extra failed building rouge-score with Windows temporary-directory PermissionError despite workspace TEMP/TMP. Evaluation/optimization execution is blocked until that optional installation completes. LocalEvalSampler import also requires pandas from the uninstalled eval extra. Do not report evaluation scores or prompt improvement as verified.
Setuptools/wheel were installed as local build helpers. A subsequent `uv sync --all-extras --no-build-isolation-package rouge-score --inexact` attempt started large evaluation dependency downloads but made no further visible progress for several minutes and was stopped. Its build workaround is not verified.

Latest checks: Maps frontend TypeScript and ESLint pass; production build still fails with spawn EPERM. The three eval-set files validate against ADK EvalSet. Eval criteria and GEPA optimizer configuration validate. Langfuse/OpenInference imports pass and disabled telemetry returns without making a connection. Updated App/Runner construction passes with the recovery plugin, two retries and twelve-call limit using a placeholder key. No model invocation was made.
