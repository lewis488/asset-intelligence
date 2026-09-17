import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.routers import auth as auth_router, assets, analysis, vaisala as vaisala_router

logging.basicConfig(
    level=logging.INFO if settings.environment != "production" else logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

app = FastAPI(
    title="Highway Asset Intelligence Platform",
    version="1.0.0",
    docs_url="/api/docs" if settings.environment != "production" else None,
    redoc_url="/api/redoc" if settings.environment != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB


@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if request.method == "POST" and content_length and int(content_length) > _MAX_UPLOAD_BYTES:
        return JSONResponse(
            {"detail": "File too large. Maximum upload size is 500 MB."},
            status_code=413,
        )
    return await call_next(request)


app.include_router(auth_router.router)
app.include_router(assets.router)
app.include_router(analysis.router)
app.include_router(vaisala_router.router)


@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok", "environment": settings.environment, "scoring_version": settings.scoring_version}
