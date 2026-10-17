# Frontend

Vite, React, TypeScript, Tailwind CSS v4 and local shadcn/ui components. Bun manages dependencies.

```powershell
bun install
Copy-Item .env.example .env.local
bun run dev
```

Open http://localhost:5173. `bun run build` checks TypeScript and produces `dist/`. `bun run typecheck` checks types. `bun run lint` checks source conventions.

## Configuration

- `VITE_API_BASE_URL`: backend origin, defaults to `http://127.0.0.1:8000`. Authenticated API calls attach a fresh Firebase ID token. Start the Python API before using operational screens.
- `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID`: Firebase web app settings. All four are required before the client initializes. They are public identifiers, not service account credentials.
- `VITE_USE_FIREBASE_EMULATORS`: `true` connects Auth at `127.0.0.1:9099` and Firestore at `127.0.0.1:8080` in Vite development mode only.

Restart Vite after editing environment variables. Keep secrets and service account files out of the frontend; every Vite-prefixed value is included in the browser bundle.

## Current scope

The public landing page is `/`. It uses the TasteSkill well-kept board direction with a read-only workspace explorer, getting-started panels, FAQs, reduced-motion support, and credited photographs. `/app` opens the authenticated workspace; `/app?mode=signup` opens registration for signed-out visitors. The landing page does not require Firebase or a running backend to render. Unknown routes show a page-not-found message.

The responsive dashboard supports email/password account creation, sign-in, sign-out, organization onboarding and workspace selection. Enable Email/Password in Firebase Authentication. Once signed in, the backend verifies the Firebase ID token and returns the user's memberships. A new workspace makes the creator its owner.

Delivery and fleet screens create, list, edit and delete real records through the backend. Owners and dispatchers can write; other roles cannot. Updates and deletions include record versions so stale edits are rejected. Lists load 100 records at a time with a Load more button; displayed counts describe only loaded records. Delivery windows use the operator's local timezone in forms and UTC on the API. Coordinates are optional pairs; records with coordinates appear on the map. No browser database writes or sample operational records are used.

The operations map has loading, timeout, network and authorization error states. Recovery, assignment and dispatch workflows remain later phases. A configured Firebase client does not prove a successful authenticated database connection: Firestore, backend credentials and provider setup are required.

## Google Maps setup

1. Select a Google Cloud project, attach billing, and enable **Maps JavaScript API**. Firebase project configuration alone does not enable Maps.
2. Create a separate browser API key. Set application restrictions to **Websites (HTTP referrers)**, allowing `http://localhost:5173/*`, `http://127.0.0.1:5173/*`, and your deployed HTTPS domain. Allow additional ports only when you use them. Restrict the key to **Maps JavaScript API**.
3. Set `VITE_GOOGLE_MAPS_API_KEY` in `.env.local`. This browser key is public; its restrictions are essential. Never use a server routing key here.
4. Optionally set `VITE_GOOGLE_MAPS_MAP_ID` to a JavaScript map ID created in Cloud Console. A map ID is optional for this base map. Set `VITE_MAP_CENTER_LAT` and `VITE_MAP_CENTER_LNG` to your preferred initial viewport; defaults show India and do not represent operational locations.
5. Restart Vite. Open the dashboard and confirm map tiles render. Authorization errors point to billing, API activation or referrer restrictions; the browser console provides Google's exact error code.

The browser integration is implemented; cloud provisioning and a live authenticated map require your Google Cloud configuration. Routes API and Route Optimization API belong to the backend with separately restricted credentials. They are not required just to display this map. Set usage quotas and billing alerts for the Cloud project.

References: [API loading](https://developers.google.com/maps/documentation/javascript/load-maps-js-api), [key restrictions](https://developers.google.com/maps/api-security-best-practices), [map errors](https://developers.google.com/maps/documentation/javascript/error-messages).

shadcn components live in `src/components/ui/`, with aliases and theme configuration in `components.json`. The initial button and card components were manually scaffolded using shadcn conventions because registry access prevented CLI generation. They use the standard Slot, class-variance-authority and `cn` pattern. To add components after installation: `bunx shadcn@latest add <component>`.
