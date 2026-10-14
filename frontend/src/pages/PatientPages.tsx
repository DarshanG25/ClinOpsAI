import { useEffect, useState } from 'react';
import {
  ArrowRight, CalendarDays, CircleAlert, FileHeart, FlaskConical, HeartPulse,
  History, ShieldAlert, UserRound,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import * as api from '../services/api';
import type { Patient, Consultation, Prescription } from '../types';

type PatientSection = 'dashboard' | 'history' | 'consultations' | 'prescriptions' | 'tests' | 'appointments' | 'profile';

const patientSections: Record<PatientSection, { title: string; eyebrow: string; intro: string }> = {
  dashboard: { title: 'Your health, in one place', eyebrow: 'PATIENT PORTAL', intro: 'A straightforward place to review the care information shared with your account.' },
  history: { title: 'Medical history', eyebrow: 'YOUR RECORD', intro: 'Review the health information linked to your account.' },
  consultations: { title: 'Your consultations', eyebrow: 'VISIT HISTORY', intro: 'Review consultations that your care team has made available.' },
  prescriptions: { title: 'Prescriptions', eyebrow: 'MEDICATIONS', intro: 'Review prescriptions approved by your care team.' },
  tests: { title: 'Tests and results', eyebrow: 'YOUR RESULTS', intro: 'Keep track of tests and results shared with you.' },
  appointments: { title: 'Appointments', eyebrow: 'YOUR CARE PLAN', intro: 'See upcoming visits and follow-up plans.' },
  profile: { title: 'Your profile', eyebrow: 'ACCOUNT DETAILS', intro: 'Review your personal and contact information.' },
};

function readableError(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: unknown } } }).response;
    if (typeof response?.data?.detail === 'string') return response.data.detail;
  }
  return 'Could not load your account information. Please try again.';
}

function dateLabel(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Date not recorded' : date.toLocaleDateString(undefined, {
    dateStyle: 'medium',
  });
}

function statusLabel(value: string): string {
  return value.replace(/_/g, ' ').toLowerCase().replace(/(^|\s)\S/g, (char) => char.toUpperCase());
}

function PatientDataState({ loading, error, children }: {
  loading: boolean; error: string | null; children: React.ReactNode;
}) {
  if (loading) return <div className="state-panel" role="status"><span className="loading-dot" /> Loading your records…</div>;
  if (error) return <div className="state-panel state-error" role="alert"><CircleAlert size={19} />{error}</div>;
  return children;
}

export function PatientPortalPage({ section }: { section: PatientSection }) {
  const config = patientSections[section];
  const [patient, setPatient] = useState<Patient | null>(null);
  const [consultations, setConsultations] = useState<Consultation[]>([]);
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [patients, visits] = await Promise.all([api.listPatients(), api.listConsultations()]);
        const sortedVisits = [...visits].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
        const approvedPrescriptions = await Promise.all(sortedVisits.map(async (visit) => {
          try {
            const prescription = await api.getPrescription(visit.id);
            return prescription.status === 'APPROVED' ? prescription : null;
          } catch (cause) {
            const status = (cause as { response?: { status?: number } })?.response?.status;
            if (status === 403 || status === 404) return null;
            throw cause;
          }
        }));
        if (active) {
          setPatient(patients[0] ?? null);
          setConsultations(sortedVisits);
          setPrescriptions(approvedPrescriptions.filter((item): item is Prescription => item !== null));
        }
      } catch (cause) {
        if (active) setError(readableError(cause));
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, []);

  const content = <PatientDataState loading={loading} error={error}>
    {section === 'dashboard' ? <Dashboard patient={patient} consultations={consultations} prescriptions={prescriptions} />
      : section === 'consultations' ? <ConsultationList consultations={consultations} />
        : section === 'prescriptions' ? <PrescriptionList prescriptions={prescriptions} />
          : section === 'profile' ? <Profile patient={patient} />
            : section === 'history' ? <HistoryPage patient={patient} />
              : <UnavailableSection section={section} config={config} />}
  </PatientDataState>;

  return <div className="page-stack patient-facing">
    <div className="page-heading"><div><span className="eyebrow">{config.eyebrow}</span><h2>{config.title}</h2><p>{config.intro}</p></div>{section === 'dashboard' && <span className="patient-welcome"><HeartPulse size={19} /> Your care overview</span>}</div>
    <div className="patient-contract-alert" role="note"><ShieldAlert size={20} /><div><strong>Your records are protected</strong><p>Only information linked to your patient account and approved for sharing is shown here.</p></div></div>
    {content}
  </div>;
}

function Dashboard({ patient, consultations, prescriptions }: {
  patient: Patient | null; consultations: Consultation[]; prescriptions: Prescription[];
}) {
  const dashboardTiles = [
    { title: 'Consultations shared', value: consultations.length, note: 'Available to your account', icon: History },
    { title: 'Approved prescriptions', value: prescriptions.length, note: 'Approved by your care team', icon: FileHeart },
    { title: 'Test results', value: 'Not available', note: 'No test-results service yet', icon: FlaskConical },
    { title: 'Appointments', value: 'Not available', note: 'No appointment service yet', icon: CalendarDays },
  ];
  return <>
    <div className="patient-metric-grid">{dashboardTiles.map(({ title, value, note, icon: Icon }) => <article className="patient-metric-card" key={title}><span className="patient-metric-icon"><Icon size={19} /></span><span>{title}</span><strong>{value}</strong><small>{note}</small></article>)}</div>
    <section className="surface-card patient-welcome-card"><span className="welcome-icon"><UserRound size={23} /></span><div><span className="eyebrow">YOUR ACCOUNT</span><h3>{patient ? `Welcome, ${patient.name}` : 'No patient record is linked'}</h3><p>{patient ? 'Your dashboard includes only records linked to your authenticated patient account.' : 'Contact your care team if you believe a patient record should be linked to your account.'}</p></div></section>
    <ConsultationList consultations={consultations} compact />
    <section className="surface-card"><div className="section-heading"><div><span className="eyebrow">CARE SERVICES</span><h3>Tests and appointments</h3></div></div><p className="patient-plain-note"><CircleAlert size={16} /> Test results and appointment records are not yet available through the backend.</p></section>
  </>;
}

function ConsultationList({ consultations, compact = false }: { consultations: Consultation[]; compact?: boolean }) {
  return <section className="surface-card">
    <div className="section-heading"><div><span className="eyebrow">{compact ? 'CARE TIMELINE' : 'VISIT HISTORY'}</span><h3>{compact ? 'Recent consultations' : 'Consultations shared with you'}</h3></div></div>
    {consultations.length === 0 ? <div className="empty-state"><span className="empty-icon"><History size={21} /></span><h4>No consultations are available</h4><p>Consultations will appear here after your care team has approved them for patient access.</p></div>
      : <div className="record-list">{consultations.slice(0, compact ? 5 : undefined).map((visit) => <article className="record-row" key={visit.id}><span className="row-avatar"><HeartPulse size={17} /></span><span className="row-primary"><strong>{dateLabel(visit.created_at)}</strong><small>Consultation · {visit.language.toUpperCase()}</small></span><span className="status-badge green">{statusLabel(visit.status)}</span></article>)}</div>}
  </section>;
}

function PrescriptionList({ prescriptions }: { prescriptions: Prescription[] }) {
  return <section className="surface-card">
    <div className="section-heading"><div><span className="eyebrow">DOCTOR-APPROVED</span><h3>Your prescriptions</h3></div></div>
    {prescriptions.length === 0 ? <div className="empty-state"><span className="empty-icon"><FileHeart size={21} /></span><h4>No approved prescriptions are available</h4><p>Drafts and rejected prescriptions are not shown in the patient portal.</p></div>
      : <div className="record-list">{prescriptions.map((prescription) => <article className="prescription-card" key={prescription.id}><div className="section-heading"><div><strong>{prescription.diagnosis_summary || 'Prescription'}</strong><small>{dateLabel(prescription.created_at)}</small></div><span className="status-badge green">Approved</span></div><ul className="prescription-items">{prescription.items.map((item, index) => <li key={`${prescription.id}-${index}`}><strong>{item.medicine}</strong><span>{[item.dosage, item.frequency, item.duration, item.route].filter(Boolean).join(' · ') || 'Instructions not recorded'}</span></li>)}</ul></article>)}</div>}
  </section>;
}

function Profile({ patient }: { patient: Patient | null }) {
  if (!patient) return <section className="surface-card patient-empty-page"><h3>No patient record is linked</h3><p>Contact your care team to confirm that your account is connected to the correct record.</p></section>;
  return <section className="surface-card patient-empty-page"><span className="empty-icon"><UserRound size={21} /></span><span className="eyebrow">PATIENT PROFILE</span><h3>{patient.name}</h3><dl className="patient-profile-details"><div><dt>Age</dt><dd>{patient.age ?? 'Not recorded'}</dd></div><div><dt>Gender</dt><dd>{patient.gender || 'Not recorded'}</dd></div><div><dt>Preferred language</dt><dd>{patient.language || 'Not recorded'}</dd></div><div><dt>Contact</dt><dd>{patient.contact || 'Not recorded'}</dd></div></dl></section>;
}

function HistoryPage({ patient }: { patient: Patient | null }) {
  return <div className="page-stack"><Profile patient={patient} /><section className="surface-card"><span className="eyebrow">STRUCTURED MEDICAL HISTORY</span><h3>History details are not available yet</h3><p>The backend does not currently provide patient-linked conditions, allergies, family history, or longitudinal medical history endpoints. This page does not infer clinical facts from consultation drafts.</p></section></div>;
}

function UnavailableSection({ section, config }: {
  section: 'tests' | 'appointments'; config: { title: string };
}) {
  const isTests = section === 'tests';
  return <section className="surface-card patient-empty-page"><span className="empty-icon">{isTests ? <FlaskConical size={21} /> : <CalendarDays size={21} />}</span><span className="eyebrow">{isTests ? 'YOUR RESULTS' : 'YOUR CARE PLAN'}</span><h3>{config.title} are not available yet</h3><p>The backend does not currently provide patient-linked {isTests ? 'test and result' : 'appointment and follow-up'} records. No sample or guessed information is displayed.</p><p className="patient-plain-note"><CircleAlert size={16} /> If you need help with your care, contact your healthcare provider directly.</p><Link className="button button-secondary" to="/patient/dashboard">Return to my dashboard <ArrowRight size={15} /></Link></section>;
}
