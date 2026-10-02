import { useEffect, useState } from 'react';
import * as api from '../services/api';
import type { Consultation, Patient } from '../types';
import { useConsultationWorkflow } from '../hooks/useConversation';
import LanguageSelector from '../components/LanguageSelector';
import ConversationInput from '../components/ConversationInput';
import TranscriptViewer from '../components/TranscriptViewer';
import RecommendationPanel from '../components/RecommendationPanel';
import DoctorApprovalPanel from '../components/DoctorApprovalPanel';
import PrescriptionPreview from '../components/PrescriptionPreview';
import PdfDownloadButton from '../components/PdfDownloadButton';

const STATUS_STEPS = [
  'CREATED', 'AUDIO_UPLOADED', 'PROCESSING', 'TRANSCRIBED', 'CLINICAL_EXTRACTED',
  'RECOMMENDATIONS_GENERATED', 'DOCTOR_REVIEW', 'APPROVED', 'PRESCRIPTION_GENERATED',
];

function StatusStepper({ status }: { status: string }) {
  const idx = STATUS_STEPS.indexOf(status);
  const isTerminalBad = status === 'REJECTED' || status === 'FAILED';
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      {isTerminalBad ? (
        <span className="rounded-full bg-rose-900 px-3 py-1 font-medium text-rose-300">{status}</span>
      ) : (
        STATUS_STEPS.map((step, i) => (
          <span
            key={step}
            className={`rounded-full px-2.5 py-1 font-medium ${
              i <= idx ? 'bg-indigo-900 text-indigo-300' : 'bg-slate-800 text-slate-500'
            }`}
          >
            {step.replace(/_/g, ' ')}
          </span>
        ))
      )}
    </div>
  );
}

function NewConsultationForm({ onCreated }: { onCreated: (c: Consultation) => void }) {
  const [name, setName] = useState('');
  const [age, setAge] = useState('');
  const [gender, setGender] = useState('');
  const [language, setLanguage] = useState('en');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const patient: Patient = await api.createPatient({
        name: name.trim(),
        age: age ? Number(age) : undefined,
        gender: gender || undefined,
        language,
      });
      const consultation = await api.createConsultation({ patient_id: patient.id, language });
      onCreated(consultation);
    } catch (err) {
      setError('Could not create the consultation. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <h3 className="font-semibold text-white">New Consultation</h3>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Patient name"
          required
          className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white sm:col-span-2"
        />
        <input
          value={age}
          onChange={(e) => setAge(e.target.value)}
          placeholder="Age"
          type="number"
          className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
        />
        <select
          value={gender}
          onChange={(e) => setGender(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
        >
          <option value="">Gender (optional)</option>
          <option value="male">Male</option>
          <option value="female">Female</option>
          <option value="other">Other</option>
        </select>
        <div className="sm:col-span-2">
          <label className="text-xs text-slate-400">Consultation language</label>
          <div className="mt-1">
            <LanguageSelector value={language} onChange={setLanguage} />
          </div>
        </div>
      </div>
      <button
        type="submit"
        disabled={loading}
        className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
      >
        {loading ? 'Creating…' : 'Start Consultation'}
      </button>
      {error && <p className="mt-2 text-sm text-rose-400">{error}</p>}
    </form>
  );
}

function Dashboard({ onSelect, onNew }: { onSelect: (c: Consultation) => void; onNew: () => void }) {
  const [consultations, setConsultations] = useState<Consultation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listConsultations()
      .then(setConsultations)
      .catch(() => setConsultations([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-white">Consultations</h3>
        <button
          onClick={onNew}
          className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500"
        >
          + New Consultation
        </button>
      </div>
      {loading ? (
        <p className="mt-3 text-sm text-slate-500">Loading…</p>
      ) : consultations.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">No consultations yet. Create one to get started.</p>
      ) : (
        <ul className="mt-3 divide-y divide-slate-800">
          {consultations.map((c) => (
            <li key={c.id}>
              <button
                onClick={() => onSelect(c)}
                className="flex w-full items-center justify-between py-2.5 text-left text-sm hover:bg-slate-800/50 rounded px-2"
              >
                <span className="text-slate-200">{c.id}</span>
                <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-400">{c.status}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ConsultationWorkspace({ consultation, onBack }: { consultation: Consultation; onBack: () => void }) {
  const wf = useConsultationWorkflow(consultation);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleFileSelected = (file: File) => {
    setSelectedFile(file);
    wf.uploadAndProcess(consultation.id, file);
  };

  const doctorId = consultation.doctor_id ?? '';

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <button onClick={onBack} className="text-sm text-slate-400 hover:text-white">
          ← Back to dashboard
        </button>
        <StatusStepper status={wf.status} />
      </div>

      {wf.error && (
        <div className="rounded-lg border border-rose-800 bg-rose-950 px-4 py-2 text-sm text-rose-300">
          {wf.error}
        </div>
      )}

      {!wf.transcript && (
        <ConversationInput onFileSelected={handleFileSelected} disabled={wf.processing} />
      )}
      {selectedFile && !wf.transcript && (
        <p className="text-xs text-slate-500">Selected: {selectedFile.name}</p>
      )}

      {(wf.processing || wf.transcript) && (
        <TranscriptViewer
          transcript={wf.transcript}
          loading={wf.processing}
          savingRoles={wf.saving}
          onSaveRoles={(roles) => wf.saveSpeakerRoles(consultation.id, roles)}
        />
      )}

      {wf.transcript && (
        <RecommendationPanel
          clinicalData={wf.clinicalData}
          recommendations={wf.recommendations}
          loading={false}
        />
      )}

      {wf.transcript && wf.status !== 'APPROVED' && wf.status !== 'REJECTED' && wf.status !== 'PRESCRIPTION_GENERATED' && (
        <DoctorApprovalPanel
          recommendations={wf.recommendations}
          saving={wf.saving}
          onSaveEdits={(items) => wf.saveEdits(consultation.id, items)}
          onApprove={(summary, precautions) => wf.approve(consultation.id, doctorId, summary, precautions)}
          onReject={(reason) => wf.reject(consultation.id, doctorId, reason)}
        />
      )}

      {wf.prescription && <PrescriptionPreview prescription={wf.prescription} />}

      {wf.prescription?.status === 'APPROVED' && (
        <PdfDownloadButton consultationId={consultation.id} enabled />
      )}
    </div>
  );
}

const HomePage = () => {
  const [active, setActive] = useState<Consultation | null>(null);
  const [creating, setCreating] = useState(false);

  if (active) {
    return <ConsultationWorkspace consultation={active} onBack={() => setActive(null)} />;
  }

  if (creating) {
    return (
      <div className="space-y-4">
        <button onClick={() => setCreating(false)} className="text-sm text-slate-400 hover:text-white">
          ← Back to dashboard
        </button>
        <NewConsultationForm
          onCreated={(c) => {
            setCreating(false);
            setActive(c);
          }}
        />
      </div>
    );
  }

  return <Dashboard onSelect={setActive} onNew={() => setCreating(true)} />;
};

export default HomePage;
