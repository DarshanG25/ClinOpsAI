"""ClinOps-AI backend test suite.

Uses a temporary SQLite database (isolated per test session) and
ASR_MODE=demo so tests run fully offline/deterministically without needing
real Whisper model weights.

Run with:  cd backend && pytest -q
"""
import os
import sys
import math
import struct
import tempfile
import wave
import uuid
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path

# --- Force an isolated temporary DB + demo ASR mode before importing the app ---
TEST_DB_DIRECTORY = tempfile.TemporaryDirectory(prefix="clinops-api-tests-")
TEST_DB_PATH = Path(TEST_DB_DIRECTORY.name) / "clinops_test.db"
TEST_STORAGE_DIRECTORY = tempfile.TemporaryDirectory(prefix="clinops-api-storage-")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["UPLOAD_DIR"] = str(Path(TEST_STORAGE_DIRECTORY.name) / "audio")
os.environ["PDF_OUTPUT_DIR"] = str(Path(TEST_STORAGE_DIRECTORY.name) / "pdfs")
os.environ["MODEL_CACHE_DIR"] = str(Path(TEST_STORAGE_DIRECTORY.name) / "models")
os.environ["ASR_MODE"] = "demo"
os.environ["DEFAULT_LANGUAGE"] = "en"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-not-for-any-real-environment"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["CORS_ALLOWED_ORIGINS"] = '["http://localhost:5173"]'

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

import pytest
from fastapi.testclient import TestClient

from app.main import app  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.db.database import SessionLocal, engine  # noqa: E402
from app.models.domain import Consultation, Doctor, Prescription, User  # noqa: E402
from app.core.security import hash_password  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        db = SessionLocal()
        try:
            doctor = Doctor(name="Test Clinician")
            db.add(doctor)
            db.flush()
            user = User(
                name="Test Clinician",
                email="doctor@example.test",
                password_hash=hash_password("test-password"),
                role="doctor",
                doctor_id=doctor.id,
                is_active=True,
            )
            db.add(user)
            db.commit()
            token = create_access_token(user.id, user.role)
        finally:
            db.close()
        c.headers["Authorization"] = "Bearer " + token
        c.headers["Authorization"] = f"Bearer {token}"
        yield c
    engine.dispose()
    TEST_DB_DIRECTORY.cleanup()
    TEST_STORAGE_DIRECTORY.cleanup()


@pytest.fixture(scope="module")
def patient(client):
    r = client.post("/api/patients", json={
        "name": "Ravi Kumar", "age": 34, "gender": "male", "language": "en",
    })
    assert r.status_code == 201
    return r.json()


@pytest.fixture(scope="module")
def consultation(client, patient):
    r = client.post("/api/consultations", json={
        "patient_id": patient["id"], "language": "en",
    })
    assert r.status_code == 201
    return r.json()


def _valid_test_wav() -> bytes:
    buffer = BytesIO()
    sample_rate = 16000
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        frames = b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * index / sample_rate)))
            for index in range(sample_rate // 4)
        )
        audio.writeframes(frames)
    return buffer.getvalue()


def _register_patient(client, name: str = "Secure Patient") -> User:
    email = f"{uuid.uuid4().hex}@example.test"
    response = client.post("/api/auth/register", json={
        "name": name,
        "email": email,
        "password": "patient-test-password",
        "role": "patient",
    })
    assert response.status_code == 201
    db = SessionLocal()
    try:
        return db.query(User).filter(User.email == email).one()
    finally:
        db.expunge_all()
        db.close()


@contextmanager
def _as_user(client, user: User):
    previous = client.headers.get("Authorization")
    client.headers["Authorization"] = (
        "Bearer " + create_access_token(user.id, user.role)
    )
    try:
        yield
    finally:
        if previous is None:
            client.headers.pop("Authorization", None)
        else:
            client.headers["Authorization"] = previous


# ---------- 1. Health ----------
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "disclaimer" in body
    assert "asr" in body
    assert "database_url" not in body
    assert "load_failure_reason" not in body["asr"]


def test_cors_allows_only_configured_origins(client):
    allowed = client.options(
        "/api/auth/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert allowed.headers["access-control-allow-credentials"] == "true"

    blocked = client.options(
        "/api/auth/me",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in blocked.headers


def test_wildcard_credentialed_cors_configuration_is_rejected():
    from pydantic import ValidationError
    from app.config.settings import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_allowed_origins=["*"])


# ---------- 2. Patient creation ----------
def test_create_patient(client):
    r = client.post("/api/patients", json={"name": "Test Patient", "age": 40, "language": "en"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Test Patient"
    assert "id" in body

    consultation = client.post(
        "/api/consultations", json={"patient_id": body["id"]},
    )
    assert consultation.status_code == 201

    r2 = client.get(f"/api/patients/{body['id']}")
    assert r2.status_code == 200
    assert r2.json()["id"] == body["id"]


def test_get_missing_patient_404(client):
    r = client.get("/api/patients/does-not-exist")
    assert r.status_code == 404


# ---------- 3. Consultation creation ----------
def test_create_consultation(client, patient):
    r = client.post("/api/consultations", json={"patient_id": patient["id"], "language": "en"})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "CREATED"
    assert body["patient_id"] == patient["id"]


def test_create_consultation_missing_patient_404(client):
    r = client.post("/api/consultations", json={"patient_id": "nope", "language": "en"})
    assert r.status_code == 404


# ---------- 4/5/6. Audio upload -> ASR -> transcript ----------
def test_audio_upload_and_process(client, consultation):
    cid = consultation["id"]

    # rejects bad extension
    bad = client.post(f"/api/consultations/{cid}/audio",
                       files={"file": ("note.txt", b"hello", "text/plain")})
    assert bad.status_code == 400

    files = {"file": ("sample.wav", _valid_test_wav(), "audio/wav")}
    r = client.post(f"/api/consultations/{cid}/audio", files=files)
    assert r.status_code == 200
    assert r.json()["status"] == "AUDIO_UPLOADED"

    r2 = client.post(f"/api/consultations/{cid}/process")
    assert r2.status_code == 200
    body = r2.json()
    assert body["asr_mode"] == "demo"  # explicitly labelled, never silently fabricated
    assert "[DEMO TRANSCRIPT" in body["transcript"]
    assert len(body["transcript"]) > 0
    assert isinstance(body["segments"], list) and len(body["segments"]) > 0

    r3 = client.get(f"/api/consultations/{cid}/transcript")
    assert r3.status_code == 200
    assert r3.json()["text"] == body["transcript"]


def test_preprocessing_failure_marks_consultation_failed(client, patient, monkeypatch):
    from app.services.audio import audio_preprocessor

    consultation_response = client.post("/api/consultations", json={"patient_id": patient["id"]})
    consultation_id = consultation_response.json()["id"]
    uploaded = client.post(
        f"/api/consultations/{consultation_id}/audio",
        files={"file": ("failure.wav", _valid_test_wav(), "audio/wav")},
    )
    assert uploaded.status_code == 200
    monkeypatch.setattr(audio_preprocessor.shutil, "which", lambda _: None)

    processed = client.post(f"/api/consultations/{consultation_id}/process")

    assert processed.status_code == 500
    assert processed.json()["detail"] == "Audio preprocessing or processing failed."
    consultation = client.get(f"/api/consultations/{consultation_id}").json()
    assert consultation["status"] == "FAILED"


def test_process_without_audio_fails(client):
    """A consultation with no uploaded audio should fail /process cleanly."""
    patient = client.post("/api/patients", json={"name": "No Audio Patient"}).json()
    cons = client.post("/api/consultations", json={"patient_id": patient["id"]}).json()
    response = client.post(f"/api/consultations/{cons['id']}/process")
    assert response.status_code == 400


# ---------- 7. Clinical extraction (+ dosage/frequency/duration) ----------
def test_clinical_extraction(client, consultation):
    cid = consultation["id"]
    r = client.get(f"/api/consultations/{cid}/clinical-data")
    assert r.status_code == 200
    data = r.json()
    assert data["consultation_id"] == cid

    all_symptom_texts = [s["normalized"] for s in data["symptoms"]]
    assert "fever" in all_symptom_texts
    assert "headache" in all_symptom_texts

    meds = data["medications"]
    assert len(meds) >= 1
    paracetamol = next((m for m in meds if m["normalized"] == "Paracetamol"), None)
    assert paracetamol is not None
    assert paracetamol["dosage"] == "500 mg"
    assert paracetamol["frequency"] == "twice daily"
    assert paracetamol["duration"] is not None


def test_dosage_frequency_duration_extraction_hindi():
    """Extractor correctly separates dosage/frequency/duration for two
    medicines mentioned back-to-back in transliterated Hindi (regression
    test for a window-truncation bug found during development)."""
    from app.services.nlp.entity_extractor import extract_clinical_data

    text = (
        "Paracetamol 500 mg din mein do baar, teen din tak lijiye. "
        "Aur Amoxicillin 500 mg din mein teen baar, paanch din tak."
    )
    entities = extract_clinical_data(text)
    meds = {e["normalized"]: e for e in entities if e["entity_type"] == "medication"}

    assert meds["Paracetamol"]["dosage"] == "500 mg"
    assert meds["Paracetamol"]["frequency"] == "twice daily"
    assert meds["Paracetamol"]["duration"] == "3 day(s)"

    assert meds["Amoxicillin"]["dosage"] == "500 mg"
    assert meds["Amoxicillin"]["frequency"] == "three times daily"
    assert meds["Amoxicillin"]["duration"] == "5 day(s)"


def test_extraction_never_hardcoded_for_unrelated_text():
    """Sanity check that extraction reflects actual input, not fixed output."""
    from app.services.nlp.entity_extractor import extract_clinical_data

    entities = extract_clinical_data("The weather is nice today and I went for a walk.")
    assert entities == []  # nothing clinical in this sentence -> empty, not fabricated


def test_clinical_extraction_handles_negation_and_multiple_findings():
    from app.services.nlp.entity_extractor import extract_clinical_data

    entities = extract_clinical_data(
        "No fever but persistent cough. The patient denies asthma. I do not have diabetes."
    )
    by_name = {e["normalized"]: e for e in entities if e.get("normalized")}

    assert by_name["fever"]["status"] == "negated"
    assert by_name["cough"]["status"] == "positive"
    assert by_name["asthma"]["status"] == "negated"
    assert by_name["diabetes"]["status"] == "negated"


def test_recommendations_only_from_explicit_orders_and_preserve_details():
    from app.services.recommendation.recommendation_service import generate_recommendations

    entities = [
        {"entity_type": "symptom", "Normalized": "fever", "normalized": "fever", "status": "positive"},
        {"entity_type": "medication", "text": "Paracetamol", "normalized": "Paracetamol",
         "status": "doctor_ordered", "dosage": "500 mg", "frequency": "twice daily",
         "duration": "3 days", "route": "oral"},
    ]
    recs = generate_recommendations(entities)
    assert recs
    assert recs[0]["medicine"] == "Paracetamol"
    assert recs[0]["dosage"] == "500 mg"
    assert recs[0]["frequency"] == "twice daily"
    assert recs[0]["duration"] == "3 days"

    assert generate_recommendations([{"entity_type": "symptom", "normalized": "fever", "status": "positive"}]) == []
    assert generate_recommendations([
        {"entity_type": "medication", "text": "Metformin", "normalized": "Metformin", "status": "historical"}
    ]) == []


# ---------- 8. Recommendation ----------
def test_recommendations_generated(client, consultation):
    cid = consultation["id"]
    r = client.get(f"/api/consultations/{cid}/recommendations")
    assert r.status_code == 200
    recs = r.json()
    assert len(recs) >= 1
    for rec in recs:
        assert 0.0 <= rec["score"] <= 1.0
        assert rec["status"] in ("AI_SUGGESTED", "DOCTOR_EDITED")

    names = [r["medicine"] for r in recs]
    assert "Paracetamol" in names


def test_recommendation_regenerate_endpoint(client, consultation):
    cid = consultation["id"]
    r = client.post(f"/api/consultations/{cid}/recommendations")
    assert r.status_code == 200
    assert len(r.json()) >= 1


# ---------- 9. Doctor review/edit ----------
def test_doctor_edit_recommendations(client, consultation):
    cid = consultation["id"]
    payload = {"items": [{
        "medicine": "Paracetamol", "dosage": "500 mg", "frequency": "twice daily",
        "duration": "3 days", "route": "oral", "reason": "Doctor confirmed dosage",
    }]}
    r = client.put(f"/api/consultations/{cid}/recommendations", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["status"] == "DOCTOR_EDITED"
    assert body[0]["doctor_edited"] is True


def test_audio_preprocessor_rejects_unsupported_file(tmp_path):
    from app.services.audio.audio_preprocessor import preprocess_audio_for_asr

    bad_file = tmp_path / "notes.txt"
    bad_file.write_text("not audio", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported audio"):
        preprocess_audio_for_asr(str(bad_file))


def test_whisper_segments_include_metadata():
    from app.services.speech.whisper_service import transcribe_audio

    result = transcribe_audio("/tmp/does-not-exist.wav")
    assert result["asr_mode"] == "demo"
    assert result["segments"]
    segment = result["segments"][0]
    assert "start" in segment and "end" in segment and "text" in segment
    assert "language" in segment
    assert "confidence" in segment


def test_auto_mode_never_returns_fixed_demo_transcript(monkeypatch):
    """Real-ASR mode must report unavailable ASR, not fabricate clinical data."""
    from app.config import settings as settings_module
    from app.services.speech import whisper_service

    monkeypatch.setattr(settings_module.settings, "asr_mode", "auto")
    monkeypatch.setattr(whisper_service, "_load_whisper_model", lambda: None)
    monkeypatch.setattr(whisper_service, "_model_load_failed_reason", "test model unavailable")

    with pytest.raises(RuntimeError, match="Real speech recognition is unavailable"):
        whisper_service.transcribe_audio("/tmp/first-conversation.wav")


def test_speaker_role_update_persists_without_changing_transcript(client, patient):
    from app.db.database import SessionLocal
    from app.repositories import repository as repo

    consultation_response = client.post("/api/consultations", json={"patient_id": patient["id"]})
    assert consultation_response.status_code == 201
    consultation_id = consultation_response.json()["id"]
    original_text = "What symptoms do you have? I have a fever. He had vomiting."
    segments = [
        {"start": 0.0, "end": 1.0, "text": "What symptoms do you have?", "speaker_id": "SPEAKER_00", "speaker_role": "Other/Unknown"},
        {"start": 1.1, "end": 2.0, "text": "I have a fever.", "speaker_id": "SPEAKER_01", "speaker_role": "Other/Unknown"},
        {"start": 2.1, "end": 3.0, "text": "He had vomiting.", "speaker_id": "SPEAKER_02", "speaker_role": "Other/Unknown"},
    ]
    db = SessionLocal()
    try:
        repo.upsert_transcript(
            db, consultation_id, text=original_text, language="en", segments=segments,
            asr_mode="whisper", diarization_status="complete",
        )
    finally:
        db.close()

    response = client.put(
        f"/api/consultations/{consultation_id}/speaker-roles",
        json={"roles": {"SPEAKER_00": "Doctor", "SPEAKER_02": "Patient's Attendant/Relative"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == original_text
    assert [segment["speaker_id"] for segment in body["segments"]] == [
        "SPEAKER_00", "SPEAKER_01", "SPEAKER_02",
    ]
    assert body["segments"][0]["speaker_role"] == "Doctor"
    assert body["segments"][1]["speaker_role"] == "Other/Unknown"
    assert body["segments"][2]["speaker_role"] == "Patient's Attendant/Relative"

    invalid = client.put(
        f"/api/consultations/{consultation_id}/speaker-roles",
        json={"roles": {"SPEAKER_01": "Nurse"}},
    )
    assert invalid.status_code == 422


# ---------- 10. Doctor approval ----------
def test_doctor_approval_generates_prescription(client, consultation):
    cid = consultation["id"]
    doctor_id = consultation["doctor_id"]

    r = client.post(f"/api/consultations/{cid}/approve", json={
        "doctor_id": doctor_id, "approved": True, "approved_by": "spoofed-id",
    })
    assert r.status_code == 200
    presc = r.json()
    assert presc["status"] == "APPROVED"
    assert presc["approved_by"] == doctor_id
    assert len(presc["items"]) >= 1

    consult = client.get(f"/api/consultations/{cid}").json()
    assert consult["status"] == "APPROVED"


def test_rejection_flow(client, patient):
    """A rejected consultation should not be able to produce a PDF."""
    cons = client.post("/api/consultations", json={"patient_id": patient["id"]}).json()
    cid = cons["id"]
    client.post(f"/api/consultations/{cid}/audio",
                files={"file": ("a.wav", _valid_test_wav(), "audio/wav")})
    client.post(f"/api/consultations/{cid}/process")

    doctor_id = cons["doctor_id"]
    r = client.post(f"/api/consultations/{cid}/approve", json={
        "doctor_id": doctor_id, "approved": False, "rejection_reason": "Needs in-person exam",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "REJECTED"

    pdf_resp = client.get(f"/api/consultations/{cid}/prescription/pdf")
    assert pdf_resp.status_code == 400  # only APPROVED prescriptions can generate a PDF


# ---------- 11/12. Prescription + PDF ----------
def test_prescription_and_pdf(client, consultation):
    cid = consultation["id"]

    r = client.get(f"/api/consultations/{cid}/prescription")
    assert r.status_code == 200
    presc = r.json()
    assert presc["status"] == "APPROVED"

    r2 = client.get(f"/api/consultations/{cid}/prescription/pdf")
    assert r2.status_code == 200
    assert r2.headers["content-type"] == "application/pdf"
    assert r2.content[:4] == b"%PDF"
    assert len(r2.content) > 500  # non-trivial PDF, not an empty stub

    consult = client.get(f"/api/consultations/{cid}").json()
    assert consult["status"] == "PRESCRIPTION_GENERATED"


# ---------- 13. Persistence ----------
def test_data_persists_after_reread(client, consultation):
    """Re-fetching everything for the same consultation returns consistent,
    previously-stored data (not recomputed on the fly)."""
    cid = consultation["id"]
    t1 = client.get(f"/api/consultations/{cid}/transcript").json()
    t2 = client.get(f"/api/consultations/{cid}/transcript").json()
    assert t1 == t2

    p1 = client.get(f"/api/consultations/{cid}/prescription").json()
    p2 = client.get(f"/api/consultations/{cid}/prescription").json()
    assert p1["id"] == p2["id"]
    assert p1["items"] == p2["items"]


# ---------- 14. Full end-to-end synthetic consultation ----------
def test_end_to_end_synthetic_consultation():
    """Runs the entire pipeline once, top to bottom, on its own patient/
    consultation, independent of the module-scoped fixtures above."""
    with TestClient(app) as c:
        db = SessionLocal()
        try:
            doctor_user = db.query(User).filter(
                User.email == "doctor@example.test",
            ).one()
            token = create_access_token(doctor_user.id, doctor_user.role)
        finally:
            db.close()
        c.headers["Authorization"] = "Bearer " + token

        patient = c.post("/api/patients", json={
            "name": "Synthetic Demo Patient", "age": 30, "gender": "female", "language": "en",
        }).json()

        consultation = c.post("/api/consultations", json={
            "patient_id": patient["id"], "language": "en",
        }).json()
        cid = consultation["id"]

        c.post(f"/api/consultations/{cid}/audio",
             files={"file": ("demo.wav", _valid_test_wav(), "audio/wav")})

        process = c.post(f"/api/consultations/{cid}/process").json()
        assert process["transcript"]

        clinical = c.get(f"/api/consultations/{cid}/clinical-data").json()
        assert any(clinical[k] for k in ("symptoms", "diagnoses", "medications", "precautions"))

        recs = c.get(f"/api/consultations/{cid}/recommendations").json()
        assert len(recs) >= 1

        doctor_id = consultation["doctor_id"]
        approval = c.post(f"/api/consultations/{cid}/approve", json={
            "doctor_id": doctor_id, "approved": True,
        }).json()
        assert approval["status"] == "APPROVED"

        pdf = c.get(f"/api/consultations/{cid}/prescription/pdf")
        assert pdf.status_code == 200
        assert pdf.content[:4] == b"%PDF"

        final = c.get(f"/api/consultations/{cid}").json()
        assert final["status"] == "PRESCRIPTION_GENERATED"


def test_clinical_summary_endpoints_for_consultation_without_transcript(client, patient):
    from app.db.database import SessionLocal
    from app.repositories import repository as repo

    consultation = client.post(
        "/api/consultations", json={"patient_id": patient["id"]},
    ).json()
    cid = consultation["id"]

    assert client.get(f"/api/consultations/{cid}/clinical-summary").status_code == 404
    assert client.post(f"/api/consultations/{cid}/clinical-summary/generate").status_code == 404

    db = SessionLocal()
    try:
        repo.upsert_transcript(
            db, cid, text="Patient reports headache since yesterday.",
            language="en",
            segments=[{
                "start": 1.25, "end": 3.5,
                "text": "Patient reports headache since yesterday.",
                "speaker_role": "Patient",
            }],
            asr_mode="demo",
        )
    finally:
        db.close()

    assert client.get(f"/api/consultations/{cid}/clinical-summary").status_code == 404
    generated = client.post(f"/api/consultations/{cid}/clinical-summary/generate")
    assert generated.status_code == 200
    assert generated.json()["relevant_segments"][0]["start"] == 1.25


def test_process_persists_summary_without_changing_full_transcript(client, patient):
    consultation = client.post(
        "/api/consultations", json={"patient_id": patient["id"], "language": "en"},
    ).json()
    cid = consultation["id"]
    uploaded = client.post(
        f"/api/consultations/{cid}/audio",
        files={"file": ("summary.wav", _valid_test_wav(), "audio/wav")},
    )
    assert uploaded.status_code == 200

    processed = client.post(f"/api/consultations/{cid}/process")
    assert processed.status_code == 200
    assert processed.json()["clinical_summary_status"] == "generated"

    transcript = client.get(f"/api/consultations/{cid}/transcript").json()
    summary_response = client.get(f"/api/consultations/{cid}/clinical-summary")
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert transcript["text"] == processed.json()["transcript"]
    assert summary["consultation_id"] == cid
    assert summary["summary_text"]
    assert summary["method"] == "keyword-extractive-v1"
    assert len(summary["segment_scores"]) == len(transcript["segments"])
    assert summary["relevant_segments"]
    assert summary["source_segment_ids"] == [
        segment["segment_id"] for segment in summary["relevant_segments"]
    ]
    assert all(segment["start"] is not None and segment["end"] is not None for segment in summary["relevant_segments"])

    regenerated = client.post(f"/api/consultations/{cid}/clinical-summary/generate")
    assert regenerated.status_code == 200
    assert regenerated.json()["summary_text"] == summary["summary_text"]


def test_summary_failure_preserves_transcript_and_continues_processing(client, patient, monkeypatch):
    from app.services.nlp import clinical_summary

    consultation = client.post(
        "/api/consultations", json={"patient_id": patient["id"], "language": "en"},
    ).json()
    cid = consultation["id"]
    client.post(
        f"/api/consultations/{cid}/audio",
        files={"file": ("summary-failure.wav", _valid_test_wav(), "audio/wav")},
    )

    def fail_summary(_segments):
        raise RuntimeError("synthetic summarization failure")

    monkeypatch.setattr(clinical_summary, "generate_clinical_summary", fail_summary)
    processed = client.post(f"/api/consultations/{cid}/process")

    assert processed.status_code == 200
    assert processed.json()["clinical_summary_status"] == "failed"
    assert client.get(f"/api/consultations/{cid}/transcript").json()["text"] == processed.json()["transcript"]
    assert client.get(f"/api/consultations/{cid}/clinical-summary").status_code == 404
    assert client.get(f"/api/consultations/{cid}/clinical-data").status_code == 200


def test_missing_invalid_expired_and_missing_claim_tokens_are_rejected(client):
    import jwt

    authorization = client.headers.pop("Authorization", None)
    try:
        assert client.get("/api/auth/me").status_code == 401
        client.headers["Authorization"] = "Bearer not-a-valid-token"
        assert client.get("/api/auth/me").status_code == 401

        secret = os.environ["JWT_SECRET_KEY"]
        missing_exp = jwt.encode(
            {"sub": "unknown", "role": "doctor"},
            secret,
            algorithm="HS256",
        )
        client.headers["Authorization"] = "Bearer " + missing_exp
        assert client.get("/api/auth/me").status_code == 401

        expired = jwt.encode(
            {"sub": "unknown", "role": "doctor", "exp": 1},
            secret,
            algorithm="HS256",
        )
        client.headers["Authorization"] = "Bearer " + expired
        assert client.get("/api/auth/me").status_code == 401
    finally:
        if authorization:
            client.headers["Authorization"] = authorization


def test_authentication_and_registration_policy(client):
    denied_doctor = client.post("/api/auth/register", json={
        "name": "Unprovisioned Doctor",
        "email": f"{uuid.uuid4().hex}@example.test",
        "password": "patient-test-password",
        "role": "doctor",
    })
    assert denied_doctor.status_code == 403

    invalid_login = client.post("/api/auth/login", json={
        "email": "doctor@example.test",
        "password": "incorrect-password",
    })
    assert invalid_login.status_code == 401

    login = client.post("/api/auth/login", json={
        "email": "doctor@example.test",
        "password": "test-password",
    })
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    assert "password_hash" not in login.json()["user"]

    whoami = client.get("/api/auth/me")
    assert whoami.status_code == 200
    assert whoami.json()["role"] == "doctor"


def test_inactive_and_role_mismatched_accounts_are_rejected(client):
    user = _register_patient(client)
    db = SessionLocal()
    try:
        stored_user = db.query(User).filter(User.id == user.id).one()
        stored_user.is_active = False
        db.commit()
    finally:
        db.close()
    with _as_user(client, user):
        assert client.get("/api/auth/me").status_code == 401

    user.is_active = True
    role_mismatch_token = create_access_token(user.id, "doctor")
    previous = client.headers.get("Authorization")
    client.headers["Authorization"] = "Bearer " + role_mismatch_token
    try:
        assert client.get("/api/auth/me").status_code == 401
    finally:
        client.headers["Authorization"] = previous


def test_patient_registration_does_not_link_existing_records(client, patient):
    existing_patient_id = patient["id"]
    email = f"{uuid.uuid4().hex}@example.test"
    response = client.post("/api/auth/register", json={
        "name": patient["name"],
        "email": email,
        "password": "patient-test-password",
        "role": "patient",
        "patient_id": existing_patient_id,
        "doctor_id": "attacker-controlled-doctor",
        "is_active": False,
    })
    assert response.status_code == 201

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        assert user.patient_id != existing_patient_id
        assert user.is_active is True
        assert user.doctor_id is None
    finally:
        db.close()


def test_patient_cannot_read_another_patient_record(client, patient):
    patient_user = _register_patient(client)
    with _as_user(client, patient_user):
        own_records = client.get("/api/patients")
        other_record = client.get(f"/api/patients/{patient['id']}")
    assert own_records.status_code == 200
    assert len(own_records.json()) == 1
    assert own_records.json()[0]["id"] == patient_user.patient_id
    assert other_record.status_code == 403


def test_doctor_cannot_access_another_doctors_consultation(client, patient):
    db = SessionLocal()
    try:
        other_doctor = Doctor(name="Other Clinician")
        db.add(other_doctor)
        db.flush()
        other_user = User(
            name="Other Clinician",
            email=f"{uuid.uuid4().hex}@example.test",
            password_hash=hash_password("other-test-password"),
            role="doctor",
            doctor_id=other_doctor.id,
            is_active=True,
        )
        db.add(other_user)
        db.flush()
        consultation = Consultation(
            patient_id=patient["id"],
            doctor_id=other_doctor.id,
            status="CREATED",
        )
        db.add(consultation)
        db.commit()
        db.refresh(other_user)
        consultation_id = consultation.id
        db.expunge(other_user)
    finally:
        db.close()

    with _as_user(client, other_user):
        assert client.get(f"/api/consultations/{consultation_id}").status_code == 200
    assert client.get(f"/api/consultations/{consultation_id}").status_code == 403
    assert client.post(f"/api/consultations/{consultation_id}/process").status_code == 403


def test_patient_cannot_perform_doctor_only_write_operations(client):
    patient_user = _register_patient(client)
    created = client.post("/api/consultations", json={
        "patient_id": patient_user.patient_id,
    })
    assert created.status_code == 201
    consultation_id = created.json()["id"]
    doctor_id = created.json()["doctor_id"]

    with _as_user(client, patient_user):
        assert client.post("/api/patients", json={"name": "Spoofed"}).status_code == 403
        assert client.post("/api/consultations", json={
            "patient_id": patient_user.patient_id,
        }).status_code == 403
        assert client.post(
            f"/api/consultations/{consultation_id}/audio",
            files={"file": ("write.wav", _valid_test_wav(), "audio/wav")},
        ).status_code == 403
        assert client.post(f"/api/consultations/{consultation_id}/process").status_code == 403
        assert client.post(
            f"/api/consultations/{consultation_id}/recommendations",
        ).status_code == 403
        assert client.put(
            f"/api/consultations/{consultation_id}/recommendations",
            json={"items": []},
        ).status_code == 403
        assert client.post(
            f"/api/consultations/{consultation_id}/approve",
            json={"doctor_id": doctor_id, "approved": True},
        ).status_code == 403
        assert client.get(
            f"/api/consultations/{consultation_id}/prescription/pdf",
        ).status_code == 403


def test_client_cannot_assign_consultation_to_another_doctor(client, patient):
    db = SessionLocal()
    try:
        other_doctor = Doctor(name="Unlinked Clinician")
        db.add(other_doctor)
        db.commit()
        other_doctor_id = other_doctor.id
    finally:
        db.close()

    response = client.post("/api/consultations", json={
        "patient_id": patient["id"],
        "doctor_id": other_doctor_id,
    })
    assert response.status_code == 403


def test_patients_only_receive_approved_prescriptions(client):
    patient_user = _register_patient(client)
    consultation_response = client.post("/api/consultations", json={
        "patient_id": patient_user.patient_id,
    })
    assert consultation_response.status_code == 201
    consultation_id = consultation_response.json()["id"]
    doctor_id = consultation_response.json()["doctor_id"]

    db = SessionLocal()
    try:
        consultation = db.query(Consultation).filter(
            Consultation.id == consultation_id,
        ).one()
        consultation.status = "PRESCRIPTION_GENERATED"
        db.commit()
        from app.repositories import repository as repo
        prescription = repo.create_or_update_prescription(
            db,
            consultation_id=consultation_id,
            patient_id=patient_user.patient_id,
            doctor_id=doctor_id,
            diagnosis_summary="Test-only summary",
            precautions=[],
            status="DRAFT",
            items=[{"medicine": "Test-only medicine"}],
        )
        prescription.pdf_path = "/private/test-only.pdf"
        db.commit()
    finally:
        db.close()

    with _as_user(client, patient_user):
        draft = client.get(f"/api/consultations/{consultation_id}/prescription")
    assert draft.status_code == 403

    db = SessionLocal()
    try:
        prescription = db.query(Prescription).filter(
            Prescription.consultation_id == consultation_id,
        ).one()
        prescription.status = "REJECTED"
        db.commit()
    finally:
        db.close()
    with _as_user(client, patient_user):
        rejected = client.get(f"/api/consultations/{consultation_id}/prescription")
    assert rejected.status_code == 403

    db = SessionLocal()
    try:
        prescription = db.query(Prescription).filter(
            Prescription.consultation_id == consultation_id,
        ).one()
        prescription.status = "APPROVED"
        prescription.approved_by = doctor_id
        db.commit()
    finally:
        db.close()

    with _as_user(client, patient_user):
        approved = client.get(f"/api/consultations/{consultation_id}/prescription")
        consultation_list = client.get("/api/consultations")
        consultation_detail = client.get(f"/api/consultations/{consultation_id}")
        transcript = client.get(f"/api/consultations/{consultation_id}/transcript")
        clinical_data = client.get(f"/api/consultations/{consultation_id}/clinical-data")
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["doctor_id"] is None
    assert approved.json()["approved_by"] is None
    assert approved.json()["pdf_path"] is None
    assert consultation_list.status_code == 200
    assert all(row["doctor_id"] is None and row["notes"] is None for row in consultation_list.json())
    assert consultation_detail.status_code == 200
    assert consultation_detail.json()["doctor_id"] is None
    assert consultation_detail.json()["notes"] is None
    assert consultation_detail.json()["audio_path"] is None
    assert transcript.status_code == 403
    assert clinical_data.status_code == 403
