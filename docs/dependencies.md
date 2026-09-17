# Dependencies

Runtime libraries, external services, and environment variables.

## Backend (Python)

`backend/requirements.txt` — the following are load-bearing:

| Package | Why |
| --- | --- |
| FastAPI 0.111 | Web framework + OpenAPI |
| SQLAlchemy 2.0.30 | ORM |
| Alembic 1.13.1 | Schema migrations |
| psycopg2-binary 2.9.9 | PostgreSQL driver (only DB driver in the deps) |
| pandas 2.2.2 | Ingestion, scoring vectorisation |
| numpy | Underlies pandas + Vaisala scoring matrix ops |
| openpyxl 3.1.4 | XLSX reading with hyperlinks and multi-sheet support |
| python-calamine ≥ 0.2 | Faster XLSX parsing (primary engine, openpyxl fallback) |
| geopandas ≥ 1.0 | Reads/writes shapefiles via pyogrio |
| pyogrio 0.12.x | Native GDAL bindings for geopandas |
| shapely ≥ 2.0 | Geometry mapping and shape operations |
| pyproj ≥ 3.6 | CRS transformations (network geometry reprojection to EPSG:4326) |
| anthropic ≥ 0.28 | Claude API SDK |
| pydantic 2.7 + pydantic-settings | Config + schema validation |
| python-jose 3.3 | JWT encode / decode (HS256) |
| passlib 1.7 + bcrypt 4.0 | Password hashing |
| python-dotenv 1.0 | `.env` loading |
| python-multipart | Multipart form parsing for uploads |

Notably not in `requirements.txt`:

- `fiona`, `pyshp` — not installed. All shapefile IO goes through geopandas + pyogrio.
- No test runner is declared; ad-hoc `pytest` is used against `backend/tests/`.

## Frontend (Node)

`frontend/package.json` — the following are load-bearing:

| Package | Why |
| --- | --- |
| React 18.3.1 + React DOM | UI |
| Vite 5.2.x | Dev server + build |
| axios 1.7.x | HTTP client |
| react-router-dom 6.23.x | Routing |
| leaflet 1.9.x + react-leaflet 4.2.x | Map rendering (react-leaflet pinned to v4 for React 18 compatibility) |
| recharts 2.12.x | Bar charts on Analysis page |
| papaparse | CSV parsing (used by upload preview and some fallback paths) |

## External services

- **PostgreSQL** — connection string from `DATABASE_URL`. Connection pool is 10 steady + 20 overflow (`backend/database.py`).
- **Anthropic API** — key from `ANTHROPIC_API_KEY`. Model id from `LLM_MODEL` (default `claude-sonnet-4-5`). Called from `backend/services/llm.py` for full-run briefings, multi-turn queries, and per-section narratives.
- **OS Maps API** — key from `VITE_OS_MAPS_API_KEY` (frontend, injected into the bundle). When set, `MapTab` uses OS `Light_3857` raster tiles; otherwise it falls back to OpenStreetMap tiles. The key sits in the browser bundle; restrict by HTTP referrer on the OS Data Hub project before deploy.

## Environment variables

### Backend (`.env` at repo root, consumed by `backend/config/__init__.py`)

Required:
- `ANTHROPIC_API_KEY`
- `DATABASE_URL`
- `JWT_SECRET`

Optional (defaults in parentheses):
- `ENVIRONMENT` (`development`) — `development` | `production`; only affects log level.
- `LLM_MODEL` (`claude-sonnet-4-5`)
- `ALLOWED_ORIGINS_RAW` (`http://localhost:5173,http://localhost:3000`) — comma-separated CORS list.
- Scoring weights and thresholds (see [analytical-models.md](./analytical-models.md) for the full list): `CI_*`, `DD_*`, `EDI_*`, `REACTIVE_*`, `RISK_*`, `SCORING_VERSION`.

### Frontend (`frontend/.env.local`, `.env.example` template)

- `VITE_OS_MAPS_API_KEY` — see above.
- `VITE_API_BASE_URL` — optional axios base URL override; empty (default) means same origin.

Only vars prefixed with `VITE_` reach the browser bundle.

## Reference implementation (not code, referenced by design)

`vaisala_dst_handoff/priority_dst.html` — the original single-file browser tool. Backend logic mirrors its scoring, RAG threshold derivation, defect groups, dedup rule, 100m sub-group chunking, urban-always-section brief, and percentile-treatment mode. Any behaviour question about the Vaisala DST should first be checked against this file.
