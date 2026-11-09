
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from .common.config.env import load_backend_env
except ImportError:
    from common.config.env import load_backend_env


# Load environment variables before importing application routes.
load_backend_env()

try:
    from .common.config.env import FRONTEND_ORIGINS
except ImportError:
    from common.config.env import FRONTEND_ORIGINS

try:
    from .pii_route import router as pii_router
except ImportError:
    from pii_route import router as pii_router


app = FastAPI(
    title="Conseal - Trust & Explainability",
    description=(
        "Privacy-first document anonymization "
        "with explainable PII redaction."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=[
        "Content-Type",
        "Authorization",
    ],
)

app.include_router(
    pii_router,
    prefix="/pii",
    tags=["PII Anonymization"],
)


@app.get("/")
async def root():
    return {
        "application": "Conseal",
        "version": "2.0.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Conseal API",
    }
