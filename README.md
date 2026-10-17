# Delivery Exception Manager

A setup foundation for recovering deliveries after a vehicle breakdown.

## Stack

- Frontend: Bun, Vite, React, TypeScript, Tailwind and shadcn/ui.
- Backend: uv, Python, FastAPI, Google ADK, MCP and Firebase Admin.
- Database and identity: Cloud Firestore and Firebase Authentication.

## Install

Use Bun 1.4+ and uv. uv provisions the backend's pinned Python version.

```powershell
bun install
bun install --cwd frontend
uv sync --directory backend
bun run setup:env
```

Run both apps concurrently from the repository root:

```powershell
bun run dev
```

Frontend: http://localhost:5173. Backend API docs: http://127.0.0.1:8000/docs. MCP: http://127.0.0.1:8001/mcp. The dev command starts all three processes. Individual processes: `bun run dev:frontend`, `bun run dev:backend`, `bun run dev:mcp`.

The current restricted environment passed frontend typecheck/lint and backend health checks, but denies child processes required by the Vite build (`spawn EPERM`). Repeat `bun run build` in a normal terminal. Root dependencies were installed with lifecycle scripts disabled after an EPERM error; review needed lifecycle scripts when installing outside this environment. See handoff.md for precise verification boundaries.

## Firebase

The default Firebase CLI project is `demo-agent-war`, which targets local emulation. Install Java 21+ before running the Firestore emulator:

```powershell
bun run emulators
```

Set matching project IDs and emulator options in frontend/backend environment files. Emulator UI: http://127.0.0.1:4000. See each application's README for exact settings. Firestore rules deny all client access until organization membership and access rules are implemented. Server SDK access must be authorized separately in the backend.

For a real Firebase project, register a web application, enable Authentication and Firestore, set the web config in frontend/.env.local and project ID in backend/.env. Configure Application Default Credentials on the backend; keep service account keys outside the repository. Do not expose Gemini or server credentials through Vite variables. No cloud resources are provisioned by this setup.

## Agent and MCP

See backend/README.md for Gemini, bounded ADK tool correction, evaluation, GEPA optimization and optional Langfuse tracing/feedback. Start the MCP service, then run `bun run agent "Check service configuration"`. Current tools inspect configuration, geocode addresses and compute driving routes. Delivery mutations and fleet recovery remain product work.

Google Maps browser and server credentials are separate. See [integration setup](docs/integrations.md) and frontend/README.md for required APIs, billing, referrer restrictions and environment fields. No cloud resources or credentials are created by local setup.

## Checks and planning

```powershell
bun run build
bun run lint
```

See [plan.md](plan.md), [todo.md](todo.md), and [handoff.md](handoff.md) for scope and current evidence. Google Maps and business workflows are subsequent work.
