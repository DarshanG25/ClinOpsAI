from types import SimpleNamespace
from pathlib import Path

import pytest

from app.services.speech import speaker_diarization as diarization


class FakeAnnotation:
    def itertracks(self, yield_label=False):
        assert yield_label
        yield SimpleNamespace(start=0.0, end=2.0), 0, "SPEAKER_00"
        yield SimpleNamespace(start=2.0, end=4.0), 0, "SPEAKER_01"
        yield SimpleNamespace(start=4.0, end=6.0), 0, "SPEAKER_02"


class FakePipeline:
    def __call__(self, audio_path):
        normalized_path = Path(audio_path)
        assert normalized_path.name == "diarization.wav"
        assert normalized_path.exists()
        self.received_path = normalized_path
        return FakeAnnotation()


def test_diarization_uses_temporary_normalized_file_and_keeps_roles(monkeypatch, tmp_path):
    pipeline = FakePipeline()
    monkeypatch.setattr(diarization, "_load_pipeline", lambda: pipeline)
    monkeypatch.setattr(diarization, "ffmpeg_available", lambda: True)
    monkeypatch.setattr(
        diarization,
        "_normalize_audio_for_diarization",
        lambda source, target: Path(target).write_bytes(b"normalized wav"),
    )
    original_audio = tmp_path / "consultation.mp3"
    original_audio.write_bytes(b"original upload")
    words = [
        {"start": 0.1, "end": 0.5, "text": "Any", "confidence": 0.9},
        {"start": 0.5, "end": 1.0, "text": "symptoms?", "confidence": 0.9},
        {"start": 2.1, "end": 2.5, "text": "I", "confidence": 0.9},
        {"start": 2.5, "end": 3.0, "text": "have fever.", "confidence": 0.9},
        {"start": 4.1, "end": 4.6, "text": "He", "confidence": 0.9},
        {"start": 4.6, "end": 5.0, "text": "had vomiting.", "confidence": 0.9},
    ]
    fallback = [{"start": 0.0, "end": 6.0, "text": "Complete original transcript."}]

    segments, status = diarization.diarize_transcription(
        str(original_audio), words, fallback,
    )

    assert status == "complete"
    assert not pipeline.received_path.exists()
    assert original_audio.read_bytes() == b"original upload"
    assert [segment["speaker_id"] for segment in segments] == [
        "SPEAKER_00", "SPEAKER_01", "SPEAKER_02",
    ]
    assert [segment["speaker_role"] for segment in segments] == [
        "Other/Unknown", "Patient", "Patient's Attendant/Relative",
    ]
    assert segments[0]["start"] == 0.1
    assert segments[-1]["end"] == 5.0
    assert "Complete original transcript." in fallback[0]["text"]


def test_normalization_failure_is_reported_without_fabricated_speakers(monkeypatch, tmp_path):
    monkeypatch.setattr(diarization, "_load_pipeline", lambda: FakePipeline())
    monkeypatch.setattr(diarization, "ffmpeg_available", lambda: True)

    def fail_normalization(source, target):
        raise RuntimeError("FFmpeg could not normalize uploaded audio: bad input")

    monkeypatch.setattr(diarization, "_normalize_audio_for_diarization", fail_normalization)
    fallback = [{"start": 0.0, "end": 1.0, "text": "Original transcript."}]

    segments, status = diarization.diarize_transcription(
        str(tmp_path / "consultation.mp3"), [], fallback,
    )

    assert "FFmpeg could not normalize uploaded audio" in status
    assert segments[0]["speaker_id"] is None
    assert segments[0]["speaker_role"] is None
    assert segments[0]["text"] == "Original transcript."


def test_diarization_accepts_shared_preprocessed_wav(monkeypatch, tmp_path):
    pipeline = FakePipeline()
    audio_path = tmp_path / "diarization.wav"
    audio_path.write_bytes(b"already normalized")
    monkeypatch.setattr(diarization, "_load_pipeline", lambda: pipeline)
    monkeypatch.setattr(diarization, "ffmpeg_available", lambda: False)
    monkeypatch.setattr(
        diarization,
        "_normalize_audio_for_diarization",
        lambda *_: pytest.fail("shared normalized audio must not be converted again"),
    )

    _, status = diarization.diarize_transcription(
        str(audio_path), [], [{"start": 0.0, "end": 1.0, "text": "Transcript."}],
        audio_is_preprocessed=True,
    )

    assert status == "word_timestamps_unavailable"
    assert pipeline.received_path == audio_path


def test_speaker_role_correction_preserves_internal_ids():
    segments = [
        {"start": 1.0, "end": 2.0, "text": "Question?", "speaker_id": "SPEAKER_07", "speaker_role": "Other/Unknown"},
    ]

    corrected = diarization.apply_speaker_roles(segments, {"SPEAKER_07": "Doctor"})

    assert corrected[0]["speaker_id"] == "SPEAKER_07"
    assert corrected[0]["speaker_role"] == "Doctor"
    assert segments[0]["speaker_role"] == "Other/Unknown"