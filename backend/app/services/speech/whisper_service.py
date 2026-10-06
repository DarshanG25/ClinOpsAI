"""Speech-to-text service.

Uses faster-whisper when a model can actually be loaded. Demo transcripts are
available only when explicitly requested with `ASR_MODE=demo`; real uploads
must never silently receive the same synthetic clinical content.

Configuration (see app/config/settings.py / .env.example):
    ASR_MODE=auto    use Whisper, raising a clear error if it is unavailable
  ASR_MODE=whisper force real Whisper; raises a clear error if it can't load
  ASR_MODE=demo    always use the demo transcript (useful offline / in CI)
"""
import logging
from pathlib import Path
from typing import Optional

from app.config.settings import settings
from app.services.audio.audio_preprocessor import preprocess_audio_for_asr

logger = logging.getLogger("clinops.speech")

_model = None
_model_load_failed_reason: Optional[str] = None

DEMO_TRANSCRIPTS = {
    "en": (
        "Doctor: What's the problem today? Patient: I have had fever and headache "
        "since yesterday, and a mild dry cough. Doctor: Any body ache? Patient: Yes, "
        "mild body ache too. Doctor: This looks like a viral fever. Take Paracetamol "
        "500 mg twice daily for 3 days, and a cough syrup at night. Drink plenty of "
        "fluids and rest."
    ),
    "hi": (
        "Doctor: Kya taklif hai aapko? Patient: Mujhe do din se bukhar aur sar dard "
        "hai, aur gale mein kharash bhi hai. Doctor: Yeh gale ka infection lag raha "
        "hai. Paracetamol 500 mg din mein do baar, teen din tak lijiye. Aur "
        "Amoxicillin 500 mg din mein teen baar, paanch din tak. Garam paani se "
        "gargle kariye."
    ),
    "mr": (
        "Doctor: Kay tras hoto ahe? Patient: Mala tin divsapasun taap ani angadukhi "
        "ahe, ani pot dukhtay thoda. Doctor: He acidity mule hou shakte. "
        "Pantoprazole 40 mg roj sakali ekda, saat divas ghya. Tikhat khane taalaa."
    ),
}


def _resolve_device() -> str:
    if settings.device != "auto":
        return settings.device
    try:
        import torch  # faster-whisper's ctranslate2 backend doesn't need torch,
        # but if torch happens to be installed we can use it to probe CUDA.
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _load_whisper_model():
    """Lazily load (and cache) a faster-whisper model.

    Loading failures are recorded so the request can report that real ASR is
    unavailable instead of returning a misleading fixed transcript.
    """
    global _model, _model_load_failed_reason
    if _model is not None:
        return _model
    if _model_load_failed_reason is not None:
        return None
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        _model_load_failed_reason = f"faster-whisper not installed ({exc})"
        logger.warning(_model_load_failed_reason)
        return None

    device = _resolve_device()
    compute_type = "float16" if device == "cuda" else "int8"
    try:
        _model = WhisperModel(
            settings.whisper_model,
            device=device,
            compute_type=compute_type,
            download_root=settings.model_cache_dir,
        )
        logger.info("Loaded faster-whisper model '%s' on %s", settings.whisper_model, device)
        return _model
    except Exception as exc:  # noqa: BLE001 - report unavailable real ASR
        _model_load_failed_reason = (
            f"Could not load Whisper model '{settings.whisper_model}' ({exc.__class__.__name__}: {exc}). "
            "This usually means the model weights aren't cached and can't be downloaded "
            "in this environment. Real ASR will report an error instead of fabricating a transcript."
        )
        logger.warning(_model_load_failed_reason)
        return None


def _segment_to_dict(segment, language: str) -> dict:
    text = (getattr(segment, "text", "") or "").strip()
    return {
        "start": round(float(getattr(segment, "start", 0.0) or 0.0), 2),
        "end": round(float(getattr(segment, "end", 0.0) or 0.0), 2),
        "text": text,
        "language": language,
        "confidence": getattr(segment, "avg_logprob", None),
    }


def transcribe_audio(
    audio_path: str,
    language_hint: Optional[str] = None,
    *,
    audio_is_preprocessed: bool = False,
) -> dict:
    """Returns {language, transcript, segments, asr_mode}.

    asr_mode is always one of "whisper" or "demo" so callers/UI can display
    it plainly — the app never claims a demo transcript is a real one.
    """
    mode = settings.asr_mode.lower()
    source_path = audio_path
    if not audio_is_preprocessed:
        try:
            source_path = preprocess_audio_for_asr(audio_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Preprocessing failed for %s (%s); continuing with original file.", audio_path, exc)

    if mode in ("auto", "whisper"):
        model = _load_whisper_model()
        if model is not None:
            try:
                supported_lang = language_hint if language_hint in settings.supported_languages else None
                logger.info("Whisper VAD enabled; silence remains on the original timeline")
                segments_iter, info = model.transcribe(
                    source_path,
                    language=supported_lang,
                    vad_filter=True,
                    word_timestamps=True,
                    beam_size=5,
                )
                segments = []
                word_segments = []
                text_parts = []
                language = info.language or language_hint or settings.default_language
                for seg in segments_iter:
                    segment = _segment_to_dict(seg, language)
                    segments.append(segment)
                    if segment["text"]:
                        text_parts.append(segment["text"])
                    for word in getattr(seg, "words", None) or []:
                        word_text = (getattr(word, "word", "") or "").strip()
                        if word_text:
                            word_segments.append({
                                "start": round(float(getattr(word, "start", seg.start) or 0.0), 2),
                                "end": round(float(getattr(word, "end", seg.end) or 0.0), 2),
                                "text": word_text,
                                "confidence": getattr(word, "probability", None),
                            })
                transcript = " ".join(text_parts).strip()
                if transcript:
                    return {
                        "language": language,
                        "transcript": transcript,
                        "segments": segments,
                        "word_segments": word_segments,
                        "asr_mode": "whisper",
                    }
                logger.warning("Whisper produced an empty transcript for %s.", audio_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Whisper inference failed (%s).", exc)
        if model is None:
            raise RuntimeError(
                "Real speech recognition is unavailable. Install/configure faster-whisper "
                "and ensure the model weights are available, or set ASR_MODE=demo only for "
                f"synthetic test data. {_model_load_failed_reason}"
            )

    elif mode != "demo":
        raise ValueError(f"Unsupported ASR_MODE '{settings.asr_mode}'. Use auto, whisper, or demo.")

    if mode != "demo":
        raise RuntimeError("Real speech recognition produced no transcript for this audio file.")

    # --- Explicit offline demo mode (labelled so it cannot be mistaken for ASR) ---
    lang = language_hint if language_hint in DEMO_TRANSCRIPTS else settings.default_language
    lang = lang if lang in DEMO_TRANSCRIPTS else "en"
    demo_text = f"[DEMO TRANSCRIPT — no audio model output] {DEMO_TRANSCRIPTS[lang]}"
    return {
        "language": lang,
        "transcript": demo_text,
        "segments": [{
            "start": 0.0,
            "end": 0.0,
            "text": demo_text,
            "language": lang,
            "confidence": None,
        }],
        "word_segments": [],
        "asr_mode": "demo",
    }


def whisper_status() -> dict:
    """Small diagnostics helper (used by /health and tests)."""
    return {
        "configured_mode": settings.asr_mode,
        "model_name": settings.whisper_model,
        "model_loaded": _model is not None,
        "load_failure_reason": _model_load_failed_reason,
    }
