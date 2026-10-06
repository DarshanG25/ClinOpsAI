import logging
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.database import get_db
from app.models import domain as m
from app.repositories import repository as repo
from app.schemas.api_models import (
    ConsultationCreate, ConsultationOut, AudioUploadResponse, ProcessResponse,
    TranscriptOut, ClinicalDataOut, ClinicalEntityOut, ClinicalSummaryOut, RecommendationOut,
    RecommendationUpdateRequest, ApprovalRequest, PrescriptionOut,
    SpeakerRoleUpdateRequest,
)
from app.services.speech.whisper_service import transcribe_audio
from app.services.speech.speaker_diarization import apply_speaker_roles, diarize_transcription
from app.services.audio.audio_preprocessor import temporary_preprocessed_audio
from app.services.nlp.entity_extractor import extract_clinical_data
from app.services.nlp import clinical_summary
from app.services.recommendation.recommendation_service import generate_recommendations
from app.services.prescription.prescription_service import (
    build_prescription_items, summarize_diagnosis, default_precautions,
)
from app.services.pdf_generator.pdf_service import generate_prescription_pdf

logger = logging.getLogger("clinops.consultations")
router = APIRouter()

ALLOWED_AUDIO_EXT = {".wav", ".mp3", ".m4a", ".mpeg", ".mpg", ".mp2", ".flac", ".ogg"}


def _get_consultation_or_404(db: Session, consultation_id: str) -> m.Consultation:
    consultation = repo.get_consultation(db, consultation_id)
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return consultation


# ---------- Create / read ----------
@router.post("/consultations", response_model=ConsultationOut, status_code=201)
def create_consultation(payload: ConsultationCreate, db: Session = Depends(get_db)):
    patient = repo.get_patient(db, payload.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    doctor_id = payload.doctor_id
    if not doctor_id:
        doctor_id = repo.get_or_create_default_doctor(db).id
    consultation = repo.create_consultation(
        db, patient_id=payload.patient_id, doctor_id=doctor_id,
        language=payload.language, notes=payload.notes,
    )
    return consultation


@router.get("/consultations", response_model=List[ConsultationOut])
def list_consultations(db: Session = Depends(get_db)):
    return repo.list_consultations(db)


@router.get("/consultations/{consultation_id}", response_model=ConsultationOut)
def get_consultation(consultation_id: str, db: Session = Depends(get_db)):
    return _get_consultation_or_404(db, consultation_id)


# ---------- Audio upload ----------
@router.post("/consultations/{consultation_id}/audio", response_model=AudioUploadResponse)
async def upload_audio(consultation_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    consultation = _get_consultation_or_404(db, consultation_id)

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_AUDIO_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported audio format '{ext}'. Allowed: {sorted(ALLOWED_AUDIO_EXT)}")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{consultation_id}_{uuid.uuid4().hex[:8]}{ext}"
    uploaded_size = 0
    try:
        with dest.open("wb") as saved_audio:
            while chunk := await file.read(1024 * 1024):
                uploaded_size += len(chunk)
                if uploaded_size > settings.max_audio_size:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Audio file exceeds MAX_AUDIO_SIZE ({settings.max_audio_size} bytes)",
                    )
                saved_audio.write(chunk)
        if uploaded_size == 0:
            raise HTTPException(status_code=400, detail="Uploaded audio file is empty")
    except BaseException:
        dest.unlink(missing_ok=True)
        raise

    repo.set_audio_path(db, consultation, str(dest))

    return AudioUploadResponse(
        consultation_id=consultation_id, status=consultation.status,
        audio_path=str(dest), message="Audio uploaded. Call /process to run ASR + clinical extraction.",
    )


# ---------- Process: ASR -> transcript -> summary -> extraction -> recommendations ----------
@router.post("/consultations/{consultation_id}/process", response_model=ProcessResponse)
def process_consultation(consultation_id: str, db: Session = Depends(get_db)):
    consultation = _get_consultation_or_404(db, consultation_id)
    if not consultation.audio_path:
        raise HTTPException(status_code=400, detail="No audio uploaded for this consultation yet")

    repo.set_consultation_status(db, consultation, m.ConsultationStatus.PROCESSING.value)

    try:
        with temporary_preprocessed_audio(consultation.audio_path) as processed_audio_path:
            asr_result = transcribe_audio(
                processed_audio_path,
                language_hint=consultation.language,
                audio_is_preprocessed=True,
            )
            segments, diarization_status = diarize_transcription(
                processed_audio_path,
                asr_result.get("word_segments", []),
                asr_result["segments"],
                is_demo=asr_result["asr_mode"] == "demo",
                audio_is_preprocessed=True,
            )
    except Exception as exc:  # noqa: BLE001
        error_message = f"Audio preprocessing or processing failed: {exc}"
        repo.set_consultation_status(
            db, consultation, m.ConsultationStatus.FAILED.value, error_message=error_message,
        )
        raise HTTPException(status_code=500, detail=error_message) from exc

    repo.upsert_transcript(
        db, consultation_id, text=asr_result["transcript"], language=asr_result["language"],
        segments=segments, asr_mode=asr_result["asr_mode"],
        diarization_status=diarization_status,
    )
    repo.set_consultation_status(db, consultation, m.ConsultationStatus.TRANSCRIBED.value)
    repo.delete_clinical_summary(db, consultation_id)

    summary_status = "failed"
    extraction_text = asr_result["transcript"]
    try:
        summary_result = clinical_summary.generate_clinical_summary(segments)
        repo.upsert_clinical_summary(
            db, consultation_id,
            summary_text=summary_result["summary_text"],
            segment_scores=summary_result["segment_scores"],
            relevant_segments=summary_result["relevant_segments"],
            source_segment_ids=summary_result["source_segment_ids"],
            status=summary_result["status"],
            method=summary_result["method"],
            version=summary_result["version"],
        )
        summary_status = summary_result["status"]
        extraction_text = summary_result["summary_text"]
    except Exception:  # noqa: BLE001 - transcript and downstream workflow must survive summary failure
        db.rollback()
        logger.exception("Clinical summary generation failed for consultation %s", consultation_id)

    # Clinical extraction
    entities = extract_clinical_data(extraction_text)
    repo.replace_clinical_entities(db, consultation_id, entities)
    status_after_extraction = (
        m.ConsultationStatus.CLINICAL_EXTRACTED.value if entities else m.ConsultationStatus.TRANSCRIBED.value
    )
    repo.set_consultation_status(db, consultation, status_after_extraction)

    # Recommendations (best-effort; doctor still reviews everything)
    if entities:
        recs = generate_recommendations(entities)
        repo.replace_recommendations(db, consultation_id, [
            {**r, "status": m.RecommendationStatus.AI_SUGGESTED.value} for r in recs
        ])
        if recs:
            repo.set_consultation_status(db, consultation, m.ConsultationStatus.RECOMMENDATIONS_GENERATED.value)

    return ProcessResponse(
        consultation_id=consultation_id,
        status=consultation.status,
        language=asr_result["language"],
        transcript=asr_result["transcript"],
        segments=segments,
        asr_mode=asr_result["asr_mode"],
        diarization_status=diarization_status,
        clinical_summary_status=summary_status,
    )


# ---------- Transcript / clinical data ----------
@router.get("/consultations/{consultation_id}/transcript", response_model=TranscriptOut)
def get_transcript(consultation_id: str, db: Session = Depends(get_db)):
    _get_consultation_or_404(db, consultation_id)
    transcript = repo.get_transcript(db, consultation_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not available yet. Call /process first.")
    return TranscriptOut(
        consultation_id=consultation_id, text=transcript.text, language=transcript.language,
        segments=transcript.segments or [], asr_mode=transcript.asr_mode,
        diarization_status=transcript.diarization_status or "not_run",
    )


@router.get("/consultations/{consultation_id}/clinical-summary", response_model=ClinicalSummaryOut)
def get_clinical_summary(consultation_id: str, db: Session = Depends(get_db)):
    _get_consultation_or_404(db, consultation_id)
    summary = repo.get_clinical_summary(db, consultation_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Clinical summary not available. Generate it after transcription.")
    return summary


@router.post("/consultations/{consultation_id}/clinical-summary/generate", response_model=ClinicalSummaryOut)
def generate_consultation_clinical_summary(consultation_id: str, db: Session = Depends(get_db)):
    _get_consultation_or_404(db, consultation_id)
    transcript = repo.get_transcript(db, consultation_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not available yet. Process audio first.")
    try:
        result = clinical_summary.generate_clinical_summary(transcript.segments or [])
        return repo.upsert_clinical_summary(
            db, consultation_id,
            summary_text=result["summary_text"],
            segment_scores=result["segment_scores"],
            relevant_segments=result["relevant_segments"],
            source_segment_ids=result["source_segment_ids"],
            status=result["status"],
            method=result["method"],
            version=result["version"],
        )
    except Exception as exc:  # noqa: BLE001 - explicit API failure, no fabricated summary
        db.rollback()
        logger.exception("Clinical summary generation failed for consultation %s", consultation_id)
        raise HTTPException(status_code=500, detail="Clinical summary generation failed.") from exc


@router.put("/consultations/{consultation_id}/speaker-roles", response_model=TranscriptOut)
def update_speaker_roles(
    consultation_id: str,
    payload: SpeakerRoleUpdateRequest,
    db: Session = Depends(get_db),
):
    _get_consultation_or_404(db, consultation_id)
    transcript = repo.get_transcript(db, consultation_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not available yet. Process audio first.")
    try:
        updated_segments = apply_speaker_roles(transcript.segments or [], payload.roles)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    transcript = repo.update_transcript_speaker_roles(db, transcript, updated_segments)
    return TranscriptOut(
        consultation_id=consultation_id, text=transcript.text, language=transcript.language,
        segments=transcript.segments or [], asr_mode=transcript.asr_mode,
        diarization_status=transcript.diarization_status or "not_run",
    )


@router.get("/consultations/{consultation_id}/clinical-data", response_model=ClinicalDataOut)
def get_clinical_data(consultation_id: str, db: Session = Depends(get_db)):
    _get_consultation_or_404(db, consultation_id)
    entities = repo.get_clinical_entities(db, consultation_id)

    def to_out(rows):
        return [ClinicalEntityOut.model_validate(r) for r in rows]

    return ClinicalDataOut(
        consultation_id=consultation_id,
        symptoms=to_out([e for e in entities if e.entity_type == "symptom"]),
        diagnoses=to_out([e for e in entities if e.entity_type == "diagnosis"]),
        medications=to_out([e for e in entities if e.entity_type == "medication"]),
        precautions=to_out([e for e in entities if e.entity_type == "precaution"]),
    )


# ---------- Recommendations: generate/re-generate + doctor edit ----------
@router.post("/consultations/{consultation_id}/recommendations", response_model=List[RecommendationOut])
def generate_or_regenerate_recommendations(consultation_id: str, db: Session = Depends(get_db)):
    _get_consultation_or_404(db, consultation_id)
    entities = repo.get_clinical_entities(db, consultation_id)
    if not entities:
        raise HTTPException(status_code=400, detail="No clinical data extracted yet. Call /process first.")
    entity_dicts = [{
        "entity_type": e.entity_type, "text": e.text, "normalized": e.normalized,
        "dosage": e.dosage, "frequency": e.frequency, "duration": e.duration, "route": e.route,
    } for e in entities]
    recs = generate_recommendations(entity_dicts)
    rows = repo.replace_recommendations(db, consultation_id, [
        {**r, "status": m.RecommendationStatus.AI_SUGGESTED.value} for r in recs
    ])
    consultation = repo.get_consultation(db, consultation_id)
    repo.set_consultation_status(db, consultation, m.ConsultationStatus.RECOMMENDATIONS_GENERATED.value)
    return rows


@router.get("/consultations/{consultation_id}/recommendations", response_model=List[RecommendationOut])
def list_recommendations(consultation_id: str, db: Session = Depends(get_db)):
    _get_consultation_or_404(db, consultation_id)
    return repo.get_recommendations(db, consultation_id)


@router.put("/consultations/{consultation_id}/recommendations", response_model=List[RecommendationOut])
def edit_recommendations(consultation_id: str, payload: RecommendationUpdateRequest, db: Session = Depends(get_db)):
    """Doctor review/edit endpoint: replaces the recommendation set with the
    doctor-edited version (state -> DOCTOR_EDITED / DOCTOR_REVIEW)."""
    consultation = _get_consultation_or_404(db, consultation_id)
    rows = repo.replace_recommendations(db, consultation_id, [
        {
            "medicine": item.medicine, "dosage": item.dosage, "frequency": item.frequency,
            "duration": item.duration, "route": item.route, "reason": item.reason,
            "score": 1.0, "status": m.RecommendationStatus.DOCTOR_EDITED.value, "doctor_edited": True,
        } for item in payload.items
    ])
    repo.set_consultation_status(db, consultation, m.ConsultationStatus.DOCTOR_REVIEW.value)
    return rows


# ---------- Approval ----------
@router.post("/consultations/{consultation_id}/approve", response_model=PrescriptionOut)
def approve_or_reject(consultation_id: str, payload: ApprovalRequest, db: Session = Depends(get_db)):
    consultation = _get_consultation_or_404(db, consultation_id)
    recommendations = repo.get_recommendations(db, consultation_id)
    if not recommendations:
        raise HTTPException(status_code=400, detail="No recommendations to approve/reject for this consultation")

    entities = repo.get_clinical_entities(db, consultation_id)
    entity_dicts = [{"entity_type": e.entity_type, "normalized": e.normalized} for e in entities]

    if payload.approved:
        rec_dicts = [{"medicine": r.medicine, "dosage": r.dosage, "frequency": r.frequency,
                      "duration": r.duration, "route": r.route, "reason": r.reason} for r in recommendations]
        items = build_prescription_items(rec_dicts)
        diagnosis_summary = payload.diagnosis_summary or summarize_diagnosis(entity_dicts)
        precautions = payload.precautions or default_precautions(entity_dicts)

        prescription = repo.create_or_update_prescription(
            db, consultation_id=consultation_id, patient_id=consultation.patient_id,
            doctor_id=payload.doctor_id, diagnosis_summary=diagnosis_summary, precautions=precautions,
            status="APPROVED", items=items, approved_by=payload.doctor_id,
            approved_at=__import__("datetime").datetime.utcnow(),
        )
        repo.set_consultation_status(db, consultation, m.ConsultationStatus.APPROVED.value)
    else:
        prescription = repo.create_or_update_prescription(
            db, consultation_id=consultation_id, patient_id=consultation.patient_id,
            doctor_id=payload.doctor_id,
            diagnosis_summary=payload.rejection_reason or "Rejected by doctor",
            precautions=[], status="REJECTED", items=[],
        )
        repo.set_consultation_status(db, consultation, m.ConsultationStatus.REJECTED.value)

    return prescription


# ---------- Prescription ----------
@router.get("/consultations/{consultation_id}/prescription", response_model=PrescriptionOut)
def get_prescription(consultation_id: str, db: Session = Depends(get_db)):
    _get_consultation_or_404(db, consultation_id)
    prescription = repo.get_prescription(db, consultation_id)
    if not prescription:
        raise HTTPException(status_code=404, detail="No prescription yet. Approve the consultation first.")
    return prescription


@router.get("/consultations/{consultation_id}/prescription/pdf")
def get_prescription_pdf(consultation_id: str, db: Session = Depends(get_db)):
    consultation = _get_consultation_or_404(db, consultation_id)
    prescription = repo.get_prescription(db, consultation_id)
    if not prescription or prescription.status != "APPROVED":
        raise HTTPException(status_code=400, detail="Only APPROVED prescriptions can generate a PDF")

    patient = repo.get_patient(db, consultation.patient_id)
    doctor = repo.get_doctor(db, prescription.doctor_id) if prescription.doctor_id else None

    pdf_dir = Path(settings.pdf_output_dir)
    pdf_path = pdf_dir / f"prescription_{prescription.id}.pdf"

    generate_prescription_pdf(
        output_path=str(pdf_path),
        doctor_name=doctor.name if doctor else "Doctor (not specified)",
        doctor_reg_no=doctor.registration_no if doctor else "N/A",
        patient_name=patient.name if patient else "Unknown",
        patient_age=patient.age if patient else None,
        patient_gender=patient.gender if patient else None,
        consultation_id=consultation_id,
        diagnosis_summary=prescription.diagnosis_summary or "",
        items=[{
            "medicine": it.medicine, "dosage": it.dosage, "frequency": it.frequency,
            "duration": it.duration, "route": it.route,
        } for it in prescription.items],
        precautions=prescription.precautions or [],
        approval_status=prescription.status,
    )
    repo.set_prescription_pdf_path(db, prescription, str(pdf_path))
    repo.set_consultation_status(db, consultation, m.ConsultationStatus.PRESCRIPTION_GENERATED.value)

    return FileResponse(str(pdf_path), media_type="application/pdf",
                         filename=f"prescription_{consultation_id}.pdf")
