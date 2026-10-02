"""Pydantic request/response schemas for the REST API."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


# ---------- Patient ----------
class PatientCreate(BaseModel):
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    language: str = "en"
    contact: Optional[str] = None


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    language: str
    contact: Optional[str] = None
    created_at: datetime


# ---------- Consultation ----------
class ConsultationCreate(BaseModel):
    patient_id: str
    doctor_id: Optional[str] = None
    language: str = "en"
    notes: Optional[str] = None


class ConsultationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    patient_id: str
    doctor_id: Optional[str] = None
    status: str
    language: str
    audio_path: Optional[str] = None
    notes: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AudioUploadResponse(BaseModel):
    consultation_id: str
    status: str
    audio_path: str
    message: str


class ProcessResponse(BaseModel):
    consultation_id: str
    status: str
    language: str
    transcript: str
    segments: List[dict]
    asr_mode: str
    diarization_status: str = "not_run"


# ---------- Transcript / Clinical ----------
class TranscriptOut(BaseModel):
    consultation_id: str
    text: str
    language: str
    segments: List[dict]
    asr_mode: str
    diarization_status: str = "not_run"


class SpeakerRoleUpdateRequest(BaseModel):
    roles: dict[str, str]


class ClinicalEntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entity_type: str
    text: str
    normalized: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    route: Optional[str] = None
    confidence: float


class ClinicalDataOut(BaseModel):
    consultation_id: str
    symptoms: List[ClinicalEntityOut]
    diagnoses: List[ClinicalEntityOut]
    medications: List[ClinicalEntityOut]
    precautions: List[ClinicalEntityOut]


# ---------- Recommendation ----------
class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    medicine: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    route: Optional[str] = None
    score: float = Field(description="Recommendation Relevance Score (0-1). NOT a medical probability.")
    reason: Optional[str] = None
    status: str
    doctor_edited: bool = False


class RecommendationEditItem(BaseModel):
    id: Optional[str] = None  # existing recommendation id to edit; omit to add a new one
    medicine: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    route: Optional[str] = None
    reason: Optional[str] = None


class RecommendationUpdateRequest(BaseModel):
    """Doctor review/edit payload. Replaces the recommendation set for a consultation."""
    items: List[RecommendationEditItem]


# ---------- Approval / Prescription ----------
class ApprovalRequest(BaseModel):
    doctor_id: str
    approved: bool = True
    diagnosis_summary: Optional[str] = None
    precautions: List[str] = Field(default_factory=list)
    rejection_reason: Optional[str] = None


class PrescriptionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    medicine: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    route: Optional[str] = None
    instructions: Optional[str] = None


class PrescriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    consultation_id: str
    patient_id: str
    doctor_id: Optional[str] = None
    diagnosis_summary: Optional[str] = None
    precautions: List[str] = Field(default_factory=list)
    status: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    pdf_path: Optional[str] = None
    items: List[PrescriptionItemOut]
    created_at: datetime
