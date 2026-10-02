import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import patients, consultations
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(patients.router, prefix="/api", tags=["patients"])
app.include_router(consultations.router, prefix="/api", tags=["consultations"])


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "database_url": settings.database_url,
        "asr": whisper_status(),
        "disclaimer": (
            "ClinOps-AI is an academic prototype and clinical decision-support "
            "demonstration. AI-generated recommendations are not medical advice "
            "and must be independently reviewed and approved by a qualified "
            "doctor before use."
        ),
    }
