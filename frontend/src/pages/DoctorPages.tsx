import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import {
  Activity, ArrowDownWideNarrow, ArrowRight, CalendarDays, CircleAlert,
  ClipboardCheck, FileHeart, Search, Stethoscope as StethoscopeIcon, Users,
} from 'lucide-react';
import * as api from '../services/api';
import type { ClinicalData, Consultation, Patient, Prescription } from '../types';

const displayDate = (value?: string | null, withTime = false) => {
  if (!value) return 'Not recorded';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Not recorded' : date.toLocaleString(undefined, withTime
    ? { dateStyle: 'medium', timeStyle: 'short' }
    : { dateStyle: 'medium' });
};

const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('');
const formatStatus = (value: string) => value.replace(/_/g, ' ').toLowerCase().replace(/(^|\s)\S/g, (char: string) => char.toUpperCase());

function errorMessage(error: unknown, fallback: string) {
  const response = (error as { response?: { data?: { detail?: string } } })?.response;
  return response?.data?.detail || fallback;
}

function PageHeading({ eyebrow, title, description, action }: {
  eyebrow: string; title: string; description: string; action?: ReactNode;
}) {
  return <div className="page-heading"><div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2><p>{description}</p></div>{action}</div>;
}

function MetricCard({ icon: Icon, label, value, note, tone = 'teal' }: {
  icon: typeof Users; label: string; value: string | number; note: string; tone?: string;
}) {
  return <article className="metric-card"><span className={`metric-icon ${tone}`}><Icon size={19} /></span><span className="metric-label">{label}</span><strong className="metric-value">{value}</strong><span className="metric-note">{note}</span></article>;
}

function StatusBadge({ status }: { status: string }) {
  const tone = ['APPROVED', 'PRESCRIPTION_GENERATED'].includes(status) ? 'green'
    : ['DOCTOR_REVIEW', 'RECOMMENDATIONS_GENERATED'].includes(status) ? 'amber'
      : ['REJECTED', 'FAILED'].includes(status) ? 'red' : 'blue';
  return <span className={`status-badge ${tone}`}>{formatStatus(status)}</span>;
}

function RequestState({ loading, error, empty, onRetry }: {
  loading: boolean; error: string | null; empty: string; onRetry?: () => void;
}) {
  if (loading) return <div className="state-panel" role="status"><span className="loading-dot" /> Loading records…</div>;
  if (error) return <div className="state-panel state-error" role="alert"><CircleAlert size={19} /><span>{error}</span>{onRetry && <button className="button button-secondary" onClick={onRetry}>Try again</button>}</div>;
  return <div className="state-panel">{empty}</div>;
}

export function DoctorDashboard() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [consultations, setConsultations] = useState<Consultation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [patientRows, consultationRows] = await Promise.all([api.listPatients(), api.listConsultations()]);
      setPatients(patientRows);
      setConsultations(consultationRows);
    } catch (cause) {
      setError(errorMessage(cause, 'Could not load dashboard data. Check that the backend is running.'));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { void load(); }, []);

  const sortedConsultations = useMemo(() => [...consultations].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)), [consultations]);
  const patientById = useMemo(() => new Map(patients.map((patient) => [patient.id, patient])), [patients]);
  const now = new Date();
  const todaysConsultations = sortedConsultations.filter((consultation) => {
    const date = new Date(consultation.created_at);
    return date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth() && date.getDate() === now.getDate();
  });
  const pending = sortedConsultations.filter((consultation) => ['DOCTOR_REVIEW', 'RECOMMENDATIONS_GENERATED', 'PRESCRIPTION_GENERATED'].includes(consultation.status));
  const recentPatients = [...patients].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)).slice(0, 5);

  return <div className="page-stack">
    <PageHeading eyebrow="YOUR PRACTICE, AT A GLANCE" title="Good to see you" description="A clear view of patient records and the consultation work in progress." action={<div className="heading-actions"><Link className="button button-secondary" to="/doctor/prescriptions"><FileHeart size={15} /> Review prescriptions</Link><Link className="button button-primary" to="/doctor/consultations/new"><span>＋</span> New consultation</Link></div>} />
    {error && <RequestState loading={false} error={error} empty="" onRetry={() => void load()} />}
    <div className="metric-grid">
      <MetricCard icon={Users} label="Patient records" value={loading ? '—' : patients.length} note="Available in this workspace" />
      <MetricCard icon={StethoscopeIcon} label="Consultations today" value={loading ? '—' : todaysConsultations.length} note="Based on recorded creation date" tone="blue" />
      <MetricCard icon={ClipboardCheck} label="Pending review" value={loading ? '—' : pending.length} note="Awaiting clinician review" tone="amber" />
      <MetricCard icon={Activity} label="All consultations" value={loading ? '—' : consultations.length} note="Across available patient records" tone="purple" />
    </div>

    <div className="dashboard-grid">
      <section className="surface-card dashboard-main">
        <div className="section-heading"><div><span className="eyebrow">WORK QUEUE</span><h3>Recent consultations</h3></div><Link className="subtle-link" to="/doctor/consultations">View all <ArrowRight size={15} /></Link></div>
        {loading || error ? <RequestState loading={loading} error={error} empty="" /> : sortedConsultations.length === 0
          ? <div className="empty-state"><span className="empty-icon"><StethoscopeIcon size={21} /></span><h4>No consultations yet</h4><p>Create a consultation to begin recording a visit and reviewing its transcript.</p><Link to="/doctor/consultations/new" className="button button-secondary">Start a consultation</Link></div>
          : <div className="record-list">{sortedConsultations.slice(0, 6).map((visit) => <Link className="record-row" to={`/doctor/consultations/${visit.id}`} key={visit.id}>
            <span className="row-avatar">{initials(patientById.get(visit.patient_id)?.name ?? 'Patient')}</span><span className="row-primary"><strong>{patientById.get(visit.patient_id)?.name ?? 'Patient record'}</strong><small>{displayDate(visit.created_at, true)} · {visit.id}</small></span><StatusBadge status={visit.status} /><ArrowRight className="row-arrow" size={16} />
          </Link>)}</div>}
      </section>

      <section className="surface-card">
        <div className="section-heading"><div><span className="eyebrow">NEEDS ATTENTION</span><h3>Pending reviews</h3></div><span className="count-chip">{pending.length}</span></div>
        {loading || error ? <RequestState loading={loading} error={error} empty="" /> : pending.length === 0
          ? <div className="compact-empty"><ClipboardCheck size={20} /><p>You’re all caught up. Nothing is waiting for review.</p></div>
          : <div className="review-list">{pending.slice(0, 5).map((visit) => <Link key={visit.id} to={`/doctor/consultations/${visit.id}`} className="review-row"><span className="review-dot" /><span><strong>{patientById.get(visit.patient_id)?.name ?? 'Patient record'}</strong><small>{formatStatus(visit.status)} · {displayDate(visit.created_at)}</small></span><ArrowRight size={16} /></Link>)}</div>}
        <div className="capability-note"><CalendarDays size={17} /><span>Appointments and follow-ups are not yet available from the backend.</span></div>
      </section>
    </div>

    <section className="surface-card">
      <div className="section-heading"><div><span className="eyebrow">PATIENT RECORDS</span><h3>Recently added patients</h3></div><Link className="subtle-link" to="/doctor/patients">Open directory <ArrowRight size={15} /></Link></div>
      {loading || error ? <RequestState loading={loading} error={error} empty="" /> : recentPatients.length === 0
        ? <div className="empty-state"><span className="empty-icon"><Users size={21} /></span><h4>Your directory is empty</h4><p>Patient records are added when a new consultation is created.</p><Link to="/doctor/consultations/new" className="button button-secondary">Create a patient record</Link></div>
        : <div className="patient-mini-grid">{recentPatients.map((patient) => {
          const lastVisit = sortedConsultations.find((visit) => visit.patient_id === patient.id);
          return <Link to={`/doctor/patients/${patient.id}`} className="patient-mini-card" key={patient.id}><span className="row-avatar">{initials(patient.name)}</span><span><strong>{patient.name}</strong><small>{lastVisit ? `Last visit ${displayDate(lastVisit.created_at)}` : 'No consultations recorded'}</small></span><ArrowRight size={15} /></Link>;
        })}</div>}
    </section>
  </div>;
}

export function DoctorPatientDirectory() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [consultations, setConsultations] = useState<Consultation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [sortOrder, setSortOrder] = useState<'recent' | 'name'>('recent');

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [people, visits] = await Promise.all([api.listPatients(), api.listConsultations()]);
      setPatients(people);
      setConsultations(visits);
    } catch (cause) {
      setError(errorMessage(cause, 'Could not load patient records.'));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { void load(); }, []);
  const latestVisit = useMemo(() => {
    const map = new Map<string, Consultation>();
    for (const visit of [...consultations].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))) {
      if (!map.has(visit.patient_id)) map.set(visit.patient_id, visit);
    }
    return map;
  }, [consultations]);
  const visiblePatients = useMemo(() => {
    const term = query.trim().toLowerCase();
    return patients.filter((patient) => !term || `${patient.name} ${patient.id} ${patient.contact ?? ''}`.toLowerCase().includes(term))
      .sort(sortOrder === 'name' ? (a, b) => a.name.localeCompare(b.name) : (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  }, [patients, query, sortOrder]);

  return <div className="page-stack">
    <PageHeading eyebrow="PATIENT RECORDS" title="Patient directory" description="Search and open a record to review the information available in this workspace." action={<Link to="/doctor/consultations/new" className="button button-primary">＋ New consultation</Link>} />
    <section className="surface-card">
      <div className="directory-toolbar">
        <label className="search-field"><Search size={18} /><span className="sr-only">Search by patient name, identifier, or contact</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name, patient ID, or contact" /></label>
        <label className="sort-select"><ArrowDownWideNarrow size={17} /><span className="sr-only">Sort patients</span><select value={sortOrder} onChange={(event) => setSortOrder(event.target.value as 'recent' | 'name')}><option value="recent">Recently added</option><option value="name">Name A–Z</option></select></label>
        <span className="result-count">{loading ? 'Loading…' : `${visiblePatients.length} ${visiblePatients.length === 1 ? 'record' : 'records'}`}</span>
      </div>
      {loading || error ? <RequestState loading={loading} error={error} empty="" onRetry={() => void load()} /> : patients.length === 0
        ? <div className="empty-state"><span className="empty-icon"><Users size={21} /></span><h4>No patient records yet</h4><p>Patient records are created as part of a consultation. No records have been added to this backend.</p><Link to="/doctor/consultations/new" className="button button-secondary">Create first record</Link></div>
        : visiblePatients.length === 0 ? <div className="state-panel">No patients match “{query}”. Try another name or identifier.</div>
          : <div className="responsive-table"><table className="data-table"><thead><tr><th>Patient</th><th>Patient ID</th><th>Last consultation</th><th>Record added</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{visiblePatients.map((patient) => <tr key={patient.id}>
            <td><Link className="table-person" to={`/doctor/patients/${patient.id}`}><span className="row-avatar">{initials(patient.name)}</span><span><strong>{patient.name}</strong><small>{patient.age ? `${patient.age} years` : 'Age not recorded'}{patient.gender ? ` · ${patient.gender}` : ''}</small></span></Link></td>
            <td><span className="identifier">{patient.id}</span></td><td>{latestVisit.has(patient.id) ? displayDate(latestVisit.get(patient.id)?.created_at) : 'No visit recorded'}</td><td>{displayDate(patient.created_at)}</td><td><Link className="table-action" to={`/doctor/patients/${patient.id}`} aria-label={`View record for ${patient.name}`}>View record <ArrowRight size={15} /></Link></td>
          </tr>)}</tbody></table></div>}
    </section>
  </div>;
}

type RecordTab = 'overview' | 'history' | 'consultations' | 'prescriptions' | 'tests' | 'appointments' | 'documents';
const recordTabs: { id: RecordTab; label: string }[] = [
  { id: 'overview', label: 'Overview' }, { id: 'history', label: 'Medical history' },
  { id: 'consultations', label: 'Consultations' }, { id: 'prescriptions', label: 'Prescriptions' },
  { id: 'tests', label: 'Tests & results' }, { id: 'appointments', label: 'Appointments' },
  { id: 'documents', label: 'Documents' },
];

export function DoctorPatientRecord() {
  const { patientId = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const selectedTab = (recordTabs.some(({ id }) => id === params.get('tab')) ? params.get('tab') : 'overview') as RecordTab;
  const [patient, setPatient] = useState<Patient | null>(null);
  const [visits, setVisits] = useState<Consultation[]>([]);
  const [clinicalFacts, setClinicalFacts] = useState<ClinicalData[]>([]);
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    Promise.all([api.getPatient(patientId), api.listConsultations()])
      .then(async ([person, allVisits]) => {
        if (!active) return;
        const patientVisits = allVisits.filter((visit) => visit.patient_id === person.id).sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
        setPatient(person);
        setVisits(patientVisits);
        const completed = patientVisits.filter((visit) => !['CREATED', 'AUDIO_UPLOADED', 'PROCESSING', 'FAILED'].includes(visit.status));
        const [facts, prescriptionResults] = await Promise.all([
          Promise.all(completed.map((visit) => api.getClinicalData(visit.id))),
          Promise.all(patientVisits.filter((visit) => ['APPROVED', 'PRESCRIPTION_GENERATED', 'REJECTED'].includes(visit.status)).map(async (visit) => {
            try { return await api.getPrescription(visit.id); }
            catch (cause) {
              const status = (cause as { response?: { status?: number } })?.response?.status;
              if (status === 404) return null;
              throw cause;
            }
          })),
        ]);
        if (active) {
          setClinicalFacts(facts);
          setPrescriptions(prescriptionResults.filter((item): item is Prescription => item !== null));
        }
      })
      .catch((cause) => { if (active) setError(errorMessage(cause, 'Could not load this patient record.')); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [patientId]);

  const factsByType = useMemo(() => ({
    diagnoses: clinicalFacts.flatMap((item) => item.diagnoses.map((fact) => ({ ...fact, source: item.consultation_id }))),
    symptoms: clinicalFacts.flatMap((item) => item.symptoms.map((fact) => ({ ...fact, source: item.consultation_id }))),
    medications: clinicalFacts.flatMap((item) => item.medications.map((fact) => ({ ...fact, source: item.consultation_id }))),
    precautions: clinicalFacts.flatMap((item) => item.precautions.map((fact) => ({ ...fact, source: item.consultation_id }))),
  }), [clinicalFacts]);
  const latest = visits[0];
  const setTab = (id: RecordTab) => setParams(id === 'overview' ? {} : { tab: id }, { replace: true });

  if (loading) return <div className="page-stack"><RequestState loading error={null} empty="" /></div>;
  if (error || !patient) return <div className="page-stack"><RequestState loading={false} error={error ?? 'Patient not found.'} empty="" /></div>;

  return <div className="page-stack">
    <div className="record-back"><Link to="/doctor/patients">← Patient directory</Link><span className="identifier">Record ID · {patient.id}</span></div>
    <section className="surface-card patient-profile-hero">
      <span className="profile-avatar profile-avatar-large">{initials(patient.name)}</span><div className="profile-identity"><span className="eyebrow">PATIENT RECORD</span><h2>{patient.name}</h2><p>{patient.age ? `${patient.age} years` : 'Age not recorded'}{patient.gender ? ` · ${patient.gender}` : ''} · Preferred language: {patient.language || 'Not recorded'}</p></div>
      <div className="profile-hero-meta"><span>Patient ID</span><strong>{patient.id}</strong><span>Last consultation</span><strong>{latest ? displayDate(latest.created_at) : 'None recorded'}</strong></div>
    </section>
    <div className="record-tabs" role="tablist" aria-label="Patient record sections">{recordTabs.map(({ id, label }) => <button key={id} type="button" role="tab" aria-selected={selectedTab === id} className={selectedTab === id ? 'record-tab active' : 'record-tab'} onClick={() => setTab(id)}>{label}</button>)}</div>

    {selectedTab === 'overview' && <div className="record-content-grid">
      <section className="surface-card"><div className="section-heading"><div><span className="eyebrow">PATIENT DETAILS</span><h3>Overview</h3></div></div><dl className="detail-grid">
        <div><dt>Patient identifier</dt><dd>{patient.id}</dd></div><div><dt>Age</dt><dd>{patient.age ? `${patient.age} years` : 'Not recorded'}</dd></div><div><dt>Gender</dt><dd>{patient.gender || 'Not recorded'}</dd></div><div><dt>Contact</dt><dd>{patient.contact || 'Not recorded'}</dd></div><div><dt>Preferred language</dt><dd>{patient.language || 'Not recorded'}</dd></div><div><dt>Record created</dt><dd>{displayDate(patient.created_at, true)}</dd></div>
      </dl><div className="data-note"><Activity size={16} /> Only data returned by the patient and consultation APIs is shown. No allergy or family-history fields are available.</div></section>
      <section className="surface-card"><div className="section-heading"><div><span className="eyebrow">CARE TIMELINE</span><h3>Recent visits</h3></div><button className="text-button" onClick={() => setTab('consultations')}>View all <ArrowRight size={14} /></button></div>
        {visits.length === 0 ? <div className="compact-empty"><p>No consultation has been recorded for this patient.</p></div> : <div className="record-list">{visits.slice(0, 4).map((visit) => <Link className="record-row" to={`/doctor/consultations/${visit.id}`} key={visit.id}><span className="timeline-pin" /><span className="row-primary"><strong>{displayDate(visit.created_at)}</strong><small>{visit.notes || 'No visit notes recorded'}</small></span><StatusBadge status={visit.status} /><ArrowRight size={15} /></Link>)}</div>}
      </section>
      <section className="surface-card"><div className="section-heading"><div><span className="eyebrow">RECORDED FACTS</span><h3>Clinical information</h3></div></div>
        {factsByType.diagnoses.length + factsByType.symptoms.length + factsByType.medications.length + factsByType.precautions.length === 0
          ? <div className="compact-empty"><p>No clinical facts are available from processed consultations.</p></div>
          : <FactGroups facts={factsByType} />}
      </section>
      <section className="surface-card"><div className="section-heading"><div><span className="eyebrow">PRESCRIPTIONS</span><h3>Prescription status</h3></div><button className="text-button" onClick={() => setTab('prescriptions')}>View prescriptions <ArrowRight size={14} /></button></div>
        {prescriptions.length ? <div className="record-list">{prescriptions.slice(0, 3).map((prescription) => <Link to={`/doctor/consultations/${prescription.consultation_id}`} className="record-row" key={prescription.id}><FileHeart size={18} className="text-teal" /><span className="row-primary"><strong>{prescription.diagnosis_summary || 'Prescription record'}</strong><small>{displayDate(prescription.created_at)}</small></span><StatusBadge status={prescription.status} /></Link>)}</div> : <div className="compact-empty"><p>No prescription records are available.</p></div>}
      </section>
    </div>}

    {selectedTab === 'history' && <section className="surface-card"><div className="section-heading"><div><span className="eyebrow">RECORDED INFORMATION</span><h3>Medical history</h3><p className="section-description">Facts below are extracted from recorded consultations; they are not a separately verified medical history.</p></div></div><FactGroups facts={factsByType} empty="No extracted clinical details are available for this patient." /><div className="data-note"><CircleAlert size={16} /> Allergy lists and family history are not included in the current backend API.</div></section>}
    {selectedTab === 'consultations' && <section className="surface-card"><div className="section-heading"><div><span className="eyebrow">VISIT HISTORY</span><h3>Consultations</h3></div><Link className="button button-secondary" to="/doctor/consultations/new">＋ New consultation</Link></div>{visits.length ? <div className="record-list">{visits.map((visit) => <Link className="record-row" to={`/doctor/consultations/${visit.id}`} key={visit.id}><StethoscopeIcon size={18} className="text-teal" /><span className="row-primary"><strong>{displayDate(visit.created_at, true)}</strong><small>{visit.notes || 'No consultation notes recorded'} · {visit.id}</small></span><StatusBadge status={visit.status} /><ArrowRight size={15} /></Link>)}</div> : <div className="compact-empty"><p>No consultations have been recorded.</p></div>}</section>}
    {selectedTab === 'prescriptions' && <section className="surface-card"><div className="section-heading"><div><span className="eyebrow">MEDICATION RECORDS</span><h3>Prescriptions</h3></div></div>{prescriptions.length ? <PrescriptionRows prescriptions={prescriptions} /> : <div className="compact-empty"><p>No prescription records are available for this patient.</p></div>}</section>}
    {selectedTab === 'tests' && <UnavailableRecord feature="Test orders and results" detail="The backend does not currently expose test orders, laboratory results, or imaging reports." />}
    {selectedTab === 'appointments' && <UnavailableRecord feature="Appointments and follow-ups" detail="The backend does not currently expose an appointment or follow-up API." />}
    {selectedTab === 'documents' && <UnavailableRecord feature="Documents" detail="The current backend does not provide patient-linked document storage." />}
  </div>;
}

function FactGroups({ facts, empty = 'No extracted clinical facts are available.' }: { facts: { diagnoses: { text: string; source: string }[]; symptoms: { text: string; source: string }[]; medications: { text: string; source: string }[]; precautions: { text: string; source: string }[] }; empty?: string }) {
  const groups: [string, typeof facts.diagnoses][] = [['Recorded diagnoses', facts.diagnoses], ['Symptoms', facts.symptoms], ['Medication mentions', facts.medications], ['Precautions', facts.precautions]];
  if (!groups.some(([, entries]) => entries.length)) return <div className="compact-empty"><p>{empty}</p></div>;
  return <div className="fact-grid">{groups.filter(([, entries]) => entries.length).map(([title, entries]) => <div className="fact-group" key={title}><h4>{title}</h4><ul>{entries.map((entry, index) => <li key={`${entry.source}-${entry.text}-${index}`}><span>{entry.text}</span><Link to={`/doctor/consultations/${entry.source}`}>Source visit <ArrowRight size={12} /></Link></li>)}</ul></div>)}</div>;
}

function PrescriptionRows({ prescriptions }: { prescriptions: Prescription[] }) {
  return <div className="responsive-table"><table className="data-table"><thead><tr><th>Prescription</th><th>Date</th><th>Medication items</th><th>Status</th><th /></tr></thead><tbody>{prescriptions.map((prescription) => <tr key={prescription.id}><td><strong>{prescription.diagnosis_summary || 'Prescription'}</strong><small className="table-subline">ID · {prescription.id}</small></td><td>{displayDate(prescription.created_at)}</td><td>{prescription.items.length} {prescription.items.length === 1 ? 'item' : 'items'}</td><td><StatusBadge status={prescription.status} /></td><td><Link className="table-action" to={`/doctor/consultations/${prescription.consultation_id}`}>Open <ArrowRight size={14} /></Link></td></tr>)}</tbody></table></div>;
}

function UnavailableRecord({ feature, detail }: { feature: string; detail: string }) {
  return <section className="surface-card unavailable-card"><span className="empty-icon"><CircleAlert size={21} /></span><div><span className="eyebrow">BACKEND CONTRACT NOT AVAILABLE</span><h3>{feature}</h3><p>{detail} This section is intentionally not populated with placeholder records.</p></div></section>;
}

export function DoctorConsultations() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [consultations, setConsultations] = useState<Consultation[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const filter = searchParams.get('status') ?? 'all';

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [visits, people] = await Promise.all([api.listConsultations(), api.listPatients()]);
      setConsultations(visits.sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)));
      setPatients(people);
    } catch (cause) { setError(errorMessage(cause, 'Could not load consultations.')); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);
  const patientMap = useMemo(() => new Map(patients.map((person) => [person.id, person])), [patients]);
  const filtered = consultations.filter((visit) => {
    const person = patientMap.get(visit.patient_id);
    const matchesQuery = !query.trim() || `${visit.id} ${person?.name ?? ''} ${visit.patient_id} ${visit.notes ?? ''}`.toLowerCase().includes(query.trim().toLowerCase());
    return matchesQuery && (filter === 'all' || (filter === 'review' ? ['DOCTOR_REVIEW', 'RECOMMENDATIONS_GENERATED', 'PRESCRIPTION_GENERATED'].includes(visit.status) : visit.status === filter));
  });

  return <div className="page-stack">
    <PageHeading eyebrow="CLINICAL WORKFLOW" title="Consultations" description="Review the status and details of patient visits." action={<Link className="button button-primary" to="/doctor/consultations/new">＋ New consultation</Link>} />
    <section className="surface-card">
      <div className="directory-toolbar"><label className="search-field"><Search size={18} /><span className="sr-only">Search consultations</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search patient, notes, or visit ID" /></label><label className="sort-select"><span className="sr-only">Filter by status</span><select value={filter} onChange={(event) => setSearchParams(event.target.value === 'all' ? {} : { status: event.target.value })}><option value="all">All statuses</option><option value="review">Needs review</option>{['CREATED', 'AUDIO_UPLOADED', 'PROCESSING', 'TRANSCRIBED', 'CLINICAL_EXTRACTED', 'RECOMMENDATIONS_GENERATED', 'DOCTOR_REVIEW', 'APPROVED', 'REJECTED', 'PRESCRIPTION_GENERATED', 'FAILED'].map((status) => <option key={status} value={status}>{formatStatus(status)}</option>)}</select></label><span className="result-count">{loading ? 'Loading…' : `${filtered.length} consultations`}</span></div>
      {loading || error ? <RequestState loading={loading} error={error} empty="" onRetry={() => void load()} /> : filtered.length === 0 ? <div className="state-panel">{consultations.length ? 'No consultations match these filters.' : 'No consultations have been recorded yet.'}</div> : <div className="record-list">{filtered.map((visit) => <Link className="record-row" to={`/doctor/consultations/${visit.id}`} key={visit.id}><span className="row-avatar">{initials(patientMap.get(visit.patient_id)?.name ?? 'Patient')}</span><span className="row-primary"><strong>{patientMap.get(visit.patient_id)?.name ?? 'Patient record'}</strong><small>{displayDate(visit.created_at, true)} · {visit.notes || `Visit ${visit.id}`}</small></span><StatusBadge status={visit.status} /><ArrowRight className="row-arrow" size={16} /></Link>)}</div>}
    </section>
  </div>;
}

export function DoctorPrescriptions() {
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('all');

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [visits, people] = await Promise.all([api.listConsultations(), api.listPatients()]);
      setPatients(people);
      const candidates = visits.filter((visit) => ['APPROVED', 'PRESCRIPTION_GENERATED', 'REJECTED'].includes(visit.status));
      const results = await Promise.all(candidates.map(async (visit) => {
        try { return await api.getPrescription(visit.id); }
        catch (cause) {
          if ((cause as { response?: { status?: number } })?.response?.status === 404) return null;
          throw cause;
        }
      }));
      setPrescriptions(results.filter((prescription): prescription is Prescription => prescription !== null).sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)));
    } catch (cause) { setError(errorMessage(cause, 'Could not load prescription records.')); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);
  const patientMap = useMemo(() => new Map(patients.map((person) => [person.id, person])), [patients]);
  const visible = prescriptions.filter((prescription) => filter === 'all' || prescription.status === filter);

  return <div className="page-stack">
    <PageHeading eyebrow="MEDICATION RECORDS" title="Prescriptions" description="Prescriptions available through the consultation workflow. Drafts and suggestions are not approved orders." />
    <div className="prescription-safety"><CircleAlert size={18} /><span><strong>Drafts are not prescriptions.</strong> Only records marked approved have been signed off through the doctor review workflow.</span></div>
    <section className="surface-card"><div className="directory-toolbar"><label className="sort-select"><span className="sr-only">Filter prescription status</span><select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">All statuses</option><option value="APPROVED">Approved</option><option value="DRAFT">Draft</option><option value="REJECTED">Rejected</option></select></label><span className="result-count">{loading ? 'Loading…' : `${visible.length} records`}</span></div>
      {loading || error ? <RequestState loading={loading} error={error} empty="" onRetry={() => void load()} /> : visible.length === 0 ? <div className="empty-state"><span className="empty-icon"><FileHeart size={21} /></span><h4>No prescriptions found</h4><p>Approved prescription records appear here after a doctor completes review.</p></div> : <div className="prescription-list">{visible.map((prescription) => <article className="prescription-card" key={prescription.id}><div className="prescription-card-head"><span className="prescription-icon"><FileHeart size={19} /></span><span className="row-primary"><strong>{patientMap.get(prescription.patient_id)?.name ?? 'Patient record'}</strong><small>{displayDate(prescription.created_at, true)} · Prescription {prescription.id}</small></span><StatusBadge status={prescription.status} /></div><div className="prescription-summary"><span><small>Summary</small><strong>{prescription.diagnosis_summary || 'Not recorded'}</strong></span><span><small>Medication items</small><strong>{prescription.items.length}</strong></span><span><small>Consultation</small><strong>{prescription.consultation_id}</strong></span></div><div className="prescription-items">{prescription.items.map((item, index) => <div className="medication-row" key={`${item.medicine}-${index}`}><strong>{item.medicine}</strong><span>{[item.dosage, item.frequency, item.duration, item.route].filter(Boolean).join(' · ') || 'Details not recorded'}</span></div>)}</div><div className="prescription-card-foot"><span>{prescription.status === 'APPROVED' ? `Approved ${displayDate(prescription.approved_at)}` : 'Not approved for patient use'}</span><Link className="table-action" to={`/doctor/consultations/${prescription.consultation_id}`}>Review record <ArrowRight size={14} /></Link></div></article>)}</div>}
    </section>
  </div>;
}

export function DoctorUnavailablePage({ feature }: { feature: string }) {
  const detail = feature === 'Appointments'
    ? 'The backend has no appointments or follow-up endpoint, so upcoming visits cannot be loaded or saved.'
    : feature === 'Tests and results'
      ? 'The backend has no test orders, laboratory-result, or imaging-report endpoint.'
      : 'The backend does not currently expose account or clinic settings.';
  return <div className="page-stack"><PageHeading eyebrow="WORKSPACE" title={feature} description="This workspace is ready to connect when the related backend capability is available." /><section className="surface-card unavailable-card"><span className="empty-icon"><CircleAlert size={21} /></span><div><span className="eyebrow">BACKEND CONTRACT NOT AVAILABLE</span><h3>{feature} are not connected</h3><p>{detail} No sample records are shown and changes cannot be saved.</p><Link className="button button-secondary" to="/doctor/dashboard">Return to overview</Link></div></section></div>;
}
