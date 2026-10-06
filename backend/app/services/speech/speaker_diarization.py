"""Optional pyannote speaker diarization and conservative role inference."""
from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Any

from app.config.settings import settings
from app.services.audio.audio_preprocessor import ffmpeg_available, normalize_audio_to_wav

logger = logging.getLogger("clinops.diarization")

_pipeline = None
_pipeline_load_failed_reason: str | None = None

_ROLE_DOCTOR = "Doctor"
_ROLE_PATIENT = "Patient"
_ROLE_ATTENDANT = "Patient's Attendant/Relative"
_ROLE_UNKNOWN = "Other/Unknown"


def _load_pipeline():
    global _pipeline, _pipeline_load_failed_reason
    if _pipeline is not None:
        return _pipeline
    if _pipeline_load_failed_reason:
        return None
    if not settings.diarization_enabled:
        _pipeline_load_failed_reason = "Speaker diarization is disabled by configuration."
        return None

    token = settings.hf_token
    if not token:
        try:
            from huggingface_hub import get_token

            token = get_token()
        except Exception:  # noqa: BLE001
            token = None
    if not token:
        _pipeline_load_failed_reason = (
            "Set HF_TOKEN to a Hugging Face token after accepting the model conditions "
            "for pyannote/speaker-diarization-community-1."
        )
        return None

    try:
        from pyannote.audio import Pipeline

        _pipeline = Pipeline.from_pretrained(settings.diarization_model, token=token)
        if settings.device == "cuda":
            import torch

            _pipeline.to(torch.device("cuda"))
        return _pipeline
    except Exception as exc:  # noqa: BLE001
        _pipeline_load_failed_reason = f"Could not load pyannote diarization model: {exc}"
        logger.warning(_pipeline_load_failed_reason)
        return None


def _tracks_from_annotation(annotation: Any) -> list[dict[str, Any]]:
    annotation = getattr(annotation, "speaker_diarization", annotation)
    tracks = []
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        tracks.append({
            "start": float(turn.start),
            "end": float(turn.end),
            "speaker_id": str(speaker),
        })
    return tracks


def _normalize_audio_for_diarization(audio_path: str, normalized_path: str) -> None:
    """Use the shared audio-normalization implementation for standalone calls."""
    normalize_audio_to_wav(audio_path, normalized_path)


def infer_speaker_roles(segments: list[dict[str, Any]]) -> dict[str, str]:
    """Assign a role only when the speaker's accumulated language is clear."""
    speaker_text: dict[str, list[str]] = {}
    for segment in segments:
        speaker_id = segment.get("speaker_id")
        if speaker_id:
            speaker_text.setdefault(speaker_id, []).append(segment.get("text", ""))

    roles: dict[str, str] = {}
    kinship = re.compile(
        r"\bmy\s+(?:mother|father|mom|mum|dad|son|daughter|wife|husband|"
        r"brother|sister|child|children|parent|grandmother|grandfather)\b"
    )
    clinical_question = re.compile(
        r"\b(?:any|what|when|where|how|do you|have you|are you|is there|"
        r"tell me about|how long|what kind)\b.{0,70}\b(?:pain|symptom|fever|"
        r"medicine|medication|allerg|history|feel|start|taking|happen)\b|"
        r"\b(?:pain|symptom|fever|medicine|medication|allerg|history|feel|"
        r"start|taking|happen)\b.{0,70}\?",
        re.IGNORECASE,
    )
    advice = re.compile(
        r"\b(?:take|stop taking|avoid|drink|apply|continue|increase|reduce|"
        r"prescribe|follow up|come back|rest|monitor|check your)\b",
        re.IGNORECASE,
    )
    first_person_condition = re.compile(
        r"\b(?:i have|i've had|i feel|i am having|my (?:pain|stomach|head|"
        r"throat|chest|symptoms)|i suffer from|i take)\b",
        re.IGNORECASE,
    )

    for speaker_id, utterances in speaker_text.items():
        text = " ".join(utterances)
        if kinship.search(text):
            roles[speaker_id] = _ROLE_ATTENDANT
            continue
        doctor_signals = int(bool(clinical_question.search(text))) + int(bool(advice.search(text)))
        patient_signal = bool(first_person_condition.search(text))
        third_person_report = bool(re.search(
            r"\b(?:he|she|my (?:son|daughter|mother|father|wife|husband))\s+"
            r"(?:has|had|is|was|feels|takes)\b",
            text,
            re.IGNORECASE,
        ))
        if doctor_signals == 2 and not patient_signal:
            roles[speaker_id] = _ROLE_DOCTOR
        elif patient_signal and not doctor_signals and not third_person_report:
            roles[speaker_id] = _ROLE_PATIENT
        elif third_person_report and not doctor_signals:
            roles[speaker_id] = _ROLE_ATTENDANT
        else:
            roles[speaker_id] = _ROLE_UNKNOWN
    return roles


def assign_speakers_to_words(
    word_segments: list[dict[str, Any]], tracks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group timestamped Whisper words by diarized speaker turn."""
    assigned = []
    for word in sorted(word_segments, key=lambda item: (item["start"], item["end"])):
        midpoint = (float(word["start"]) + float(word["end"])) / 2
        track = next((
            item for item in tracks
            if float(item["start"]) <= midpoint < float(item["end"])
        ), None)
        speaker_id = track["speaker_id"] if track else None
        if assigned and assigned[-1]["speaker_id"] == speaker_id and (
            float(word["start"]) - assigned[-1]["end"] <= 1.5
        ):
            assigned[-1]["end"] = float(word["end"])
            assigned[-1]["text"] += f" {word['text']}"
            if word.get("confidence") is not None:
                assigned[-1]["confidences"].append(word["confidence"])
        else:
            assigned.append({
                "start": float(word["start"]),
                "end": float(word["end"]),
                "text": word["text"],
                "speaker_id": speaker_id,
                "confidences": [word["confidence"]] if word.get("confidence") is not None else [],
            })
    for segment in assigned:
        segment["start"] = round(segment["start"], 2)
        segment["end"] = round(segment["end"], 2)
        confidences = segment.pop("confidences")
        segment["confidence"] = sum(confidences) / len(confidences) if confidences else None
    return assigned


def diarize_transcription(
    audio_path: str,
    word_segments: list[dict[str, Any]],
    fallback_segments: list[dict[str, Any]],
    *,
    is_demo: bool = False,
    audio_is_preprocessed: bool = False,
) -> tuple[list[dict[str, Any]], str]:
    """Return speaker-attributed segments; never invent labels on failure."""
    if is_demo:
        return _mark_unavailable(fallback_segments, "demo_audio")
    pipeline = _load_pipeline()
    if pipeline is None:
        status = "unavailable: " + (_pipeline_load_failed_reason or "Diarization model unavailable.")
        return _mark_unavailable(fallback_segments, status)
    if not audio_is_preprocessed and not ffmpeg_available():
        return _mark_unavailable(
            fallback_segments,
            "unavailable: FFmpeg was not found. Install FFmpeg and add it to PATH.",
        )
    try:
        if audio_is_preprocessed:
            logger.info("Diarization started: normalized=%s", audio_path)
            try:
                annotation = pipeline(str(Path(audio_path)))
            finally:
                logger.info("Diarization ended: normalized=%s", audio_path)
        else:
            with tempfile.TemporaryDirectory(prefix="clinops-diarization-") as temp_dir:
                normalized_path = str(Path(temp_dir) / "diarization.wav")
                _normalize_audio_for_diarization(audio_path, normalized_path)
                logger.info("Diarization started: source=%s normalized=%s", audio_path, normalized_path)
                try:
                    annotation = pipeline(normalized_path)
                finally:
                    logger.info("Diarization ended: source=%s normalized=%s", audio_path, normalized_path)
        tracks = _tracks_from_annotation(annotation)
        if not tracks:
            return _mark_unavailable(fallback_segments, "no_speech_tracks")
        if not word_segments:
            return _mark_unavailable(fallback_segments, "word_timestamps_unavailable")
        segments = assign_speakers_to_words(word_segments, tracks)
        roles = infer_speaker_roles(segments)
        for segment in segments:
            segment["speaker_role"] = roles.get(segment["speaker_id"], _ROLE_UNKNOWN)
        return segments, "complete"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Speaker diarization failed for %s", audio_path)
        return _mark_unavailable(fallback_segments, f"error: {exc}")


def _mark_unavailable(
    segments: list[dict[str, Any]], status: str,
) -> tuple[list[dict[str, Any]], str]:
    unchanged = []
    for segment in segments:
        unchanged.append({
            **segment,
            "speaker_id": None,
            "speaker_role": None,
            "diarization_status": status,
        })
    return unchanged, status


def apply_speaker_roles(
    segments: list[dict[str, Any]], roles: dict[str, str],
) -> list[dict[str, Any]]:
    valid_roles = {_ROLE_DOCTOR, _ROLE_PATIENT, _ROLE_ATTENDANT, _ROLE_UNKNOWN}
    invalid = {role for role in roles.values() if role not in valid_roles}
    if invalid:
        raise ValueError(f"Unsupported speaker role(s): {', '.join(sorted(invalid))}")
    speaker_ids = {segment.get("speaker_id") for segment in segments if segment.get("speaker_id")}
    missing = set(roles) - speaker_ids
    if missing:
        raise ValueError(f"Speaker ID(s) not found in transcript: {', '.join(sorted(missing))}")
    return [
        {**segment, "speaker_role": roles.get(segment.get("speaker_id"), segment.get("speaker_role"))}
        for segment in segments
    ]