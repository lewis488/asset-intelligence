# Architecture

## Overview

Asset Intelligence Platform is a Decision Support Tool (DST) for UK local highway authorities.
Two-tier web application: React + Vite frontend, Python + FastAPI backend, PostgreSQL database.
AI layer uses Anthropic Claude API for narrative briefings and free-text queries.
Deployed on Railway (production). Frontend at www.roadiq-dst.com. Backend on separate Railway domain.

## Directory Structure

```
asset-intelligence/
├── backend/               ← FastAPI application root (Railway working directory)
│   ├── main.py            ← app factory, router registration, CORS
│   ├── config.py          ← Pydantic Settings, env var loading
│   ├── database.py        ← SQLAlchemy engine, session factory, Base
│   ├── dataset_schemas.py ← DatasetSchema definitions for validation layer
│   ├── models/
│   │   ├── asset.py           ← 12 SQLAlchemy models (see database.md)
│   │   ├── user.py            ← User, Authority
│   │   ├── vaisala.py         ← VaisalaSection, VaisalaInterval, VaisalaSurvey
│   │   └── vaisala_programme.py ← VaisalaProgramme, VaisalaProgrammeItem, VaisalaProgrammeReview, VaisalaAuthorityPolicy
│   ├── routers/
│   │   ├── assets.py          ← /assets/* — upload, list, export, map-data, scoring
│   │   ├── analysis.py        ← /analysis/* — AI briefing, query, stats
│   │   ├── vaisala.py         ← /vaisala/* — Vaisala upload, view, export, treatment assessment
│   │   ├── vaisala_programme.py ← /vaisala/surveys/{id}/programme/* — action programme, policies, snapshots, reviews
│   │   └── auth.py            ← /auth/* — register, login, JWT
│   ├── services/
│   │   ├── ingestion.py       ← all data parsers (SCANNER/CVI/SCRIM/reactive/network)
│   │   ├── scoring.py         ← standalone scoring engine (see technical-debt.md)
│   │   ├── vaisala_scoring.py ← Vaisala DST scoring engine (scores, RAG, defect groups)
│   │   ├── vaisala_treatments.py ← evidence-led treatment candidate screening (vaisala-candidates-v1)
│   │   ├── vaisala_action_rules.py ← deterministic action routing rules (vaisala-programme-v2)
│   │   ├── vaisala_programme.py ← programme generation, ranking, snapshots, review logic
│   │   ├── vaisala_programme_exports.py ← CSV/XLSX/GeoJSON programme exports
│   │   ├── vaisala_qc.py      ← QC metric calculation
│   │   ├── validation.py      ← DatasetValidator, schema-first validation
│   │   ├── llm.py             ← Anthropic SDK wrapper, prompt construction
│   │   ├── knowledge.py       ← domain knowledge base injected into LLM system prompt
│   │   └── auth.py            ← JWT creation, password hashing
│   ├── schemas/           ← Pydantic request/response schemas
│   ├── alembic/           ← database migrations
│   └── docs/              ← this directory
├── frontend/              ← React + Vite application
│   ├── src/
│   │   ├── pages/         ← Dashboard, Upload, Analysis, Vaisala, Login
│   │   └── components/    ← shared components
│   └── vite.config.js     ← proxy: /api → localhost:8001
└── CLAUDE.md              ← Claude Code session context (project root)
```

## Service Separation

Designed for separation of concerns (documented in README.md, though README is stale — see database.md):

| Service | File | External dependencies |
|---------|------|-----------------------|
| Scoring engine | `services/scoring.py` | None (pure Python dataclasses) |
| Vaisala scoring | `services/vaisala_scoring.py` | pandas, numpy, geopandas |
| Vaisala treatment candidates | `services/vaisala_treatments.py` | None (pure logic over scoring output) |
| Vaisala action rules | `services/vaisala_action_rules.py` | None (deterministic routing, no DB) |
| Vaisala programme | `services/vaisala_programme.py` | SQLAlchemy (programme/snapshot/review persistence) |
| Vaisala programme exports | `services/vaisala_programme_exports.py` | openpyxl, geopandas |
| Data parsing | `services/ingestion.py` | pandas, openpyxl, geopandas |
| Validation | `services/validation.py` | pandas |
| LLM layer | `services/llm.py` | anthropic SDK |
| Knowledge base | `services/knowledge.py` | None |
| Auth | `services/auth.py` | passlib, python-jose |

`scoring.py`, `vaisala_scoring.py`, `vaisala_treatments.py`, and `vaisala_action_rules.py` have no FastAPI or SQLAlchemy imports — they are separable as standalone libraries.

**Exception:** `routers/assets.py:_score_asset()` is the live production scorer. It is tightly coupled to a SQLAlchemy session. See technical-debt.md.

## Request Flow

```
Browser → FastAPI router → validate (DatasetValidator) → parse (ingestion.py) → DB write
                        → score (_score_asset, on-demand per GET) → JSON response
                        → LLM (llm.py + knowledge.py, on POST /analysis/run)
```

## Authentication

JWT bearer tokens. Authority-scoped: every DB query filters by `current_user.authority_id`.
`User` belongs to `Authority`. All uploaded data and scores are isolated per authority.

## Local Ports

- Frontend: localhost:5173 (Vite dev server)
- Backend: localhost:8001 (NOT 8000 — changed to avoid local port collision)
- Frontend proxies `/api/*` to `http://localhost:8001`

## Deployment

Railway builds from GitHub `main` branch only. Local changes have no effect on production until committed and pushed. Procfile runs `alembic upgrade head` before starting the server. Backend memory limit raised to 8 GB (from Railway 1 GB default) after OOM crash during large Vaisala XLSX upload. API docs (`/docs`) disabled in production (`ENVIRONMENT=production`).

## AI Layer

`services/llm.py` wraps Anthropic SDK. System prompt = role definition + `ALL_KNOWLEDGE` from `services/knowledge.py` (domain knowledge base). Dataset context passed as user message. Prompt caching applied to system prompt and asset context. Multi-turn query via `POST /analysis/query`. Single analysis run persisted as `AnalysisRun` row.
