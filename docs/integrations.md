# Integration setup

## Google Cloud and Maps

Use a Google Cloud project with billing enabled. Enable Maps JavaScript API for the browser and Geocoding API plus Routes API for server tools. Create two separate keys:

1. Browser key: put it in frontend/.env.local as VITE_GOOGLE_MAPS_API_KEY. Restrict it to Maps JavaScript API and HTTP referrers for localhost:5173, 127.0.0.1:5173 and the deployed application domain.
2. Server key: put it in backend/.env as GOOGLE_MAPS_SERVER_API_KEY. Restrict it to Geocoding API and Routes API; use server egress IP restrictions where available. Never put this key in a VITE_ variable.

The frontend map loads only when a browser key is configured. Server tools are local MCP tools, not public FastAPI endpoints. Geocoding returns possible matches and flags partial/ambiguous matches for confirmation. Routes returns driving distance, duration and encoded polyline for two coordinates. It does not validate commercial vehicle road restrictions or optimize fleet allocations.

Fleet routing will use Route Optimization API in the subsequent delivery workflow. That requires separate enablement and authenticated server integration with shipment, capacity and time-window inputs; it is not replaced by point-to-point Routes API.

Do not persist Google route/geocoding responses as an unrestricted permanent dataset; review provider storage and attribution terms before implementing data retention. Configure quotas in Cloud Console before live use.

## Firebase

Create/select a Firebase project and register a web application. Enable the selected Authentication sign-in provider and create Firestore. Copy public web settings into frontend/.env.local; use matching FIREBASE_PROJECT_ID in backend/.env. Cloud server access uses Application Default Credentials. Local emulation uses the demo-agent-war project and the checked-in emulator configuration.

Install Java 21+ for Firestore emulation. Run `bun run emulators`. Client security rules intentionally deny access until organization-scoped membership rules are implemented. Admin SDK backend calls require their own verified user and organization checks before CRUD is exposed.

## Agent execution and improvement

See backend/README.md for the ADK runner, tool correction plugin, evaluation, offline optimization and optional Langfuse setup. Tool request correction during an invocation is distinct from improving instructions across evaluated examples. Neither establishes that dispatch is safe without transactional business checks and approval.

## External prerequisites

Code configuration cannot create billing accounts, obtain credentials or verify a live service without access. Maps, Gemini, Firebase cloud and Langfuse remain pending live verification until their environment settings are supplied. No remote resources are provisioned or deployed by these scripts.

## References

- https://developers.google.com/maps/documentation/javascript/load-maps-js-api
- https://developers.google.com/maps/documentation/routes/compute_route_directions
- https://developers.google.com/maps/documentation/geocoding/requests-geocoding
- https://firebase.google.com/docs/emulator-suite/install_and_configure
- https://adk.dev/optimize/
- https://adk.dev/integrations/langfuse/
