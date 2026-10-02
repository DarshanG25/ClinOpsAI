"""Audio preprocessing for long-form consultation recordings.

The goal is to keep the original uploaded file intact while producing an ASR-
ready copy with a predictable format: WAV, mono, 16 kHz, and optional volume
normalization. This keeps the pipeline compatible with long recordings without
forcing an immediate full diarization stack.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from app.config.settings import settings

ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mpeg", ".mpg", ".mp2", ".flac", ".ogg"}


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def validate_audio_path(audio_path: str) -> Path:
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    if path.suffix.lower() not in ALLOWED_AUDIO_EXTENSIONS:
        raise ValueError(f"Unsupported audio format '{path.suffix.lower()}'. Allowed: {sorted(ALLOWED_AUDIO_EXTENSIONS)}")
    if path.stat().st_size == 0:
        raise ValueError("Uploaded audio file is empty")
    return path


def preprocess_audio_for_asr(audio_path: str, output_dir: Optional[str] = None) -> str:
    """Return a path to an ASR-friendly copy of the audio.

    If FFmpeg is installed, convert to WAV PCM 16kHz mono and normalize volume.
    Otherwise, return the original file path so the caller can still gracefully
    fall back to demo mode or a non-FFmpeg path.
    """
    source = validate_audio_path(audio_path)
    if not ffmpeg_available():
        return str(source)

    if output_dir is None:
        output_dir = str(Path(settings.upload_dir) / "processed")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    target = out_dir / f"{source.stem}_asr.wav"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=11",
        str(target),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except (subprocess.CalledProcessError, OSError) as exc:
        raise RuntimeError(f"FFmpeg preprocessing failed for '{audio_path}': {exc}") from exc

    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError(f"Preprocessed audio was not created for '{audio_path}'")

    return str(target)
