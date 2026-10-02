"""Lightweight VAD helpers for long-form audio processing.

This project does not require a full diarization pipeline at this stage, but it
benefits from a tiny compatibility layer that can be extended later without
changing the wider consultation flow.
"""
from __future__ import annotations

from typing import List, Tuple


def estimate_speech_windows(duration_seconds: float, sample_rate: int = 16000) -> List[Tuple[float, float]]:
    """Return a simple placeholder segmentation for long recordings.

    The current MVP uses faster-whisper's built-in VAD; this helper keeps the
    API surface explicit and allows a future implementation to swap in a more
    advanced silence detector without changing the rest of the pipeline.
    """
    if duration_seconds <= 0:
        return []

    chunk = 30.0
    windows: List[Tuple[float, float]] = []
    for start in range(0, int(duration_seconds), int(chunk)):
        end = min(duration_seconds, start + chunk)
        windows.append((float(start), float(end)))
    return windows
