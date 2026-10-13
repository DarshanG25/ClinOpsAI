import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, CircleAlert, FileHeart, UserRound } from 'lucide-react';
import * as api from '../services/api';
import { useConsultationWorkflow } from '../hooks/useConversation';
import ClinicalSummaryPanel from '../components/ClinicalSummaryPanel';
import ConversationInput from '../components/ConversationInput';
import DoctorApprovalPanel from '../components/DoctorApprovalPanel';
import PdfDownloadButton from '../components/PdfDownloadButton';
import PrescriptionPreview from '../components/PrescriptionPreview';
import RecommendationPanel from '../components/RecommendationPanel';
import TranscriptViewer from '../components/TranscriptViewer';
import type { Consultation, Patient, Prescription } from '../types';

function formatDate(value: string) {
  return new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

export default function ConsultationDetailPage() {
  const { consultationId = '' } = useParams();
  const [consultation, setConsultation] = useState<Consultation | null>(null);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [savedPrescription, setSavedPrescription] = useState<Prescription | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const workflow = useConsultationWorkflow(consultation);

  useEffect(() => {
    let active = true;
    setConsultation(null);
    setPatient(null);
    setSavedPrescription(null);
    setLoading(true);
    setPageError(null);
    api.getConsultation(consultationId)
      .then(async (visit) => {
        const linkedPatient = await api.getPatient(visit.patient_id);
        if (!active) return;
        setConsultation(visit);
        setPatient(linkedPatient);
        if (['APPROVED', 'PRESCRIPTION_GENERATED', 'REJECTED'].includes(visit.status)) {
          try {
            const prescription = await api.getPrescription(visit.id);
            if (active) setSavedPrescription(prescription);
          } catch (cause) {
            if ((cause as { response?: { status?: number } })?.response?.status !== 404) throw cause;
          }
        }
      })
      .catch((cause) => {
        if (active) {
          const detail = (cause as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
          setPageError(detail || 'Could not load this consultation.');
        }
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [consultationId]);

  useEffect(() => {
    if (workflow.prescription?.consultation_id === consultationId) setSavedPrescription(workflow.prescription);
  }, [consultationId, workflow.prescription]);

  if (loading) return <div className="state-panel" role="status">Loading consultation…</div>;
  if (pageError || !consultation) return <div className="page-stack"><div className="state-panel state-error" role="alert"><CircleAlert size={19} />{pageError || 'Consultation not found.'}</div><Link to="/doctor/consultations" className="text-button"><ArrowLeft size={15} /> Back to consultations</Link></div>;

  const isTerminal = ['APPROVED', 'REJECTED', 'PRESCRIPTION_GENERATED'].includes(workflow.status);
  const canReview = Boolean(consultation.doctor_id) && !isTerminal;
  const handleFile = (selected: File) => {
    setFile(selected);
    void workflow.uploadAndProcess(consultation.id, selected);
  };

  return <div className="page-stack consultation-detail">
    <Link className="back-link" to="/doctor/consultations"><ArrowLeft size={16} /> All consultations</Link>
    <section className="surface-card consultation-hero">
      <div><span className="eyebrow">CONSULTATION · {consultation.id}</span><h2>{patient?.name ?? 'Patient record'}</h2><p><UserRound size={15} /> {patient?.age ? `${patient.age} years` : 'Age not recorded'}{patient?.gender ? ` · ${patient.gender}` : ''} <span>·</span> {formatDate(consultation.created_at)}</p></div>
      <span className={`status-badge ${workflow.status === 'APPROVED' || workflow.status === 'PRESCRIPTION_GENERATED' ? 'green' : workflow.status === 'FAILED' || workflow.status === 'REJECTED' ? 'red' : 'amber'}`}>{workflow.status.replace(/_/g, ' ')}</span>
    </section>

    {workflow.error && <div className="inline-error" role="alert"><CircleAlert size={17} />{workflow.error}</div>}
    {!workflow.transcript && !workflow.processing && <section className="surface-card"><div className="section-heading"><div><span className="eyebrow">AUDIO INPUT</span><h3>Consultation recording</h3><p className="section-description">Upload a supported recording or record in your browser to generate the transcript and draft clinical information.</p></div></div><ConversationInput onFileSelected={handleFile} disabled={workflow.processing} />{file && <p className="muted-caption">Selected file: {file.name}</p>}</section>}
    {workflow.processing && <div className="inline-message" role="status">Audio is being processed. The first recording may take several minutes.</div>}

    {workflow.transcript && <section className="surface-card"><div className="section-heading"><div><span className="eyebrow">CLINICAL SUMMARY</span><h3>Visit documentation</h3><p className="section-description">Review source-linked content; verify all AI-generated information against the original record.</p></div></div>
      <ClinicalSummaryPanel summary={workflow.clinicalSummary} status={workflow.clinicalSummaryStatus} error={workflow.clinicalSummaryError} generating={workflow.clinicalSummaryStatus === 'generating'} onGenerate={() => void workflow.generateSummary(consultation.id)} />
    </section>}

    {workflow.transcript && <section className="surface-card"><div className="section-heading"><div><span className="eyebrow">SOURCE RECORD</span><h3>Transcript</h3></div></div><TranscriptViewer transcript={workflow.transcript} savingRoles={workflow.saving} onSaveRoles={(roles) => void workflow.saveSpeakerRoles(consultation.id, roles)} /></section>}

    {workflow.transcript && <section className="surface-card"><div className="section-heading"><div><span className="eyebrow">EXTRACTED INFORMATION</span><h3>Clinical data and candidate suggestions</h3><p className="section-description">Extracted medication mentions and AI-generated suggestions are not a prescription.</p></div></div><RecommendationPanel clinicalData={workflow.clinicalData} recommendations={workflow.recommendations} /></section>}

    {canReview && workflow.transcript && <section className="surface-card"><div className="section-heading"><div><span className="eyebrow">AUTHORIZED CLINICIAN REVIEW</span><h3>Review and sign off</h3><p className="section-description">Saved edits remain a draft. Approval creates the prescription record.</p></div></div><DoctorApprovalPanel recommendations={workflow.recommendations} saving={workflow.saving} onSaveEdits={(items) => workflow.saveEdits(consultation.id, items)} onApprove={(summary, precautions) => workflow.approve(consultation.id, consultation.doctor_id ?? '', summary, precautions)} onReject={(reason) => workflow.reject(consultation.id, consultation.doctor_id ?? '', reason)} /></section>}
    {!consultation.doctor_id && workflow.transcript && <div className="data-note"><CircleAlert size={16} /> This consultation has no doctor identifier. The backend cannot authorize an approval action.</div>}

    {savedPrescription && <section className="surface-card"><div className="section-heading"><div><span className="eyebrow">PRESCRIPTION RECORD</span><h3>Prescription details</h3></div>{savedPrescription.status === 'APPROVED' && <PdfDownloadButton consultationId={consultation.id} enabled />}</div><PrescriptionPreview prescription={savedPrescription} /></section>}
    {!workflow.transcript && consultation.notes && <section className="surface-card"><h3>Visit notes</h3><p>{consultation.notes}</p></section>}
    {workflow.status === 'FAILED' && consultation.error_message && <div className="inline-error" role="alert">{consultation.error_message}</div>}
  </div>;
}
