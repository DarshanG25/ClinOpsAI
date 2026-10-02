"""Data-access layer. Thin CRUD wrappers around SQLAlchemy sessions so the
API/service layers never construct raw queries themselves.
"""
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models import domain as m


# ---------- Patient ----------
def create_patient(db: Session, *, name: str, age=None, gender=None, language="en", contact=None) -> m.Patient:
    patient = m.Patient(name=name, age=age, gender=gender, language=language, contact=contact)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def get_patient(db: Session, patient_id: str) -> Optional[m.Patient]:
    return db.query(m.Patient).filter(m.Patient.id == patient_id).first()


def list_patients(db: Session) -> List[m.Patient]:
    return db.query(m.Patient).order_by(m.Patient.created_at.desc()).all()


# ---------- Doctor ----------
def get_or_create_default_doctor(db: Session) -> m.Doctor:
    doctor = db.query(m.Doctor).first()
    if doctor:
        return doctor
    doctor = m.Doctor(name="Dr. Demo Doctor", specialization="General Medicine")
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


def get_doctor(db: Session, doctor_id: str) -> Optional[m.Doctor]:
    return db.query(m.Doctor).filter(m.Doctor.id == doctor_id).first()


# ---------- Consultation ----------
def create_consultation(db: Session, *, patient_id: str, doctor_id=None, language="en", notes=None) -> m.Consultation:
    consultation = m.Consultation(
        patient_id=patient_id,
        doctor_id=doctor_id,
        language=language,
        notes=notes,
        status=m.ConsultationStatus.CREATED.value,
    )
    db.add(consultation)
    db.commit()
    db.refresh(consultation)
    return consultation


def get_consultation(db: Session, consultation_id: str) -> Optional[m.Consultation]:
    return db.query(m.Consultation).filter(m.Consultation.id == consultation_id).first()


def list_consultations(db: Session) -> List[m.Consultation]:
    return db.query(m.Consultation).order_by(m.Consultation.created_at.desc()).all()


def set_consultation_status(db: Session, consultation: m.Consultation, status: str, error_message: str = None):
    consultation.status = status
    consultation.error_message = error_message
    db.commit()
    db.refresh(consultation)
    return consultation


def set_audio_path(db: Session, consultation: m.Consultation, path: str):
    consultation.audio_path = path
    consultation.status = m.ConsultationStatus.AUDIO_UPLOADED.value
    db.commit()
    db.refresh(consultation)
    return consultation


# ---------- Transcript ----------
def upsert_transcript(
    db: Session, consultation_id: str, *, text: str, language: str,
    segments: list, asr_mode: str, diarization_status: str = "not_run",
) -> m.Transcript:
    transcript = db.query(m.Transcript).filter(m.Transcript.consultation_id == consultation_id).first()
    if transcript is None:
        transcript = m.Transcript(
            consultation_id=consultation_id, text=text, language=language,
            segments=segments, asr_mode=asr_mode,
            diarization_status=diarization_status,
        )
        db.add(transcript)
    else:
        transcript.text = text
        transcript.language = language
        transcript.segments = segments
        transcript.asr_mode = asr_mode
        transcript.diarization_status = diarization_status
    db.commit()
    db.refresh(transcript)
    return transcript


def get_transcript(db: Session, consultation_id: str) -> Optional[m.Transcript]:
    return db.query(m.Transcript).filter(m.Transcript.consultation_id == consultation_id).first()


def update_transcript_speaker_roles(db: Session, transcript: m.Transcript, segments: list) -> m.Transcript:
    transcript.segments = segments
    db.commit()
    db.refresh(transcript)
    return transcript


# ---------- Clinical entities ----------
def replace_clinical_entities(db: Session, consultation_id: str, entities: List[dict]) -> List[m.ClinicalEntity]:
    db.query(m.ClinicalEntity).filter(m.ClinicalEntity.consultation_id == consultation_id).delete()
    rows = []
    for e in entities:
        row = m.ClinicalEntity(consultation_id=consultation_id, **e)
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def get_clinical_entities(db: Session, consultation_id: str) -> List[m.ClinicalEntity]:
    return db.query(m.ClinicalEntity).filter(m.ClinicalEntity.consultation_id == consultation_id).all()


# ---------- Recommendations ----------
def replace_recommendations(db: Session, consultation_id: str, recs: List[dict]) -> List[m.Recommendation]:
    db.query(m.Recommendation).filter(m.Recommendation.consultation_id == consultation_id).delete()
    rows = []
    for r in recs:
        row = m.Recommendation(consultation_id=consultation_id, **r)
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def get_recommendations(db: Session, consultation_id: str) -> List[m.Recommendation]:
    return db.query(m.Recommendation).filter(m.Recommendation.consultation_id == consultation_id).all()


# ---------- Prescription ----------
def create_or_update_prescription(db: Session, *, consultation_id: str, patient_id: str, doctor_id: str,
                                   diagnosis_summary: str, precautions: list, status: str,
                                   items: List[dict], approved_by: str = None, approved_at=None) -> m.Prescription:
    prescription = db.query(m.Prescription).filter(m.Prescription.consultation_id == consultation_id).first()
    if prescription is None:
        prescription = m.Prescription(
            consultation_id=consultation_id, patient_id=patient_id, doctor_id=doctor_id,
            diagnosis_summary=diagnosis_summary, precautions=precautions, status=status,
            approved_by=approved_by, approved_at=approved_at,
        )
        db.add(prescription)
        db.flush()
    else:
        prescription.diagnosis_summary = diagnosis_summary
        prescription.precautions = precautions
        prescription.status = status
        prescription.approved_by = approved_by
        prescription.approved_at = approved_at
        db.query(m.PrescriptionItem).filter(m.PrescriptionItem.prescription_id == prescription.id).delete()

    for it in items:
        db.add(m.PrescriptionItem(prescription_id=prescription.id, **it))

    db.commit()
    db.refresh(prescription)
    return prescription


def get_prescription(db: Session, consultation_id: str) -> Optional[m.Prescription]:
    return db.query(m.Prescription).filter(m.Prescription.consultation_id == consultation_id).first()


def set_prescription_pdf_path(db: Session, prescription: m.Prescription, path: str):
    prescription.pdf_path = path
    db.commit()
    db.refresh(prescription)
    return prescription
