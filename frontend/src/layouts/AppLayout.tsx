import { useState, type ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  Activity, Bell, CalendarDays, ClipboardList, FileHeart, FlaskConical, LayoutDashboard,
  LogOut, Menu, Settings, Stethoscope, Users, X,
} from 'lucide-react';

type Portal = 'doctor' | 'patient';

const doctorNavigation = [
  { label: 'Overview', to: '/doctor/dashboard', icon: LayoutDashboard },
  { label: 'Patients', to: '/doctor/patients', icon: Users },
  { label: 'Consultations', to: '/doctor/consultations', icon: Stethoscope },
  { label: 'Prescriptions', to: '/doctor/prescriptions', icon: FileHeart },
  { label: 'Appointments', to: '/doctor/appointments', icon: CalendarDays },
  { label: 'Tests & results', to: '/doctor/tests', icon: FlaskConical },
  { label: 'Settings', to: '/doctor/settings', icon: Settings },
];

const patientNavigation = [
  { label: 'My dashboard', to: '/patient/dashboard', icon: LayoutDashboard },
  { label: 'Medical history', to: '/patient/history', icon: Activity },
  { label: 'Consultations', to: '/patient/consultations', icon: Stethoscope },
  { label: 'Prescriptions', to: '/patient/prescriptions', icon: FileHeart },
  { label: 'Tests & results', to: '/patient/tests', icon: FlaskConical },
  { label: 'Appointments', to: '/patient/appointments', icon: CalendarDays },
  { label: 'My profile', to: '/patient/profile', icon: ClipboardList },
];

const pageTitles: Record<string, string> = {
  '/doctor/dashboard': 'Overview',
  '/doctor/patients': 'Patient directory',
  '/doctor/consultations': 'Consultations',
  '/doctor/consultations/new': 'New consultation',
  '/doctor/prescriptions': 'Prescriptions',
  '/doctor/appointments': 'Appointments',
  '/doctor/tests': 'Tests & results',
  '/doctor/settings': 'Settings',
  '/patient/dashboard': 'My dashboard',
  '/patient/history': 'Medical history',
  '/patient/consultations': 'Consultations',
  '/patient/prescriptions': 'Prescriptions',
  '/patient/tests': 'Tests & results',
  '/patient/appointments': 'Appointments',
  '/patient/profile': 'My profile',
};

interface Props {
  portal: Portal;
  children: ReactNode;
}

export default function AppLayout({ portal, children }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const items = portal === 'doctor' ? doctorNavigation : patientNavigation;
  const title = pageTitles[location.pathname] ??
    (location.pathname.includes('/patients/') ? 'Patient record' :
      location.pathname.includes('/consultations/') ? 'Consultation details' : 'ClinOps-AI');

  return (
    <div className="app-shell">
      <aside className={`app-sidebar ${menuOpen ? 'is-open' : ''}`}>
        <div className="brand-row">
          <Link className="brand-lockup" to={`/${portal}/dashboard`} onClick={() => setMenuOpen(false)}>
            <span className="brand-symbol"><Activity size={20} strokeWidth={2.4} /></span>
            <span><strong>ClinOps<span className="brand-accent">-AI</span></strong><small>Care, thoughtfully organized</small></span>
          </Link>
          <button
            className="sidebar-close icon-button"
            type="button"
            aria-label="Close navigation"
            onClick={(event) => { event.preventDefault(); setMenuOpen(false); }}
          ><X size={18} /></button>
        </div>

        <div className="portal-switch">
          <span className="portal-switch-icon">{portal === 'doctor' ? <Stethoscope size={17} /> : <Activity size={17} />}</span>
          <span><small>WORKSPACE</small><strong>{portal === 'doctor' ? 'Doctor portal' : 'Patient portal'}</strong></span>
        </div>

        <nav className="side-nav" aria-label={`${portal} navigation`}>
          <p className="nav-caption">WORKSPACE</p>
          {items.map(({ label, to, icon: Icon }) => (
            <NavLink
              className={({ isActive }: { isActive: boolean }) => `nav-link ${isActive ? 'active' : ''}`}
              to={to}
              end={to.endsWith('/dashboard')}
              key={to}
              onClick={() => setMenuOpen(false)}
            >
              <Icon size={18} strokeWidth={1.8} /><span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="safety-note">
            <span className="safety-icon"><Activity size={16} /></span>
            <div><strong>Clinical review matters</strong><p>AI suggestions are drafts. A clinician must review before use.</p></div>
          </div>
          <button className="sign-out-link" type="button" onClick={() => navigate('/login')}>
            <LogOut size={17} /> Sign in / switch role
          </button>
        </div>
      </aside>

      {menuOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}

      <div className="app-main">
        <header className="app-topbar">
          <button
            className="icon-button mobile-menu-button"
            type="button"
            aria-label={menuOpen ? 'Close navigation' : 'Open navigation'}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          ><Menu size={20} /></button>
          <div className="topbar-heading">
            <span className="breadcrumbs">ClinOps-AI <span>/</span> {portal === 'doctor' ? 'Doctor portal' : 'Patient portal'}</span>
            <h1>{title}</h1>
          </div>
          <div className="topbar-actions">
            <span className="prototype-indicator"><span /> Prototype</span>
            <span className="notification-unavailable" aria-label="Notifications are not connected"><Bell size={16} /><small>Notifications unavailable</small></span>
            <details className="profile-menu">
              <summary className="profile-button">
                <span className="profile-avatar">{portal === 'doctor' ? 'DR' : 'PT'}</span>
                <span className="profile-label">{portal === 'doctor' ? 'Care team' : 'My account'}<small>{portal === 'doctor' ? 'Doctor workspace' : 'Patient workspace'}</small></span>
              </summary>
              <div className="profile-popover">
                <Link to={portal === 'doctor' ? '/doctor/settings' : '/patient/profile'} onClick={(event) => event.currentTarget.closest('details')?.removeAttribute('open')}>{portal === 'doctor' ? 'Workspace settings' : 'Profile details'}</Link>
                <Link to="/login" onClick={(event) => event.currentTarget.closest('details')?.removeAttribute('open')}>Sign in / switch role</Link>
              </div>
            </details>
          </div>
        </header>

        <main className="page-content">
          <div className="prototype-notice" role="note">
            <strong>Prototype access</strong>
            <span>Authentication and role-based authorization are not available in the backend yet. Do not use this app with real patient data.</span>
            <Link to="/login">Authentication details</Link>
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
