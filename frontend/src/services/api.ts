import axios from 'axios';
import type {
  Patient, Consultation, Transcript, ClinicalData, Recommendation,
  Prescription, ProcessResponse, ClinicalSummary,
} from '../types';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
    timeout: 10 * 60 * 1000, // First ASR run downloads the model and CPU transcription is slow
});

export default api;

// ---------- Patients ----------
export async function createPatient(payload: {
  name: string; age?: number; gender?: string; language?: string; contact?: string;
}): Promise<Patient> {
  const { data } = await api.post('/patients', payload);
  return data;
}

export async function listPatients(): Promise<Patient[]> {
  const { data } = await api.get('/patients');
  return data;
}

// ---------- Consultations ----------
export async function createConsultation(payload: {
  patient_id: string; doctor_id?: string; language?: string; notes?: string;
}): Promise<Consultation> {
  const { data } = await api.post('/consultations', payload);
  return data;
}

export async function listConsultations(): Promise<Consultation[]> {
  const { data } = await api.get('/consultations');
  return data;
}

export async function getConsultation(id: string): Promise<Consultation> {
  const { data } = await api.get(`/consultations/${id}`);
  return data;
}

export async function uploadAudio(consultationId: string, file: File) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post(`/consultations/${consultationId}/audio`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function processConsultation(consultationId: string): Promise<ProcessResponse> {
  const { data } = await api.post(`/consultations/${consultationId}/process`);
  return data;
}

export async function getTranscript(consultationId: string): Promise<Transcript> {
  const { data } = await api.get(`/consultations/${consultationId}/transcript`);
  return data;
}

export async function getClinicalSummary(consultationId: string): Promise<ClinicalSummary> {
  const { data } = await api.get(`/consultations/${consultationId}/clinical-summary`);
  return data;
}

export async function generateClinicalSummary(consultationId: string): Promise<ClinicalSummary> {
  const { data } = await api.post(`/consultations/${consultationId}/clinical-summary/generate`);
  return data;
}

export async function updateSpeakerRoles(
  consultationId: string, roles: Record<string, string>,
): Promise<Transcript> {
  const { data } = await api.put(`/consultations/${consultationId}/speaker-roles`, { roles });
  return data;
}

export async function getClinicalData(consultationId: string): Promise<ClinicalData> {
  const { data } = await api.get(`/consultations/${consultationId}/clinical-data`);
  return data;
}

export async function getRecommendations(consultationId: string): Promise<Recommendation[]> {
  const { data } = await api.get(`/consultations/${consultationId}/recommendations`);
  return data;
}

export async function regenerateRecommendations(consultationId: string): Promise<Recommendation[]> {
  const { data } = await api.post(`/consultations/${consultationId}/recommendations`);
  return data;
}

export interface RecommendationEditItem {
  medicine: string;
  dosage?: string;
  frequency?: string;
  duration?: string;
  route?: string;
  reason?: string;
}

export async function saveDoctorEditedRecommendations(
  consultationId: string, items: RecommendationEditItem[],
): Promise<Recommendation[]> {
  const { data } = await api.put(`/consultations/${consultationId}/recommendations`, { items });
  return data;
}

export async function approveConsultation(consultationId: string, payload: {
  doctor_id: string; approved: boolean; diagnosis_summary?: string;
  precautions?: string[]; rejection_reason?: string;
}): Promise<Prescription> {
  const { data } = await api.post(`/consultations/${consultationId}/approve`, payload);
  return data;
}

export async function getPrescription(consultationId: string): Promise<Prescription> {
  const { data } = await api.get(`/consultations/${consultationId}/prescription`);
  return data;
}

export function prescriptionPdfUrl(consultationId: string): string {
  const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';
  return `${base}/consultations/${consultationId}/prescription/pdf`;
}
