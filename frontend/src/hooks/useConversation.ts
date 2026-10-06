import { useCallback, useEffect, useState } from 'react';
import * as api from '../services/api';
import type { RecommendationEditItem } from '../services/api';
import type {
  Consultation, Transcript, ClinicalData, ClinicalSummary, Recommendation, Prescription,
} from '../types';

/**
 * Drives one consultation through the full pipeline:
 * audio -> process (ASR + clinical extraction + recommendations)
 * -> doctor edit -> approve/reject -> prescription -> PDF.
 */
export function useConsultationWorkflow(consultation: Consultation | null) {
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [clinicalData, setClinicalData] = useState<ClinicalData | null>(null);
  const [clinicalSummary, setClinicalSummary] = useState<ClinicalSummary | null>(null);
  const [clinicalSummaryStatus, setClinicalSummaryStatus] = useState<string | null>(null);
  const [clinicalSummaryError, setClinicalSummaryError] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [prescription, setPrescription] = useState<Prescription | null>(null);
  const [processing, setProcessing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string>(consultation?.status ?? 'CREATED');

  useEffect(() => {
    setTranscript(null);
    setClinicalSummary(null);
    setClinicalSummaryStatus(null);
    setClinicalSummaryError(null);
    setError(null);
    if (consultation) setStatus(consultation.status);
    if (!consultation || ['CREATED', 'AUDIO_UPLOADED', 'PROCESSING', 'FAILED'].includes(consultation.status)) {
      return;
    }

    let active = true;
    const loadSavedTranscript = async () => {
      try {
        const savedTranscript = await api.getTranscript(consultation.id);
        if (!active) return;
        setTranscript(savedTranscript);
        try {
          const savedSummary = await api.getClinicalSummary(consultation.id);
          if (!active) return;
          setClinicalSummary(savedSummary);
          setClinicalSummaryStatus(savedSummary.status);
        } catch (err: any) {
          if (!active) return;
          if (err?.response?.status === 404) {
            setClinicalSummaryStatus('missing');
          } else {
            setClinicalSummaryError('Could not load the saved clinical summary.');
          }
        }
      } catch (err: any) {
        if (active && err?.response?.status !== 404) {
          setError('Could not load the saved transcript.');
        }
      }
    };
    void loadSavedTranscript();
    return () => {
      active = false;
    };
  }, [consultation?.id, consultation?.status]);

  const reset = useCallback(() => {
    setTranscript(null);
    setClinicalData(null);
    setClinicalSummary(null);
    setClinicalSummaryStatus(null);
    setClinicalSummaryError(null);
    setRecommendations([]);
    setPrescription(null);
    setError(null);
    setStatus('CREATED');
  }, []);

  const generateSummary = useCallback(async (consultationId: string) => {
    setClinicalSummaryError(null);
    setClinicalSummaryStatus('generating');
    try {
      const summary = await api.generateClinicalSummary(consultationId);
      setClinicalSummary(summary);
      setClinicalSummaryStatus(summary.status);
    } catch (err: any) {
      setClinicalSummaryStatus('failed');
      setClinicalSummaryError(
        err?.response?.data?.detail || 'Clinical summary generation failed. The full transcript is preserved.',
      );
    }
  }, []);

  const uploadAndProcess = useCallback(async (consultationId: string, file: File) => {
    setError(null);
    setProcessing(true);
    try {
      await api.uploadAudio(consultationId, file);
      setStatus('AUDIO_UPLOADED');
      const result = await api.processConsultation(consultationId);
      setStatus(result.status);
      setClinicalSummaryStatus(result.clinical_summary_status ?? null);
      setClinicalSummaryError(
        result.clinical_summary_status === 'failed'
          ? 'Clinical summary could not be generated. The full transcript is preserved.'
          : null,
      );

      const [t, cd, recs] = await Promise.all([
        api.getTranscript(consultationId),
        api.getClinicalData(consultationId),
        api.getRecommendations(consultationId),
      ]);
      setTranscript(t);
      setClinicalData(cd);
      setRecommendations(recs);
      if (result.clinical_summary_status !== 'failed') {
        try {
          const summary = await api.getClinicalSummary(consultationId);
          setClinicalSummary(summary);
          setClinicalSummaryStatus(summary.status);
        } catch (summaryErr: any) {
          if (summaryErr?.response?.status !== 404) {
            setClinicalSummaryError('Clinical summary is currently unavailable. The full transcript is preserved.');
          }
        }
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Processing failed. Please try again.');
    } finally {
      setProcessing(false);
    }
  }, []);

  const saveEdits = useCallback(async (consultationId: string, items: RecommendationEditItem[]) => {
    setSaving(true);
    setError(null);
    try {
      const updated = await api.saveDoctorEditedRecommendations(consultationId, items);
      setRecommendations(updated);
      setStatus('DOCTOR_REVIEW');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not save edits.');
    } finally {
      setSaving(false);
    }
  }, []);

  const saveSpeakerRoles = useCallback(async (consultationId: string, roles: Record<string, string>) => {
    setSaving(true);
    setError(null);
    try {
      const updatedTranscript = await api.updateSpeakerRoles(consultationId, roles);
      setTranscript(updatedTranscript);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not save speaker roles.');
    } finally {
      setSaving(false);
    }
  }, []);

  const approve = useCallback(
    async (consultationId: string, doctorId: string, diagnosisSummary: string, precautions: string[]) => {
      setSaving(true);
      setError(null);
      try {
        const presc = await api.approveConsultation(consultationId, {
          doctor_id: doctorId,
          approved: true,
          diagnosis_summary: diagnosisSummary || undefined,
          precautions: precautions.length ? precautions : undefined,
        });
        setPrescription(presc);
        setStatus('APPROVED');
      } catch (err: any) {
        setError(err?.response?.data?.detail || 'Approval failed.');
      } finally {
        setSaving(false);
      }
    },
    [],
  );

  const reject = useCallback(async (consultationId: string, doctorId: string, reason: string) => {
    setSaving(true);
    setError(null);
    try {
      const presc = await api.approveConsultation(consultationId, {
        doctor_id: doctorId,
        approved: false,
        rejection_reason: reason || undefined,
      });
      setPrescription(presc);
      setStatus('REJECTED');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Rejection failed.');
    } finally {
      setSaving(false);
    }
  }, []);

  return {
    transcript, clinicalData, clinicalSummary, clinicalSummaryStatus, clinicalSummaryError,
    recommendations, prescription, status,
    processing, saving, error,
    uploadAndProcess, saveEdits, saveSpeakerRoles, approve, reject, reset,
    generateSummary,
  };
}
