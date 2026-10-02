"""Central application configuration.

All values can be overridden with environment variables or a `.env` file
(see `.env.example` at the repository root). Nothing here is a secret.
"""
from pathlib import Path
from pydantic_settings import BaseSettings

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "ClinOps-AI"
    environment: str = "development"

    # Database
    database_url: str = f"sqlite:///{(BACKEND_ROOT / 'clinops_ai.db').as_posix()}"

    # ASR
    asr_mode: str = "auto"  # auto | whisper | demo
    whisper_model: str = "small"
    device: str = "auto"  # auto | cpu | cuda
    model_cache_dir: str = str(BACKEND_ROOT / "model_cache")
    diarization_enabled: bool = True
    diarization_model: str = "pyannote/speaker-diarization-community-1"
    hf_token: str | None = None

    # Storage
    upload_dir: str = str(BACKEND_ROOT / "uploads" / "audio")
    pdf_output_dir: str = str(BACKEND_ROOT / "outputs" / "pdfs")
    max_audio_size: int = 26_214_400  # 25 MB

    # Data (medicines.json, demo/sample transcripts). Defaults to
    # <repo-root>/data for local runs; override with DATA_DIR in Docker
    # where the layout differs (see backend/Dockerfile).
    data_dir: str = str(BACKEND_ROOT.parent / "data")

    # Language
    default_language: str = "en"
    supported_languages: list[str] = ["en", "hi", "mr"]

    # Legacy keys kept so an old .env doesn't crash pydantic-settings
    mongodb_uri: str | None = None
    mongodb_db: str | None = None
    embedding_model: str | None = None
    pdf_output_dir_legacy: str | None = None

    class Config:
        env_file = (BACKEND_ROOT.parent / ".env", BACKEND_ROOT / ".env")
        case_sensitive = False
        extra = "ignore"
        protected_namespaces = ("settings_",)


settings = Settings()

# Ensure runtime directories exist.
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
Path(settings.pdf_output_dir).mkdir(parents=True, exist_ok=True)
Path(settings.model_cache_dir).mkdir(parents=True, exist_ok=True)
