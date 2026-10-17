# Frontend

Vite, React, TypeScript, Tailwind CSS v4 and local shadcn/ui components. Bun manages dependencies.

```powershell
bun install
Copy-Item .env.example .env.local
bun run dev
```

Open http://localhost:5173. `bun run build` checks TypeScript and produces `dist/`. `bun run typecheck` checks types. `bun run lint` checks source conventions.

## Configuration

- `VITE_API_BASE_URL`: backend origin, defaults to `http://localhost:8000`. The dashboard calls `/api/health` with a five second timeout.
- `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID`: Firebase web app settings. All four are required before the client initializes. They are public identifiers, not service account credentials.
- `VITE_USE_FIREBASE_EMULATORS`: `true` connects Auth at `127.0.0.1:9099` and Firestore at `127.0.0.1:8080` in Vite development mode only.

Restart Vite after editing environment variables. Keep secrets and service account files out of the frontend; every Vite-prefixed value is included in the browser bundle.

## Current scope

The responsive dashboard displays honest empty states and API connection status. Firebase Auth and Firestore clients are exported from `src/lib/firebase.ts`. The operations map loads Google Maps when configured, with loading, timeout, network and authorization error states. It displays no invented shipments or vehicles. Authentication screens, operational CRUD and recovery screens remain implementation work. A configured Firebase client does not prove a successful authenticated database connection.

## Google Maps setup

1. Select a Google Cloud project, attach billing, and enable **Maps JavaScript API**. Firebase project configuration alone does not enable Maps.
2. Create a separate browser API key. Set application restrictions to **Websites (HTTP referrers)**, allowing `http://localhost:5173/*`, `http://127.0.0.1:5173/*`, and your deployed HTTPS domain. Allow additional ports only when you use them. Restrict the key to **Maps JavaScript API**.
3. Set `VITE_GOOGLE_MAPS_API_KEY` in `.env.local`. This browser key is public; its restrictions are essential. Never use a server routing key here.
4. Optionally set `VITE_GOOGLE_MAPS_MAP_ID` to a JavaScript map ID created in Cloud Console. A map ID is optional for this base map. Set `VITE_MAP_CENTER_LAT` and `VITE_MAP_CENTER_LNG` to your preferred initial viewport; defaults show India and do not represent operational locations.
5. Restart Vite. Open the dashboard and confirm map tiles render. Authorization errors point to billing, API activation or referrer restrictions; the browser console provides Google's exact error code.

The browser integration is implemented; cloud provisioning and a live authenticated map require your Google Cloud configuration. Routes API and Route Optimization API belong to the backend with separately restricted credentials. They are not required just to display this map. Set usage quotas and billing alerts for the Cloud project.

References: [API loading](https://developers.google.com/maps/documentation/javascript/load-maps-js-api), [key restrictions](https://developers.google.com/maps/api-security-best-practices), [map errors](https://developers.google.com/maps/documentation/javascript/error-messages).

shadcn components live in `src/components/ui/`, with aliases and theme configuration in `components.json`. The initial button and card components were manually scaffolded using shadcn conventions because registry access prevented CLI generation. They use the standard Slot, class-variance-authority and `cn` pattern. To add components after installation: `bunx shadcn@latest add <component>`.
