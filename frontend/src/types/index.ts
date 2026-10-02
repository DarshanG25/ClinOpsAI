// Types mirror the backend Pydantic schemas (see backend/app/schemas/api_models.py)

export type ConsultationStatus =
  | 'CREATED'
  | 'AUDIO_UPLOADED'
  | 'PROCESSING'
  | 'TRANSCRIBED'
  | 'CLINICAL_EXTRACTED'
  | 'RECOMMENDATIONS_GENERATED'
  | 'DOCTOR_REVIEW'
  | 'APPROVED'
  | 'REJECTED'
  | 'PRESCRIPTION_GENERATED'
  | 'FAILED';

export interface Patient {
  id: string;
  name: string;
  age?: number | null;
  gender?: string | null;
  language: string;
  contact?: string | null;
  created_at: string;
}

export interface Consultation {
  id: string;
  patient_id: string;
  doctor_id?: string | null;
  status: ConsultationStatus;
  language: string;
  audio_path?: string | null;
  notes?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
  speaker_id?: string | null;
  speaker_role?: string | null;
  confidence?: number | null;
  diarization_status?: string;
}

export interface Transcript {
  consultation_id: string;
  text: string;
  language: string;
  segments: TranscriptSegment[];
  asr_mode: 'whisper' | 'demo';
  diarization_status?: string;
}

export interface ClinicalEntity {
  id: string;
  entity_type: 'symptom' | 'diagnosis' | 'medication' | 'precaution';
  text: string;
  normalized?: string | null;
  dosage?: string | null;
  frequency?: string | null;
  duration?: string | null;
  route?: string | null;
  confidence: number;
}

export interface ClinicalData {
  consultation_id: string;
  symptoms: ClinicalEntity[];
  diagnoses: ClinicalEntity[];
  medications: ClinicalEntity[];
  precautions: ClinicalEntity[];
}

export interface Recommendation {
  id: string;
  medicine: string;
  dosage?: string | null;
  frequency?: string | null;
  duration?: string | null;
  route?: string | null;
  score: number; // "Recommendation Relevance Score" — NOT a medical probability
  reason?: string | null;
  status: 'AI_SUGGESTED' | 'DOCTOR_EDITED' | 'APPROVED' | 'REJECTED' | 'DRAFT';
  doctor_edited: boolean;
}

export interface PrescriptionItem {
  medicine: string;
  dosage?: string | null;
  frequency?: string | null;
  duration?: string | null;
  route?: string | null;
  instructions?: string | null;
}

export interface Prescription {
  id: string;
  consultation_id: string;
  patient_id: string;
  doctor_id?: string | null;
  diagnosis_summary?: string | null;
  precautions: string[];
  status: 'DRAFT' | 'APPROVED' | 'REJECTED';
  approved_by?: string | null;
  approved_at?: string | null;
  pdf_path?: string | null;
  items: PrescriptionItem[];
  created_at: string;
}

export interface ProcessResponse {
  consultation_id: string;
  status: string;
  language: string;
  transcript: string;
  segments: TranscriptSegment[];
  asr_mode: 'whisper' | 'demo';
  diarization_status?: string;
}
