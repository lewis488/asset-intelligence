# Asset Intelligence — Highway Network Management Platform

AI-powered highway asset prioritisation platform for local highway authorities. Combines SCANNER condition survey data, CVI assessments, and reactive maintenance records into a composite risk model with Claude-powered analysis briefings.

---

## Architecture

```
/backend   FastAPI + SQLAlchemy — scoring engine, ingestion, LLM layer
/frontend  React + Vite — dashboard, upload, analysis, query pages
```

**Separation of concerns:**
- `services/scoring.py` — risk scoring engine, isolated from ingestion and LLM. Tune weights in `.env`.
- `services/knowledge.py` — structured domain knowledge base. Injected into every LLM call.
- `services/ingestion.py` — CSV/Excel parsing with flexible column alias mapping.
- `services/llm.py` — Anthropic SDK wrapper. Knowledge is a cached system prompt; dataset is user message.

---

## Setup

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Environment

```bash
# from asset-intelligence/ root
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY, DATABASE_URL, JWT_SECRET
```

### 3. Database

```bash
cd backend
alembic upgrade head
```

### 4. Start API

```bash
# from asset-intelligence/ root
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/api/docs

### 5. Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

---

## SCANNER Data Format

The SCANNER Excel upload handles WSCC's HMDIF-derived multi-row header format:

```
Row 0 (merged):   SECTION INFORMATION | DEFECT LENGTHS | AMBER LENGTHS ONLY | RED LENGTHS ONLY | CI DISTRIBUTION
Row 1:            (descriptions)
Row 2:            NSG | ROAD_NAME | PARISH | LENGTH | OVERALL | RUTTING | CRACKING | TEXTURE_DEPTH | LPV | ...
Row 3:            (network summary row — auto-skipped)
Row 4+:           per-section data
```

**Sheet names must contain:** `A ROAD` (→ road_class=A) or both `B` and `C` (→ road_class=BC).

**B+C roads** have an additional `EDI AVERAGE` column not present on A roads — detected automatically.

**CI Distribution section** (last 5 columns): proportional contributions to the CI from each parameter. These sum to approximately 1.0 and drive the defect driver scoring.

---

## Scoring Model

### SCANNER Pathway (classified A, B, C roads)

| Component | Max Points | Description |
|-----------|-----------|-------------|
| CI Score | 40 | Scaled by RCI band (Green 0–10, Amber 10–25, Red 25–40) |
| Defect Driver Score | 30 | CI contribution analysis + red/amber band penetration bonus |
| EDI Score | 15 | Edge deterioration index (B+C only) |
| Reactive Score | 15 | Job frequency × recency weighting |
| **Total** | **100** | |

**Defect driver score logic (key differentiator):**
- LPV dominant (>40% CI) → +15 pts — *structural roughness, most serious, inlay/reconstruction*
- Rutting dominant (>35% CI) → +15 pts — *structural deformation, inlay/reconstruction*
- Cracking dominant (>40% CI) → +12 pts — *surface/structural, investigate*
- Texture dominant (>50% CI) → +8 pts — *surface treatment usually sufficient*
- High red% (>15%) → +10 pts bonus
- High amber% (>40%) → +5 pts bonus

### CVI Pathway (unclassified roads)

| Condition | Points |
|-----------|--------|
| Structural CI ≥ 85 | 40 |
| Structural CI 70–84 | 25 |
| Edge CI ≥ 50 | 20 |
| Edge CI 35–49 | 10 |
| Wearing Course CI ≥ 60 | 15 |
| Wearing Course CI 45–59 | 8 |
| Reactive score | 0–15 |

### Risk Bands

| Band | Score | Action |
|------|-------|--------|
| Critical | ≥ 65 | Capital programme — immediate action |
| High | 40–64 | Plan treatment within 1–2 years |
| Medium | 20–39 | Monitor, programme surface treatment |
| Low | < 20 | Routine monitoring |

---

## Tuning the Scoring Model

All weights are environment variables — no code changes needed:

```bash
# Increase structural defect driver weight (e.g., after field validation shows LPV more serious)
DD_LPV_POINTS=18.0

# Make EDI more influential on B+C roads
EDI_HIGH_POINTS=20.0

# Adjust risk band thresholds
RISK_CRITICAL=70.0

# Bump version to track model evolution
SCORING_VERSION=1.1.0
```

After changing weights, run a new analysis (`POST /analysis/run`) to recompute and persist scores with the new version.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register authority + user |
| POST | `/auth/login` | Obtain JWT |
| POST | `/assets/upload/scanner` | Upload SCANNER Excel |
| POST | `/assets/upload/cvi` | Upload CVI CSV |
| POST | `/assets/upload/reactive` | Upload reactive jobs CSV |
| GET  | `/assets/` | Paginated scored asset list (filter: risk_band, road_class, parish) |
| GET  | `/assets/export` | Download full priority list as CSV |
| GET  | `/assets/schema/aliases` | Column alias reference |
| POST | `/analysis/run` | Trigger AI analysis + persist risk scores |
| GET  | `/analysis/latest` | Latest analysis briefing |
| POST | `/analysis/query` | Multi-turn LLM query |
| GET  | `/analysis/stats` | KPI stats (no LLM call) |

---

## Production Deployment

```bash
# Build frontend
cd frontend && npm run build

# Run backend
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

- Set `ENVIRONMENT=production` to disable API docs
- Run behind nginx, serving the built frontend on the same origin
- Store `ANTHROPIC_API_KEY` and `JWT_SECRET` in a secrets manager
- Use PgBouncer connection pooler in front of PostgreSQL
