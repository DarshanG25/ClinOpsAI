import hashlib
import shutil
import subprocess
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.audio import audio_preprocessor as preprocessing


@pytest.fixture
def stereo_mp3(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and ffprobe are required for audio conversion tests")
    source = tmp_path / "stereo.mp3"
    subprocess.run(
        [
            ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5",
            "-ac", "2", "-ar", "44100", "-c:a", "libmp3lame", str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return source


def test_mp3_stereo_resamples_to_mono_16khz_pcm16_and_preserves_original(stereo_mp3, tmp_path):
    original_digest = hashlib.sha256(stereo_mp3.read_bytes()).digest()
    target = tmp_path / "normalized.wav"

    preprocessing.normalize_audio_to_wav(str(stereo_mp3), str(target))

    with wave.open(str(target), "rb") as output:
        assert output.getframerate() == 16000
        assert output.getnchannels() == 1
        assert output.getsampwidth() == 2
        assert output.getnframes() > 0
    assert hashlib.sha256(stereo_mp3.read_bytes()).digest() == original_digest


def test_temporary_audio_is_removed_after_context(stereo_mp3):
    with preprocessing.temporary_preprocessed_audio(str(stereo_mp3)) as processed_path:
        with wave.open(processed_path, "rb") as output:
            assert output.getframerate() == 16000
        assert Path(processed_path).exists()

    assert not Path(processed_path).exists()
    assert stereo_mp3.exists()


def test_temporary_audio_is_removed_after_consumer_error(stereo_mp3):
    processed_path = None
    with pytest.raises(RuntimeError, match="consumer failed"):
        with preprocessing.temporary_preprocessed_audio(str(stereo_mp3)) as processed_path:
            raise RuntimeError("consumer failed")

    assert processed_path is not None
    assert not Path(processed_path).exists()


def test_corrupt_audio_returns_clear_error(tmp_path):
    corrupt = tmp_path / "corrupt.mp3"
    corrupt.write_bytes(b"not an encoded audio stream")

    with pytest.raises(preprocessing.AudioPreprocessingError, match="Could not inspect audio file"):
        preprocessing.normalize_audio_to_wav(str(corrupt), str(tmp_path / "out.wav"))


def test_missing_ffmpeg_returns_actionable_error(monkeypatch, tmp_path):
    source = tmp_path / "input.wav"
    source.write_bytes(b"input")
    monkeypatch.setattr(preprocessing.shutil, "which", lambda _: None)

    with pytest.raises(preprocessing.AudioPreprocessingError, match="Install FFmpeg"):
        preprocessing.normalize_audio_to_wav(str(source), str(tmp_path / "out.wav"))


def test_whisper_accepts_shared_wav_without_preprocessing_again(monkeypatch):
    from app.config import settings as settings_module
    from app.services.speech import whisper_service

    class FakeModel:
        def transcribe(self, audio_path, **options):
            assert audio_path == "shared/processed.wav"
            assert options["vad_filter"] is True
            assert options["word_timestamps"] is True
            segment = SimpleNamespace(text="hello", start=0.0, end=1.0, avg_logprob=-0.1, words=[])
            return iter([segment]), SimpleNamespace(language="en")

    monkeypatch.setattr(settings_module.settings, "asr_mode", "auto")
    monkeypatch.setattr(whisper_service, "_load_whisper_model", lambda: FakeModel())
    monkeypatch.setattr(
        whisper_service,
        "preprocess_audio_for_asr",
        lambda _: pytest.fail("shared normalized audio must not be converted again"),
    )

    result = whisper_service.transcribe_audio(
        "shared/processed.wav", language_hint="en", audio_is_preprocessed=True,
    )

    assert result["transcript"] == "hello"
    assert result["asr_mode"] == "whisper"