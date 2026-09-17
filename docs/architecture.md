# Architecture

## Runtime topology

```
Browser (React 18 + Vite)                    Backend (FastAPI + Uvicorn)
────────────────────────                    ─────────────────────────
  React Router SPA                            /auth       auth router
  axios (JWT bearer)          HTTP JSON        /assets     assets router
  Leaflet + OS Maps API     ──────────►       /analysis   analysis router
                                              /vaisala    vaisala router
                                              /health     health probe
                                                    │
                                                    ▼
                                              SQLAlchemy 2.0 (ORM)
                                                    │
                                                    ▼
                                              PostgreSQL (psycopg2)

                                              Anthropic API ◄── services/llm.py
```

## Backend layout

`backend/main.py` mounts four routers, applies CORS from `settings.cors_origins`, and enforces a 500 MB upload cap. Uvicorn is the ASGI runner. Alembic drives schema migrations.

| Layer | Directory | Purpose |
| --- | --- | --- |
| Entry | `backend/main.py` | ASGI app, middleware, router mounting, `/health` |
| Config | `backend/config/__init__.py` | Pydantic settings, env-var-driven scoring weights |
| DB | `backend/database.py` | SQLAlchemy engine (pool 10, overflow 20), `SessionLocal`, `Base` |
| Auth | `backend/services/auth.py`, `backend/routers/auth.py` | bcrypt + HS256 JWT, 8-hour expiry |
| ORM | `backend/models/{user,asset,vaisala}.py` | Declarative tables and relationships |
| Schemas | `backend/schemas/{auth,asset,vaisala}.py` | Pydantic request/response contracts |
| Ingestion | `backend/services/ingestion.py` | SCANNER, CVI, SCRIM, Reactive, Network parsers |
| Validation | `backend/services/validation.py` | Column presence, unit sanity, multi-year detection |
| Scoring | `backend/services/scoring.py` (asset), `backend/services/vaisala_scoring.py` (Vaisala DST) |
| LLM | `backend/services/llm.py`, `backend/services/knowledge.py` | Anthropic client, cached knowledge base |
| Routers | `backend/routers/{auth,assets,analysis,vaisala}.py` | HTTP surface |
| Migrations | `backend/alembic/versions/00[1-10]_*.py` | Schema evolution, sequentially numbered |

## Frontend layout

`frontend/src/main.jsx` renders `App.jsx`, which registers routes and wraps them in `Guard` (auth-required) or `PublicOnly` (unauthenticated-only). Global auth state lives in `context/AuthContext.jsx` and persists to `localStorage` (`ai_token`, `ai_user`).

| Concern | Location |
| --- | --- |
| Routing | `frontend/src/App.jsx` (BrowserRouter, 6 top-level routes) |
| API client | `frontend/src/api/client.js` (axios + JWT interceptor + 401 redirect) |
| Auth state | `frontend/src/context/AuthContext.jsx` (`useAuth`) |
| Pages | `frontend/src/pages/{Login,Dashboard,Upload,Analysis,Query,Vaisala}.jsx` |
| Shared UI | `frontend/src/components/*` (Layout, PriorityList, KPIStrip, AIBriefing, ChatInterface, DefectDriverChart, AssetDetailPanel, VaisalaSectionDetailPanel) |
| Styling | CSS custom properties in `frontend/src/index.css` (RAG colours, spacing tokens) |
| Env | `frontend/.env.local` — `VITE_OS_MAPS_API_KEY`, optional `VITE_API_BASE_URL` |

## Router surface (current)

### Auth
- `POST /auth/register`
- `POST /auth/login`

### Assets
- `POST /assets/upload/scanner` (also `/scanner/raw`, `/cvi`, `/cvi/raw`, `/scrim/raw`, `/reactive`, `/reactive/raw`, `/network`)
- `GET  /assets/`
- `GET  /assets/export`
- `GET  /assets/schema/aliases`
- `GET  /assets/network-stats`

### Analysis
- `POST /analysis/run` — full rescoring + LLM briefing, persisted to `AnalysisRun`
- `GET  /analysis/latest`
- `GET  /analysis/stats`
- `POST /analysis/query` — multi-turn LLM (uses cached `ALL_KNOWLEDGE`)
- `POST /analysis/asset/{nsg_ref}`
- `POST /analysis/vaisala/{section_id}`

### Vaisala
- `POST /vaisala/upload/raw` — XLSX/CSV, params `network_key`, `dedup_strategy`, `weights_json`
- `POST /vaisala/upload/shp` — pre-scored zipped shapefile
- `GET  /vaisala/surveys`
- `GET  /vaisala/surveys/{id}/stats` — params `merge_scale`, `split`, `treatment_mode`
- `GET  /vaisala/surveys/{id}/sections` — same params + `rag_band`, `treatment`, `sort_by`, `sort_dir`, `skip`, `limit`
- `GET  /vaisala/surveys/{id}/sections/all`
- `GET  /vaisala/surveys/{id}/export` — params include `format=csv|xlsx|shp`
- `POST /vaisala/network-geometry/upload`
- `GET  /vaisala/network-geometry/current`
- `GET  /vaisala/network-geometry/features?survey_id=…`
- `DELETE /vaisala/network-geometry/{id}`

Auth is enforced via `get_current_user` dependency injection everywhere except `/auth/*` and `/health`.

## Request lifecycle (representative)

`POST /vaisala/upload/raw` with an XLSX file:

1. Middleware enforces auth (`Authorization: Bearer <jwt>`) via `get_current_user`.
2. Router validates `network_key`, `dedup_strategy`, optional `weights_json`.
3. Body is buffered up to 500 MB and dispatched to `parse_raw_xlsx` (or `parse_raw_csv`).
4. `parse_raw_xlsx` runs: openpyxl hyperlink recovery → `_attach_extras_json_column` → optional dedup → `_aggregate_intervals` → `detect_weight_drift` → `_parse_info_sheet`.
5. Router persists `VaisalaSurvey`, bulk-inserts sections and intervals, records any `VaisalaRagDriftLog` rows.
6. Response returns `VaisalaUploadResult` (survey id, RAG summary, drift details, dup count, info meta, flattened-link warnings).

## Deployment assumptions

- Single-process Uvicorn with `--reload` for development. Production topology not codified; `settings.environment == "production"` merely raises log level to WARNING.
- Frontend served from Vite dev server on port 5173 in development. Production build is not wired into the backend; a reverse proxy is assumed.
- Database is PostgreSQL; the `psycopg2-binary` driver is the only DB driver in `requirements.txt`.
