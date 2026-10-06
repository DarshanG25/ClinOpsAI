"""SQLAlchemy ORM models for ClinOps-AI.

Entities: Doctor, Patient, Consultation, Transcript, ClinicalSummary, ClinicalEntity,
Recommendation, Prescription, PrescriptionItem.

Consultation.status follows the state machine from the project brief:
CREATED -> AUDIO_UPLOADED -> PROCESSING -> TRANSCRIBED -> CLINICAL_EXTRACTED
-> RECOMMENDATIONS_GENERATED -> DOCTOR_REVIEW -> APPROVED/REJECTED
-> PRESCRIPTION_GENERATED
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, ForeignKey, Enum, JSON, Boolean
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class ConsultationStatus(str, enum.Enum):
    CREATED = "CREATED"
    AUDIO_UPLOADED = "AUDIO_UPLOADED"
    PROCESSING = "PROCESSING"
    TRANSCRIBED = "TRANSCRIBED"
    CLINICAL_EXTRACTED = "CLINICAL_EXTRACTED"
    RECOMMENDATIONS_GENERATED = "RECOMMENDATIONS_GENERATED"
    DOCTOR_REVIEW = "DOCTOR_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PRESCRIPTION_GENERATED = "PRESCRIPTION_GENERATED"
    FAILED = "FAILED"


class RecommendationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    AI_SUGGESTED = "AI_SUGGESTED"
    DOCTOR_EDITED = "DOCTOR_EDITED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    specialization = Column(String, default="General Medicine")
    registration_no = Column(String, default="DEMO-REG-0001")
    created_at = Column(DateTime, default=datetime.utcnow)

    consultations = relationship("Consultation", back_populates="doctor")


class Patient(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    language = Column(String, default="en")
    contact = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    consultations = relationship("Consultation", back_populates="patient")


class Consultation(Base):
    __tablename__ = "consultations"

    id = Column(String, primary_key=True, default=gen_id)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=True)
    status = Column(String, default=ConsultationStatus.CREATED.value)
    language = Column(String, default="en")
    audio_path = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship("Patient", back_populates="consultations")
    doctor = relationship("Doctor", back_populates="consultations")
    transcript = relationship("Transcript", back_populates="consultation", uselist=False)
    clinical_summary = relationship(
        "ClinicalSummary", back_populates="consultation", uselist=False,
        cascade="all, delete-orphan",
    )
    clinical_entities = relationship("ClinicalEntity", back_populates="consultation")
    recommendations = relationship("Recommendation", back_populates="consultation")
    prescription = relationship("Prescription", back_populates="consultation", uselist=False)


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(String, primary_key=True, default=gen_id)
    consultation_id = Column(String, ForeignKey("consultations.id"), nullable=False, unique=True)
    text = Column(Text, nullable=False)
    language = Column(String, default="en")
    segments = Column(JSON, default=list)  # [{start, end, text}]
    asr_mode = Column(String, default="demo")  # whisper | demo
    diarization_status = Column(String, default="not_run")
    created_at = Column(DateTime, default=datetime.utcnow)

    consultation = relationship("Consultation", back_populates="transcript")


class ClinicalSummary(Base):
    """Derived, source-linked clinical condensation; never replaces Transcript."""
    __tablename__ = "clinical_summaries"

    id = Column(String, primary_key=True, default=gen_id)
    consultation_id = Column(String, ForeignKey("consultations.id"), nullable=False, unique=True)
    summary_text = Column(Text, nullable=False, default="")
    segment_scores = Column(JSON, nullable=False, default=list)
    relevant_segments = Column(JSON, nullable=False, default=list)
    source_segment_ids = Column(JSON, nullable=False, default=list)
    status = Column(String, nullable=False, default="generated")
    method = Column(String, nullable=False)
    version = Column(String, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    consultation = relationship("Consultation", back_populates="clinical_summary")


class ClinicalEntity(Base):
    """One structured clinical fact extracted from the transcript.

    entity_type in {symptom, diagnosis, medication, precaution}.
    For medication rows, dosage/frequency/duration/route are populated.
    """
    __tablename__ = "clinical_entities"

    id = Column(String, primary_key=True, default=gen_id)
    consultation_id = Column(String, ForeignKey("consultations.id"), nullable=False)
    entity_type = Column(String, nullable=False)
    text = Column(String, nullable=False)
    normalized = Column(String, nullable=True)
    dosage = Column(String, nullable=True)
    frequency = Column(String, nullable=True)
    duration = Column(String, nullable=True)
    route = Column(String, nullable=True)
    confidence = Column(Float, default=0.6)
    created_at = Column(DateTime, default=datetime.utcnow)

    consultation = relationship("Consultation", back_populates="clinical_entities")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(String, primary_key=True, default=gen_id)
    consultation_id = Column(String, ForeignKey("consultations.id"), nullable=False)
    medicine = Column(String, nullable=False)
    dosage = Column(String, nullable=True)
    frequency = Column(String, nullable=True)
    duration = Column(String, nullable=True)
    route = Column(String, nullable=True)
    score = Column(Float, default=0.0)  # "Recommendation Relevance Score", NOT a medical probability
    reason = Column(Text, nullable=True)
    status = Column(String, default=RecommendationStatus.AI_SUGGESTED.value)
    doctor_edited = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    consultation = relationship("Consultation", back_populates="recommendations")


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(String, primary_key=True, default=gen_id)
    consultation_id = Column(String, ForeignKey("consultations.id"), nullable=False, unique=True)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=True)
    diagnosis_summary = Column(Text, nullable=True)
    precautions = Column(JSON, default=list)
    status = Column(String, default="DRAFT")  # DRAFT | APPROVED | REJECTED
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    pdf_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    consultation = relationship("Consultation", back_populates="prescription")
    items = relationship("PrescriptionItem", back_populates="prescription", cascade="all, delete-orphan")


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"

    id = Column(String, primary_key=True, default=gen_id)
    prescription_id = Column(String, ForeignKey("prescriptions.id"), nullable=False)
    medicine = Column(String, nullable=False)
    dosage = Column(String, nullable=True)
    frequency = Column(String, nullable=True)
    duration = Column(String, nullable=True)
    route = Column(String, nullable=True)
    instructions = Column(String, nullable=True)

    prescription = relationship("Prescription", back_populates="items")
