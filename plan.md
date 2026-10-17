# Delivery Exception Manager: implementation plan

## Goal
Help a dispatcher recover remaining deliveries after a vehicle breakdown. Start with one depot. Firestore is the operational database; users manage records through the application.

## Architecture
- Frontend: Bun, Vite, React, TypeScript, Tailwind, shadcn/ui.
- Backend: uv-managed Python, FastAPI, Firebase Admin SDK and Firestore.
- Agent: Google ADK and Gemini consuming typed logistics tools through MCP.
- Maps: Google Maps display and Route Optimization API after the core workflow.
- Auth: Firebase Authentication, organization membership and backend authorization.

## Delivery stages
1. Bootstrap both applications concurrently, configuration, dependency locks, health connectivity, MCP/ADK scaffold, Firebase emulator config and documentation.
2. Add authentication, organization membership, delivery/vehicle models, CRUD and transactional assignment validation.
3. Add breakdown reporting and feasible recovery proposals for dispatcher approval.
4. Add ADK orchestration through authorized MCP tools, bounded repair attempts, idempotent execution and persisted outcome verification.
5. Add routing, recorded dispatcher corrections, recovery evaluations and operational metrics.

## Integration foundations added
Google Maps rendering and MCP geocoding/driving-route adapters are wired. ADK App/Runner uses bounded reflect-and-retry. Evaluation and GEPA configurations support offline candidate instruction improvements; optional Langfuse exports traces and operator scores. These are integration foundations. Fleet optimization, durable recovery and delivery CRUD remain subsequent product work.

## Recovery contract
Observe -> propose -> validate -> approve -> execute -> verify. Validation failures may trigger bounded revised proposals. Check persisted state before retrying mutations. Escalate infeasible plans. Store feedback with original state, proposal, correction and verified outcome; evaluate improvements before activation.

## Setup boundaries
Setup provides runnable applications and integration foundations. It does not claim working dispatch, production authentication, autonomous recovery or learned improvements. Live Firebase/Gemini/Maps require project configuration and credentials. No deployment is part of setup.
