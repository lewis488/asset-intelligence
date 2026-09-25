# Dependencies

## Runtime Dependencies (backend)

Source: `backend/requirements.txt` (referenced but not read in this session — versions below from `.venv` dist-info where observable).

| Package | Purpose |
|---------|---------|
| fastapi | Web framework, routing, dependency injection |
| uvicorn | ASGI server |
| sqlalchemy | ORM, query builder |
| alembic | Database migrations |
| psycopg2 / asyncpg | PostgreSQL driver |
| pydantic / pydantic-settings | Config validation, request/response schemas |
| anthropic | Claude API SDK |
| pandas | Data parsing, aggregation, column mapping |
| openpyxl | Excel file reading (SCANNER HMDIF, Vaisala XLSX) |
| python-calamine | Alternative Excel engine used as primary for Vaisala XLSX (`pd.read_excel(..., engine="calamine")`) |
| geopandas | Shapefile / GeoPackage reading, CRS reprojection |
| shapely | Geometry operations (unary_union, WKT serialisation) |
| numpy | Vectorised scoring in vaisala_scoring.py |
| passlib | Password hashing (bcrypt) |
| python-jose | JWT creation and validation |
| python-multipart | File upload parsing |

## Key Dependency Notes

### geopandas
Required for `parse_network_file()` and `parse_shp_export()`. Not imported at module level — imported inside functions to avoid startup crash when not installed. Failure to import geopandas blocks network SHP and Vaisala SHP ingest.

### python-calamine
Used as preferred Excel engine for Vaisala XLSX (`vaisala_scoring.py:658`):
```python
df = pd.read_excel(io.BytesIO(file_bytes), header=0, engine="calamine")
```
Falls back to default openpyxl if calamine unavailable. Calamine is faster and lower-memory for large Excel files.

### anthropic
`services/llm.py` uses `anthropic.Anthropic` (sync client). Client is a module-level singleton initialised on first call (`_get_client()`). Prompt caching uses `cache_control: {"type": "ephemeral"}` on system prompt blocks.

### numpy
Used only in `vaisala_scoring.py` for matrix multiply scoring (`defect_matrix @ weight_vec`, line 284). Not used in `scoring.py` or `ingestion.py`.

## Frontend Dependencies

| Package | Purpose |
|---------|---------|
| React 18 | UI framework |
| Vite | Build tool, dev server, API proxy |
| Leaflet / react-leaflet | Map rendering (MapTab) |
| axios | HTTP client for API calls |
| recharts | Charts (correlation analysis, CI distribution) |

Frontend proxies `/api/*` to `http://localhost:8001` in development. In production, Vite build is served as static files from Railway.

## Python Version

Pinned to Python 3.11 via `backend/.python-version`. Required for Railway deployment. Earlier versions may lack `tomllib` (stdlib) and some type annotation syntax used in the codebase.

## Railway Infrastructure

- PostgreSQL: provided as Railway managed service
- No Redis, no message queue, no background task runner (all processing is synchronous within request handlers, off-loaded to thread executor for CPU-bound parse)
