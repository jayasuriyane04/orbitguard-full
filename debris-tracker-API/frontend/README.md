# ORBITGUARD frontend

Next.js (App Router) + TypeScript mission-control dashboard for the
ORBITGUARD backend, with a CesiumJS 3D orbital map.

## Setup

```bash
npm install                 # postinstall copies Cesium's static assets into public/cesium
cp .env.example .env.local  # set NEXT_PUBLIC_API_BASE_URL / NEXT_PUBLIC_API_KEY
npm run dev
```

## Environment variables

See [`.env.example`](.env.example):

- `NEXT_PUBLIC_API_BASE_URL` -- backend URL (e.g. `http://localhost:8000`)
- `NEXT_PUBLIC_API_KEY` -- must match one of the backend's `DEBRIS_TRACKER_API_KEYS`
- `NEXT_PUBLIC_CESIUM_ION_TOKEN` -- optional; without it, the 3D map uses Cesium's
  bundled Natural Earth II imagery (no token, no network call)

## Pages

| Route | Page |
|---|---|
| `/` | Overview dashboard -- analytics cards + charts |
| `/map` | 3D orbital map (CesiumJS) -- live positions, layer toggles, click for detail |
| `/objects` | Object catalog -- filter/search/paginate |
| `/objects/[noradId]` | Object detail -- elements + short trajectory chart |
| `/conjunctions` | Conjunction list -- filter by severity, trigger a screening pass |
| `/conjunctions/[eventId]` | Conjunction detail -- risk factor breakdown + avoidance maneuver simulator |
| `/debris` | Debris removal priority -- ranked, with per-object explanation |
| `/cascade` | Kessler cascade simulator -- no-intervention / avoidance / removal comparison |
| `/alerts` | Alerts -- filter by status, acknowledge |

## Design

Dark ops-console theme grounded in real telemetry/mission-control
conventions rather than generic "sci-fi dashboard" styling: hairline
borders instead of shadows or rounded cards, monospace for numeric
readouts (NORAD IDs, coordinates, risk scores), and severity color
(cyan/amber/orange/red) reserved strictly for risk signal so it stays
meaningful. See `app/globals.css` for the token values.

## Notes / known limitations

- Cesium's static assets (`Assets/`, `Widgets/`, `Workers/`, `ThirdParty/`)
  are copied into `public/cesium/` by `scripts/copy-cesium-assets.js`
  (runs via `postinstall`) rather than via a bundler plugin, so it works
  under both webpack and Turbopack.
- The map fetches one state vector per visible object (capped at 150 for a
  hackathon-scale catalog) rather than requiring a batch endpoint --
  documented as a scaling limitation in the main README.
- Selected-object trajectory polylines on the 3D map plot raw ECI
  coordinates directly, which is a reasonable short-window visual
  approximation but is not corrected for Earth's rotation -- fine for the
  ~1-2 hour trails currently used, would need an ECI->ECEF rotation for
  longer trails.
- No automated frontend tests yet -- see the main README roadmap.

## Build

```bash
npm run build
npm run start
```

Or via Docker from the repo root: `docker compose up --build` (see the
main [README](../README.md)).
