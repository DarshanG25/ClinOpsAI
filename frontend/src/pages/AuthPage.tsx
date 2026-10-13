import { useState, type FormEvent } from 'react';
import { Activity, ArrowRight, LockKeyhole, ShieldCheck, Stethoscope, UserRound } from 'lucide-react';
import { Link } from 'react-router-dom';

type Role = 'doctor' | 'patient';

export default function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const [role, setRole] = useState<Role>('doctor');
  const [message, setMessage] = useState('');
  const isRegister = mode === 'register';

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    if (isRegister && values.get('password') !== values.get('confirmPassword')) {
      setMessage('Passwords do not match.');
      return;
    }
    setMessage('Authentication is not implemented by the backend. No credentials were sent or stored. Portal access is not protected.');
    form.reset();
  }

  return (
    <main className="auth-screen">
      <section className="auth-panel">
        <Link className="auth-brand" to="/"><span className="brand-symbol"><Activity size={20} /></span><strong>ClinOps<span className="brand-accent">-AI</span></strong></Link>
        <div className="auth-heading">
          <span className="auth-kicker">CLINICAL WORKFLOW, MADE CLEARER</span>
          <h1>{isRegister ? 'Create your account' : 'Welcome back'}</h1>
          <p>{isRegister ? 'Choose your workspace to get started.' : 'Sign in to continue to your workspace.'}</p>
        </div>

        <fieldset className="role-choice">
          <legend>{isRegister ? 'I am joining as a' : 'Continue as a'}</legend>
          <button type="button" className={role === 'doctor' ? 'role-option selected' : 'role-option'} onClick={() => setRole('doctor')}>
            <Stethoscope size={19} /><span><strong>Doctor</strong><small>Clinical team workspace</small></span>{role === 'doctor' && <span className="role-check" />}
          </button>
          <button type="button" className={role === 'patient' ? 'role-option selected' : 'role-option'} onClick={() => setRole('patient')}>
            <UserRound size={19} /><span><strong>Patient</strong><small>Personal health workspace</small></span>{role === 'patient' && <span className="role-check" />}
          </button>
        </fieldset>

        <form className="auth-form" onSubmit={handleSubmit}>
          {isRegister && <label>Full name<input name="name" autoComplete="name" required placeholder="Your name" /></label>}
          <label>Email address<input name="email" type="email" autoComplete="email" required placeholder="you@example.com" /></label>
          <label>Password<input name="password" type="password" autoComplete={isRegister ? 'new-password' : 'current-password'} required minLength={8} placeholder="At least 8 characters" /></label>
          {isRegister && <label>Confirm password<input name="confirmPassword" type="password" autoComplete="new-password" required minLength={8} placeholder="Enter your password again" /></label>}
          <button className="button button-primary auth-submit" type="submit">{isRegister ? 'Create account' : 'Sign in'} <ArrowRight size={17} /></button>
        </form>

        {message && <p className="inline-message" role="alert">{message}</p>}

        <div className="auth-unavailable"><LockKeyhole size={16} /><span><strong>Secure sign-in is not connected</strong><br />This project currently has no authentication API. This form will not accept or store credentials.</span></div>
        <p className="auth-switch">{isRegister ? 'Already have an account?' : 'New to ClinOps-AI?'} <Link to={isRegister ? '/login' : '/register'}>{isRegister ? 'Sign in' : 'Create an account'}</Link></p>
      </section>
      <aside className="auth-aside">
        <div className="auth-aside-top"><ShieldCheck size={19} /><span>Designed around responsible care</span></div>
        <div className="auth-aside-copy"><span className="eyebrow">THE CLINOPS-AI WORKSPACE</span><h2>Less time navigating. More time caring.</h2><p>Bring patient records and consultation workflows into one clear, considered space.</p></div>
        <div className="auth-aside-footer"><span>SELECTED ROLE</span><strong>{role === 'doctor' ? 'Doctor workspace' : 'Patient workspace'}</strong><p>Secure access will be available when the backend supports authentication.</p></div>
      </aside>
    </main>
  );
}
