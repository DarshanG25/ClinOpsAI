import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import patients, consultations, auth
from app.config.settings import settings
from app.db.database import init_db
from app.services.speech.whisper_service import whisper_status

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="ClinOps-AI",
    version="0.2.0",
    description="Multilingual AI-Assisted Prescription & Clinical Recommendation System (academic prototype).",
    lifespan=lifespan,
)


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(
    _request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    logging.getLogger("clinops.database").error(
        "Database operation failed (%s)",
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "A database operation failed."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(patients.router, prefix="/api", tags=["patients"])
app.include_router(consultations.router, prefix="/api", tags=["consultations"])
app.include_router(auth.router, prefix="/api", tags=["authentication"])

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
        "asr": {
            "configured_mode": settings.asr_mode,
            "model_loaded": whisper_status()["model_loaded"],
        },
        "disclaimer": (
            "ClinOps-AI is an academic prototype and clinical decision-support "
            "demonstration. AI-generated recommendations are not medical advice "
            "and must be independently reviewed and approved by a qualified "
            "doctor before use."
        ),
    }
