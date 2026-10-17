# Todo

## Setup
- [x] Bootstrap Bun/Vite/React/TypeScript frontend and shadcn/ui conventions (Button/Card manually scaffolded; CLI generation pending).
- [x] Bootstrap uv/FastAPI backend and lock dependencies.
- [x] Configure lazy Firebase clients and environment examples.
- [x] Provide Google ADK and MCP foundations.
- [x] Add root development commands and Firebase emulator configuration.
- [ ] Verify setup and record evidence/limitations in handoff.md.
- [x] Frontend TypeScript and lint checks; backend imports and HTTP health smoke check.
- [ ] Complete production build outside restricted child-process permissions.
- [ ] Install Java 21+ and verify Firebase emulators.
- [x] Add Google Maps browser loader, viewport configuration and error states.
- [x] Add read-only MCP geocoding and point-to-point driving routes.
- [x] Add bounded ADK tool correction and runnable local agent.
- [x] Add evaluation datasets, heldout scenarios and offline GEPA configuration.
- [x] Add opt-in Langfuse tracing and operator feedback command.
- [x] Add environment merge command and concurrent frontend/backend/MCP startup.
- [ ] Activate and verify live Firebase, Gemini, Maps and optional Langfuse integrations with credentials.
- [ ] Finish optional ADK eval dependency installation (rouge-score temporary-directory PermissionError), then run credentialed evaluation/optimization.

## Product workflow
- [ ] Define delivery, vehicle, incident, recovery plan and feedback schemas.
- [ ] Implement Firebase login and organization/role authorization.
- [ ] Implement delivery and fleet management backed by Firestore.
- [ ] Implement transactional assignments and stale-plan rejection.
- [ ] Implement breakdown reporting and constraint-validated recovery proposals.
- [ ] Implement dispatcher approval and idempotent plan application.
- [ ] Connect ADK to authorized logistics MCP tools.
- [ ] Add bounded recovery, persisted jobs and outcome verification.
- [ ] Integrate Google Maps and route optimization.
- [ ] Capture corrections and evaluate repeat-mistake prevention.
