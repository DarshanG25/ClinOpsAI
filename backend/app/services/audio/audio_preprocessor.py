"""Streaming FFmpeg preprocessing for consultation audio."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
import time
import wave
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from app.config.settings import settings

logger = logging.getLogger("clinops.audio.preprocessing")

ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mpeg", ".mpg", ".mp2", ".flac", ".ogg"}
_AUDIO_FILTERS = (
    "highpass=f=80,lowpass=f=7600,afftdn=nr=10:nf=-40:tn=1,"
    "loudnorm=I=-16:TP=-1.5:LRA=11"
)


class AudioPreprocessingError(RuntimeError):
    """Raised when audio cannot be safely decoded and normalized."""


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def validate_audio_path(audio_path: str) -> Path:
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    if path.suffix.lower() not in ALLOWED_AUDIO_EXTENSIONS:
        raise ValueError(
            f"Unsupported audio format '{path.suffix.lower()}'. "
            f"Allowed: {sorted(ALLOWED_AUDIO_EXTENSIONS)}"
        )
    if path.stat().st_size == 0:
        raise ValueError("Uploaded audio file is empty")
    return path


def _probe_audio(source: Path) -> dict:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise AudioPreprocessingError(
            "ffprobe was not found. Install FFmpeg including ffprobe and add both to PATH."
        )
    try:
        result = subprocess.run(
            [
                ffprobe, "-v", "error", "-select_streams", "a:0",
                "-show_entries", "stream=codec_name,sample_rate,channels,sample_fmt",
                "-show_entries", "format=format_name,duration", "-of", "json", str(source),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        metadata = json.loads(result.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        raise AudioPreprocessingError(f"Could not inspect audio file '{source.name}': {detail.strip()}") from exc

    streams = metadata.get("streams") or []
    if not streams:
        raise AudioPreprocessingError(f"Audio file '{source.name}' has no decodable audio stream.")
    return {"format": (metadata.get("format") or {}).get("format_name", source.suffix),
            "duration": (metadata.get("format") or {}).get("duration", "unknown"),
            **streams[0]}


def normalize_audio_to_wav(audio_path: str, output_path: str) -> str:
    """Decode to mono 16 kHz PCM16 using FFmpeg without loading audio into Python."""
    source = validate_audio_path(audio_path)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioPreprocessingError(
            "FFmpeg was not found. Install FFmpeg and add it to PATH before processing audio."
        )

    metadata = _probe_audio(source)
    logger.info(
        "Audio preprocessing started: format=%s duration=%ss sample_rate=%s "
        "channels=%s codec=%s",
        metadata["format"], metadata["duration"], metadata.get("sample_rate", "unknown"),
        metadata.get("channels", "unknown"), metadata.get("codec_name", "unknown"),
    )
    started_at = time.monotonic()
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000",
        "-af", _AUDIO_FILTERS, "-c:a", "pcm_s16le", "-f", "wav", str(target),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        raise AudioPreprocessingError(
            f"FFmpeg could not preprocess audio '{source.name}': {detail.strip()}"
        ) from exc

    try:
        with wave.open(str(target), "rb") as processed:
            sample_rate = processed.getframerate()
            channels = processed.getnchannels()
            sample_width = processed.getsampwidth()
            frames = processed.getnframes()
    except (OSError, wave.Error) as exc:
        raise AudioPreprocessingError(f"FFmpeg output is not a valid WAV file: {exc}") from exc

    if sample_rate != 16000 or channels != 1 or sample_width != 2 or frames <= 0:
        raise AudioPreprocessingError(
            "FFmpeg produced an invalid WAV "
            f"(sample_rate={sample_rate}, channels={channels}, sample_width={sample_width}, frames={frames})."
        )

    logger.info(
        "Audio preprocessing completed: output=%s format=wav codec=pcm_s16le "
        "sample_rate=%s channels=%s duration=%.3fs elapsed=%.2fs "
        "noise_filter=afftdn+highpass+lowpass loudness=normalized "
        "silence=preserved vad=not_applied_during_preprocessing",
        target, sample_rate, channels, frames / sample_rate, time.monotonic() - started_at,
    )
    return str(target)


@contextmanager
def temporary_preprocessed_audio(audio_path: str) -> Iterator[str]:
    """Yield one normalized audio path and remove it after all consumers finish."""
    with tempfile.TemporaryDirectory(prefix="clinops-audio-") as temp_dir:
        output_path = str(Path(temp_dir) / "processed.wav")
        yield normalize_audio_to_wav(audio_path, output_path)


def preprocess_audio_for_asr(audio_path: str, output_dir: Optional[str] = None) -> str:
    """Return a normalized WAV at a caller-managed persistent path.

    The consultation route uses ``temporary_preprocessed_audio`` so ASR and
    diarization share one conversion and automatic cleanup.
    """
    source = validate_audio_path(audio_path)
    out_dir = Path(output_dir) if output_dir else Path(settings.upload_dir) / "processed"
    return normalize_audio_to_wav(str(source), str(out_dir / f"{source.stem}_asr.wav"))