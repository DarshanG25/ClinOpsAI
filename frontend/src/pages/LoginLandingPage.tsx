import { Activity, ArrowRight, ShieldCheck, Stethoscope, UserRound } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

export default function LoginLandingPage() {
  const { user } = useAuth();

  return (
    <main className="auth-screen">
      <section className="auth-panel">
        <Link className="auth-brand" to="/login">
          <span className="brand-symbol"><Activity size={20} /></span>
          <strong>ClinOps<span className="brand-accent">-AI</span></strong>
        </Link>
        <div className="auth-heading">
          <span className="auth-kicker">SECURE CLINICAL WORKSPACE</span>
          <h1>How would you like to continue?</h1>
          <p>Choose the sign-in that matches your ClinOps-AI account.</p>
        </div>

        <div className="login-role-cards">
          <Link className="login-role-card" to="/doctor/login">
            <span className="login-role-icon doctor"><Stethoscope size={21} /></span>
            <span className="login-role-copy">
              <strong>Continue as Doctor</strong>
              <small>Access assigned patients and clinical workflows.</small>
            </span>
            <ArrowRight size={18} aria-hidden="true" />
          </Link>
          <Link className="login-role-card" to="/patient/login">
            <span className="login-role-icon patient"><UserRound size={21} /></span>
            <span className="login-role-copy">
              <strong>Continue as Patient</strong>
              <small>View your own care information shared with you.</small>
            </span>
            <ArrowRight size={18} aria-hidden="true" />
          </Link>
        </div>

        <p className="auth-switch">
          New patient? <Link to="/patient/register">Create a patient account</Link>
        </p>
        {user && <p className="auth-switch">Already signed in? <Link to={`/${user.role}/dashboard`}>Go to your {user.role} workspace</Link></p>}
      </section>
      <aside className="auth-aside">
        <div className="auth-aside-top"><ShieldCheck size={19} /><span>Designed around responsible care</span></div>
        <div className="auth-aside-copy">
          <span className="eyebrow">THE CLINOPS-AI WORKSPACE</span>
          <h2>Care information, thoughtfully organized.</h2>
          <p>Your sign-in determines which workspace you can access. Permissions are verified by the ClinOps-AI service.</p>
        </div>
        <div className="auth-aside-footer">
          <span>ACCOUNT ACCESS</span>
          <strong>Separate sign-in for each role</strong>
          <p>Doctor accounts are provisioned by a trusted administrator.</p>
        </div>
      </aside>
    </main>
  );
}
