import { ArrowRight, CalendarDays, CircleAlert, FileHeart, FlaskConical, HeartPulse, History, ShieldAlert, UserRound } from 'lucide-react';
import { Link } from 'react-router-dom';

type PatientSection = 'dashboard' | 'history' | 'consultations' | 'prescriptions' | 'tests' | 'appointments' | 'profile';

const patientSections: Record<PatientSection, { title: string; eyebrow: string; intro: string }> = {
  dashboard: { title: 'Your health, in one place', eyebrow: 'PATIENT PORTAL', intro: 'A straightforward place to review your care information.' },
  history: { title: 'Medical history', eyebrow: 'YOUR RECORD', intro: 'Review the health information linked to your account.' },
  consultations: { title: 'Your consultations', eyebrow: 'VISIT HISTORY', intro: 'Find summaries from your recent care visits.' },
  prescriptions: { title: 'Prescriptions', eyebrow: 'MEDICATIONS', intro: 'Review prescriptions approved by your care team.' },
  tests: { title: 'Tests and results', eyebrow: 'YOUR RESULTS', intro: 'Keep track of tests and results shared with you.' },
  appointments: { title: 'Appointments', eyebrow: 'YOUR CARE PLAN', intro: 'See upcoming visits and follow-up plans.' },
  profile: { title: 'Your profile', eyebrow: 'ACCOUNT DETAILS', intro: 'Review your personal and contact information.' },
};

const dashboardTiles = [
  { title: 'Next appointment', icon: CalendarDays },
  { title: 'Approved prescriptions', icon: FileHeart },
  { title: 'Recent test results', icon: FlaskConical },
  { title: 'Medical history', icon: History },
];

export function PatientPortalPage({ section }: { section: PatientSection }) {
  const config = patientSections[section];
  return <div className="page-stack patient-facing">
    <div className="page-heading"><div><span className="eyebrow">{config.eyebrow}</span><h2>{config.title}</h2><p>{config.intro}</p></div>{section === 'dashboard' && <span className="patient-welcome"><HeartPulse size={19} /> Your care overview</span>}</div>

    <div className="patient-contract-alert" role="status"><ShieldAlert size={20} /><div><strong>Your personal records are not connected yet</strong><p>The backend does not provide patient sign-in or patient-linked record access. For privacy, this portal does not load another person’s records or display unverified sample information.</p></div><Link to="/login">About account access <ArrowRight size={14} /></Link></div>

    {section === 'dashboard' ? <>
      <div className="patient-metric-grid">{dashboardTiles.map(({ title, icon: Icon }) => <article className="patient-metric-card" key={title}><span className="patient-metric-icon"><Icon size={19} /></span><span>{title}</span><strong>Not connected</strong><small>Patient account service required</small></article>)}</div>
      <section className="surface-card patient-welcome-card"><span className="welcome-icon"><UserRound size={23} /></span><div><span className="eyebrow">A NOTE ABOUT YOUR INFORMATION</span><h3>Nothing has been added to this portal</h3><p>Once the backend supports secure patient accounts, information shared with your account can appear here. No medical facts are being generated or assumed.</p></div></section>
      <section className="surface-card"><div className="section-heading"><div><span className="eyebrow">CARE TIMELINE</span><h3>Your recent visits</h3></div></div><div className="empty-state"><span className="empty-icon"><History size={21} /></span><h4>Visit history is not connected</h4><p>Patient-linked consultations are not available through the current API.</p><Link className="subtle-link" to="/patient/consultations">Visit consultations <ArrowRight size={15} /></Link></div></section>
    </> : <section className="surface-card patient-empty-page"><span className="empty-icon">{section === 'history' ? <History size={21} /> : section === 'prescriptions' ? <FileHeart size={21} /> : section === 'tests' ? <FlaskConical size={21} /> : section === 'appointments' ? <CalendarDays size={21} /> : section === 'consultations' ? <HeartPulse size={21} /> : <UserRound size={21} />}</span><span className="eyebrow">NO PATIENT DATA REQUESTED</span><h3>{section === 'profile' ? 'Profile details are not available' : `${config.title} are not available`}</h3><p>{section === 'profile'
        ? 'The current backend does not provide patient identity, profile, or account endpoints.'
        : 'There is no patient authentication or patient-linked data endpoint in the current backend. This area will not show clinician-only notes, unapproved drafts, or guessed health information.'}</p><p className="patient-plain-note"><CircleAlert size={16} /> If you need help with your care, contact your healthcare provider directly.</p><Link className="button button-secondary" to="/patient/dashboard">Return to my dashboard</Link></section>}
  </div>;
}
