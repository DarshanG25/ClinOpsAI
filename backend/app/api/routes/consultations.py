
"""Authenticated consultation, clinical-data, recommendation, and prescription routes."""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.models import domain as m
from app.repositories import repository as repo
from app.schemas.api_models import (
    ApprovalRequest,
    AudioUploadResponse,
    ClinicalDataOut,
    ClinicalEntityOut,
    ClinicalSummaryOut,
    ConsultationCreate,
    ConsultationOut,
    PrescriptionOut,
    ProcessResponse,
    RecommendationOut,
    RecommendationUpdateRequest,
    SpeakerRoleUpdateRequest,
    TranscriptOut,
)
from app.services.audio.audio_preprocessor import temporary_preprocessed_audio
from app.services.nlp import clinical_summary
from app.services.nlp.entity_extractor import extract_clinical_data
from app.services.pdf_generator.pdf_service import generate_prescription_pdf
from app.services.prescription.prescription_service import (
    build_prescription_items,
    default_precautions,
    summarize_diagnosis,
)
from app.services.recommendation.recommendation_service import (
    generate_recommendations,
)
from app.services.speech.speaker_diarization import (
    apply_speaker_roles,
    diarize_transcription,
)
from app.services.speech.whisper_service import transcribe_audio

logger = logging.getLogger("clinops.consultations")
router = APIRouter()

ALLOWED_AUDIO_EXT = {
    ".wav", ".mp3", ".m4a", ".mpeg", ".mpg", ".mp2", ".flac", ".ogg"
}


# ---------- Authentication and ownership helpers ----------

def _get_consultation_or_404(
    db: Session, consultation_id: str
) -> m.Consultation:
    consultation = repo.get_consultation(db, consultation_id)
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return consultation


def _get_authorized_consultation(
    db: Session,
    consultation_id: str,
    current_user: m.User,
) -> m.Consultation:
    """Ensure the consultation belongs to the authenticated user's linked record."""
    consultation = _get_consultation_or_404(db, consultation_id)

    if current_user.role == "doctor":
        if (
            not current_user.doctor_id
            or consultation.doctor_id != current_user.doctor_id
        ):
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this consultation.",
            )

    elif current_user.role == "patient":
        if (
            not current_user.patient_id
            or consultation.patient_id != current_user.patient_id
        ):
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this consultation.",
            )

    else:
        raise HTTPException(status_code=403, detail="Access denied.")

    return consultation


def _require_assigned_doctor(
    consultation: m.Consultation,
    current_user: m.User,
) -> None:
    """Require the doctor assigned to this consultation."""
    if current_user.role != "doctor":
        raise HTTPException(
            status_code=403,
            detail="Only the assigned doctor can perform this action.",
        )

    if (
        not current_user.doctor_id
        or consultation.doctor_id != current_user.doctor_id
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not the doctor assigned to this consultation.",
        )


def _get_readable_consultation(
    db: Session,
    consultation_id: str,
    current_user: m.User,
) -> m.Consultation:
    """Patients see clinical details only after the doctor has decided."""
    consultation = _get_authorized_consultation(
        db, consultation_id, current_user
    )

    if current_user.role == "patient" and consultation.status not in {
        m.ConsultationStatus.APPROVED.value,
        m.ConsultationStatus.REJECTED.value,
        m.ConsultationStatus.PRESCRIPTION_GENERATED.value,
    }:
        raise HTTPException(
            status_code=403,
            detail="Clinical details are not available until doctor review is complete.",
        )

    return consultation


def _patient_safe_consultation(
    consultation: m.Consultation,
) -> dict:
    """Retain the existing response shape without exposing internal fields."""
    return {
        "id": consultation.id,
        "patient_id": consultation.patient_id,
        "doctor_id": None,
        "status": consultation.status,
        "language": consultation.language,
        "audio_path": None,
        "notes": None,
        "error_message": None,
        "created_at": consultation.created_at,
        "updated_at": consultation.updated_at,
    }


def _require_linked_doctor(db: Session, current_user: m.User) -> str:
    """Return a valid linked doctor ID, or deny the operation."""
    if current_user.role != "doctor" or not current_user.doctor_id:
        raise HTTPException(
            status_code=403,
            detail="A linked doctor account is required.",
        )

    doctor = repo.get_doctor(db, current_user.doctor_id)
    if not doctor:
        raise HTTPException(
            status_code=403,
            detail="The linked doctor record does not exist.",
        )

    return doctor.id


# ---------- Create / read ----------

@router.post(
    "/consultations",
    response_model=ConsultationOut,
    status_code=201,
)
def create_consultation(
    payload: ConsultationCreate,
    db: Session = Depends(get_db),
    current_user: m.User = Depends(get_current_user),
):
    doctor_id = _require_linked_doctor(db, current_user)

    patient = repo.get_patient(db, payload.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Never trust a doctor ID supplied by the client.
    if payload.doctor_id and payload.doctor_id != doctor_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot create a consultation assigned to another doctor.",
        )

    return repo.create_consultation(
        db,
        patient_id=patient.id,
        doctor_id=doctor_id,
        language=payload.language,
        notes=payload.notes,
    )


@router.get("/consultations", response_model=List[ConsultationOut])
def list_consultations(
    db: Session = Depends(get_db),
    current_user: m.User = Depends(get_current_user),
):
    if current_user.role == "doctor":
        doctor_id = _require_linked_doctor(db, current_user)
        return (
            db.query(m.Consultation)
            .filter(m.Consultation.doctor_id == doctor_id)
            .order_by(m.Consultation.created_at.desc())
            .all()
        )

    if current_user.role == "patient":
        if not current_user.patient_id:
            raise HTTPException(
                status_code=403,
                detail="Patient account is not linked to a patient record.",
            )

        consultations = (
            db.query(m.Consultation)
            .filter(m.Consultation.patient_id == current_user.patient_id)
            .filter(
                m.Consultation.status.in_(
                    {
                        m.ConsultationStatus.APPROVED.value,
                        m.ConsultationStatus.PRESCRIPTION_GENERATED.value,
                    }
                )
            )
            .order_by(m.Consultation.created_at.desc())
            .all()
        )
        return [_patient_safe_consultation(item) for item in consultations]

    raise HTTPException(status_code=403, detail="Access denied.")


@router.get(
    "/consultations/{consultation_id}",
    response_model=ConsultationOut,
)
def get_consultation(
    consultation_id: str,
    db: Session = Depends(get_db),
    current_user: m.User = Depends(get_current_user),
):
    consultation = _get_authorized_consultation(
        db, consultation_id, current_user
    )
    if current_user.role == "patient":
        if consultation.status not in {
            m.ConsultationStatus.APPROVED.value,
            m.ConsultationStatus.PRESCRIPTION_GENERATED.value,
        }:
            raise HTTPException(
                status_code=404,
                detail="Consultation not found.",
            )
        return _patient_safe_consultation(consultation)
    return consultation


# ---------- Audio upload ----------

@router.post(
    "/consultations/{consultation_id}/audio",
    response_model=AudioUploadResponse,
)
async def upload_audio(
    consultation_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: m.User = Depends(get_current_user),
):
    consultation = _get_authorized_consultation(
        db, consultation_id, current_user
    )
    _require_assigned_doctor(consultation, current_user)

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_AUDIO_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format '{ext}'. Allowed: {sorted(ALLOWED_AUDIO_EXT)}",
        )

    upload_dir = Path(settings.upload_dir)
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error(
            "Audio storage is unavailable for consultation %s (%s)",
            consultation_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Audio storage is unavailable.",
        ) from exc
    dest = upload_dir / f"{consultation_id}_{uuid.uuid4().hex[:8]}{ext}"
    uploaded_size = 0

    try:
        with dest.open("wb") as saved_audio:
            while chunk := await file.read(1024 * 1024):
                uploaded_size += len(chunk)
                if uploaded_size > settings.max_audio_size:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "Audio file exceeds MAX_AUDIO_SIZE "
                            f"({settings.max_audio_size} bytes)"
                        ),
                    )
                saved_audio.write(chunk)

        if uploaded_size == 0:
            raise HTTPException(
                status_code=400,
                detail="Uploaded audio file is empty",
            )
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    except OSError as exc:
        dest.unlink(missing_ok=True)
        logger.error(
            "Audio upload failed for consultation %s (%s)",
            consultation_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Audio upload failed.",
        ) from exc
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    try:
        repo.set_audio_path(db, consultation, str(dest))
    except SQLAlchemyError as exc:
        dest.unlink(missing_ok=True)
        logger.error(
            "Audio metadata save failed for consultation %s (%s)",
            consultation_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Audio upload could not be saved.",
        ) from exc

    return AudioUploadResponse(
        consultation_id=consultation_id,
        status=consultation.status,
        audio_path=dest.name,
        message="Audio uploaded. Call /process to run ASR + clinical extraction.",
    )


# ---------- Process: ASR -> summary -> extraction -> recommendations ----------

@router.post(
    "/consultations/{consultation_id}/process",
    response_model=ProcessResponse,
)
def process_consultation(
    consultation_id: str,
    db: Session = Depends(get_db),
    current_user: m.User = Depends(get_current_user),
):
    consultation = _get_authorized_consultation(
        db, consultation_id, current_user
    )
    _require_assigned_doctor(consultation, current_user)

    if not consultation.audio_path:
        raise HTTPException(
            status_code=400,
            detail="No audio uploaded for this consultation yet",
        )

    repo.set_consultation_status(
        db, consultation, m.ConsultationStatus.PROCESSING.value
    )

    try:
        with temporary_preprocessed_audio(
            consultation.audio_path
        ) as processed_audio_path:
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
    except Exception as exc:
        logger.error(
            "Audio processing failed for consultation %s (%s)",
            consultation_id,
            type(exc).__name__,
        )
        repo.set_consultation_status(
            db,
            consultation,
            m.ConsultationStatus.FAILED.value,
            error_message="Audio preprocessing or processing failed.",
        )
        raise HTTPException(
            status_code=500,
            detail="Audio preprocessing or processing failed.",
        ) from exc

    repo.upsert_transcript(
        db,
        consultation_id,
        text=asr_result["transcript"],
        language=asr_result["language"],
        segments=segments,
        asr_mode=asr_result["asr_mode"],
        diarization_status=diarization_status,
    )
    repo.set_consultation_status(
        db, consultation, m.ConsultationStatus.TRANSCRIBED.value
    )
    repo.delete_clinical_summary(db, consultation_id)

    summary_status = "failed"
    extraction_text = asr_result["transcript"]

    try:
        summary_result = clinical_summary.generate_clinical_summary(segments)
        repo.upsert_clinical_summary(
            db,
            consultation_id,
            summary_text=summary_result["summary_text"],
            segment_scores=summary_result["segment_scores"],
            relevant_segments=summary_result["relevant_segments"],
            source_segment_ids=summary_result["source_segment_ids"],
            status=summary_result["status"],
            method=summary_result["method"],
            version=summary_result["version"],
        )
        summary_status = summary_result["status"]
    except Exception as exc:
        db.rollback()
        logger.error(
            "Clinical summary generation failed for consultation %s (%s)",
            consultation_id,
            type(exc).__name__,
        )

    # Extract from the full transcript, not just the condensed summary.
    entities = extract_clinical_data(extraction_text)
    repo.replace_clinical_entities(db, consultation_id, entities)

    status_after_extraction = (
        m.ConsultationStatus.CLINICAL_EXTRACTED.value
        if entities
        else m.ConsultationStatus.TRANSCRIBED.value
    )
    repo.set_consultation_status(
        db, consultation, status_after_extraction
    )

    if entities:
        recs = generate_recommendations(entities)
        repo.replace_recommendations(
            db,
            consultation_id,
            [
                {
                    **recommendation,
                    "status": m.RecommendationStatus.AI_SUGGESTED.value,
                }
                for recommendation in recs
            ],
        )
        if recs:
            repo.set_consultation_status(
                db,
                consultation,
                m.ConsultationStatus.RECOMMENDATIONS_GENERATED.value,
            )

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

@router.get(
    "/consultations/{consultation_id}/transcript",
    response_model=TranscriptOut,
)
def get_transcript(
    consultation_id: str,
    db: Session = Depends(get_db),
    current_user: m.User = Depends(get_current_user),
):
    consultation = _get_readable_consultation(
        db, consultation_id, current_user
    )
    _require_assigned_doctor(consultation, current_user)
    transcript = repo.get_transcript(db, consultation_id)

    if not transcript:
        raise HTTPException(
            status_code=404,
            detail="Transcript not available yet. Call /process first.",
        )

    return TranscriptOut(
        consultation_id=consultation_id,
        text=transcript.text,
        language=transcript.language,
        segments=transcript.segments or [],
        asr_mode=transcript.asr_mode,
        diarization_status=transcript.diarization_status or "not_run",
    )


@router.get(
    "/consultations/{consultation_id}/clinical-summary",
    response_model=ClinicalSummaryOut,
)
def get_clinical_summary(
    consultation_id: str,
    db: Session = Depends(get_db),
    current_user: m.User = Depends(get_current_user),
):
    consultation = _get_readable_consultation(
        db, consultation_id, current_user
    )
    _require_assigned_doctor(consultation, current_user)
    summary = repo.get_clinical_summary(db, consultation_id)

    if not summary:
        raise HTTPException(
            status_code=404,
            detail="Clinical summary not available. Generate it after transcription.",
        )

    return summary


@router.post(
    "/consultations/{consultation_id}/clinical-summary/generate",
    response_model=ClinicalSummaryOut,
)
def generate_consultation_clinical_summary(
    consultation_id: str,
    db: Session = Depends(get_db),
    current_user: m.User = Depends(get_current_user),
):
    consultation = _get_authorized_consultation(
        db, consultation_id, current_user
    )
    _require_assigned_doctor(consultation, current_user)

    transcript = repo.get_transcript(db, consultation_id)
    if not transcript:
        raise HTTPException(
            status_code=404,
            detail="Transcript not available yet. Process audio first.",
        )

    try:
        result = clinical_summary.generate_clinical_summary(
            transcript.segments or []
        )
        return repo.upsert_clinical_summary(
            db,
            consultation_id,
            summary_text=result["summary_text"],
            segment_scores=result["segment_scores"],
            relevant_segments=result["relevant_segments"],
            source_segment_ids=result["source_segment_ids"],
            status=result["status"],
            method=result["method"],
            version=result["version"],
        )
    except Exception as exc:
        db.rollback()
        logger.error(
            "Clinical summary generation failed for consultation %s (%s)",
            consultation_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Clinical summary generation failed.",
        ) from exc


@router.put(
    "/consultations/{consultation_id}/speaker-roles",
    response_model=TranscriptOut,
)
def update_speaker_roles(
    consultation_id: str,
    payload: SpeakerRoleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: m.User = Depends(get_current_user),
):
    consultation = _get_authorized_consultation(
        db, consultation_id, current_user
    )
    _require_assigned_doctor(consultation, current_user)

    transcript = repo.get_transcript(db, consultation_id)
    if not transcript:
        raise HTTPException(
            status_code=404,
            detail="Transcript not available yet. Process audio first.",
        )

    try:
        updated_segments = apply_speaker_roles(
            transcript.segments or [], payload.roles
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    transcript = repo.update_transcript_speaker_roles(
        db, transcript, updated_segments
    )

    return TranscriptOut(
        consultation_id=consultation_id,
        text=transcript.text,
        language=transcript.language,
        segments=transcript.segments or [],
        asr_mode=transcript.asr_mode,
        diarization_status=transcript.diarization_status or "not_run",
    )


@router.get(
    "/consultations/{consultation_id}/clinical-data",
    response_model=ClinicalDataOut,
)
def get_clinical_data(
    consultation_id: str,
    db: Session = Depends(get_db),
    current_user: m.User = Depends(get_current_user),
):
    consultation = _get_readable_consultation(
        db, consultation_id, current_user
    )
    _require_assigned_doctor(consultation, current_user)
    entities = repo.get_clinical_entities(db, consultation_id)

    def to_out(rows):
        return [ClinicalEntityOut.model_validate(row) for row in rows]

    return ClinicalDataOut(
        consultation_id=consultation_id,
        symptoms=to_out(
            [e for e in entities if e.entity_type == "symptom"]
        ),
        diagnoses=to_out(
            [e for e in entities if e.entity_type == "diagnosis"]
        ),
        medications=to_out(
            [e for e in entities if e.entity_type == "medication"]
        ),
        precautions=to_out(
            [e for e in entities if e.entity_type == "precaution"]
        ),
    )


# ---------- Recommendations ----------

@router.post(
    "/consultations/{consultation_id}/recommendations",
    response_model=List[RecommendationOut],
)
def generate_or_regenerate_recommendations(
    consultation_id: str,
    db: Session = Depends(get_db),
    current_user: m.User = Depends(get_current_user),
):
    consultation = _get_authorized_consultation(
        db, consultation_id, current_user
    )
    _require_assigned_doctor(consultation, current_user)

    entities = repo.get_clinical_entities(db, consultation_id)
    if not entities:
        raise HTTPException(
            status_code=400,
            detail="No clinical data extracted yet. Call /process first.",
        )

    entity_dicts = [
        {
            "entity_type": e.entity_type,
            "text": e.text,
            "normalized": e.normalized,
            "dosage": e.dosage,
            "frequency": e.frequency,
            "duration": e.duration,
            "route": e.route,
        }
        for e in entities
    ]

    recommendations = generate_recommendations(entity_dicts)
    rows = repo.replace_recommendations(
        db,
        consultation_id,
        [
            {
                **recommendation,
                "status": m.RecommendationStatus.AI_SUGGESTED.value,
            }
            for recommendation in recommendations
        ],
    )

    repo.set_consultation_status(
        db,
        consultation,
        m.ConsultationStatus.RECOMMENDATIONS_GENERATED.value,
    )
    return rows


@router.get(
    "/consultations/{consultation_id}/recommendations",
    response_model=List[RecommendationOut],
)
def list_recommendations(
    consultation_id: str,
    db: Session = Depends(get_db),
    current_user: m.User = Depends(get_current_user),
):
    consultation = _get_readable_consultation(
        db, consultation_id, current_user
    )
    _require_assigned_doctor(consultation, current_user)
    return repo.get_recommendations(db, consultation_id)


@router.put(
    "/consultations/{consultation_id}/recommendations",
    response_model=List[RecommendationOut],
)
def edit_recommendations(
    consultation_id: str,
    payload: RecommendationUpdateRequest,
    db: Session = Depends(get_db),
    current_user: m.User = Depends(get_current_user),
):
    consultation = _get_authorized_consultation(
        db, consultation_id, current_user
    )
    _require_assigned_doctor(consultation, current_user)

    rows = repo.replace_recommendations(
        db,
        consultation_id,
        [
            {
                "medicine": item.medicine,
                "dosage": item.dosage,
                "frequency": item.frequency,
                "duration": item.duration,
                "route": item.route,
                "reason": item.reason,
                "score": 1.0,
                "status": m.RecommendationStatus.DOCTOR_EDITED.value,
                "doctor_edited": True,
            }
            for item in payload.items
        ],
    )

    repo.set_consultation_status(
        db, consultation, m.ConsultationStatus.DOCTOR_REVIEW.value
    )
    return rows


# ---------- Approval ----------

@router.post(
    "/consultations/{consultation_id}/approve",
    response_model=PrescriptionOut,
)
def approve_or_reject(
    consultation_id: str,
    payload: ApprovalRequest,
    db: Session = Depends(get_db),
    current_user: m.User = Depends(get_current_user),
):
    consultation = _get_authorized_consultation(
        db, consultation_id, current_user
    )
    _require_assigned_doctor(consultation, current_user)
    doctor_id = _require_linked_doctor(db, current_user)
    if payload.doctor_id != doctor_id:
        raise HTTPException(
            status_code=403,
            detail="The approval doctor must match the authenticated account.",
        )

    recommendations = repo.get_recommendations(db, consultation_id)
    if not recommendations:
        raise HTTPException(
            status_code=400,
            detail="No recommendations to approve/reject for this consultation",
        )

    entities = repo.get_clinical_entities(db, consultation_id)
    entity_dicts = [
        {"entity_type": e.entity_type, "normalized": e.normalized}
        for e in entities
    ]

    if payload.approved:
        rec_dicts = [
            {
                "medicine": r.medicine,
                "dosage": r.dosage,
                "frequency": r.frequency,
                "duration": r.duration,
                "route": r.route,
                "reason": r.reason,
            }
            for r in recommendations
        ]
        items = build_prescription_items(rec_dicts)
        diagnosis_summary = (
            payload.diagnosis_summary or summarize_diagnosis(entity_dicts)
        )
        precautions = payload.precautions or default_precautions(entity_dicts)

        prescription = repo.create_or_update_prescription(
            db,
            consultation_id=consultation_id,
            patient_id=consultation.patient_id,
            doctor_id=doctor_id,
            diagnosis_summary=diagnosis_summary,
            precautions=precautions,
            status="APPROVED",
            items=items,
            approved_by=doctor_id,
            approved_at=datetime.utcnow(),
        )

        repo.set_consultation_status(
            db, consultation, m.ConsultationStatus.APPROVED.value
        )
    else:
        prescription = repo.create_or_update_prescription(
            db,
            consultation_id=consultation_id,
            patient_id=consultation.patient_id,
            doctor_id=doctor_id,
            diagnosis_summary=payload.rejection_reason or "Rejected by doctor",
            precautions=[],
            status="REJECTED",
            items=[],
        )

        repo.set_consultation_status(
            db, consultation, m.ConsultationStatus.REJECTED.value
        )

    return prescription


# ---------- Prescription ----------

@router.get(
    "/consultations/{consultation_id}/prescription",
    response_model=PrescriptionOut,
)
def get_prescription(
    consultation_id: str,
    db: Session = Depends(get_db),
    current_user: m.User = Depends(get_current_user),
):
    _get_readable_consultation(db, consultation_id, current_user)
    prescription = repo.get_prescription(db, consultation_id)

    if not prescription:
        raise HTTPException(
            status_code=404,
            detail="No prescription yet. Doctor review may still be pending.",
        )

    # Do not expose draft prescriptions to patient accounts.
    if (
        current_user.role == "patient"
        and prescription.status != "APPROVED"
    ):
        raise HTTPException(
            status_code=403,
            detail="This prescription is not approved for patient access.",
        )

    if current_user.role == "patient":
        return PrescriptionOut.model_validate(prescription).model_copy(
            update={
                "doctor_id": None,
                "approved_by": None,
                "pdf_path": None,
            }
        )

    return prescription


@router.get("/consultations/{consultation_id}/prescription/pdf")
def get_prescription_pdf(
    consultation_id: str,
    db: Session = Depends(get_db),
    current_user: m.User = Depends(get_current_user),
):
    consultation = _get_readable_consultation(
        db, consultation_id, current_user
    )
    _require_assigned_doctor(consultation, current_user)
    prescription = repo.get_prescription(db, consultation_id)

    if not prescription or prescription.status != "APPROVED":
        raise HTTPException(
            status_code=400,
            detail="Only APPROVED prescriptions can generate a PDF",
        )

    patient = repo.get_patient(db, consultation.patient_id)
    doctor = (
        repo.get_doctor(db, prescription.doctor_id)
        if prescription.doctor_id
        else None
    )

    pdf_dir = Path(settings.pdf_output_dir)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"prescription_{prescription.id}.pdf"

    try:
        generate_prescription_pdf(
            output_path=str(pdf_path),
            doctor_name=doctor.name if doctor else "Doctor (not specified)",
            doctor_reg_no=doctor.registration_no if doctor else "N/A",
            patient_name=patient.name if patient else "Unknown",
            patient_age=patient.age if patient else None,
            patient_gender=patient.gender if patient else None,
            consultation_id=consultation.id,
            diagnosis_summary=prescription.diagnosis_summary or "",
            items=[
                {
                    "medicine": item.medicine,
                    "dosage": item.dosage,
                    "frequency": item.frequency,
                    "duration": item.duration,
                    "route": item.route,
                }
                for item in prescription.items
            ],
            precautions=prescription.precautions or [],
            approval_status=prescription.status,
        )
    except Exception as exc:
        logger.error(
            "Prescription PDF generation failed for consultation %s (%s)",
            consultation_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Prescription PDF generation failed.",
        ) from exc

    repo.set_prescription_pdf_path(db, prescription, str(pdf_path))
    repo.set_consultation_status(
        db,
        consultation,
        m.ConsultationStatus.PRESCRIPTION_GENERATED.value,
    )

    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename=f"prescription_{consultation.id}.pdf",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )