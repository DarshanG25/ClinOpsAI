import { useEffect, useState, type FormEvent } from 'react';
import { Activity, ArrowLeft, ArrowRight, LockKeyhole, ShieldCheck } from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../auth/AuthContext';
import { registerPatient } from '../services/auth';

type Role = 'doctor' | 'patient';

export default function AuthPage({ mode, role }: { mode: 'login' | 'register'; role: Role }) {
  const [message, setMessage] = useState('');
  const [messageKind, setMessageKind] = useState<'success' | 'error'>('error');
  const [submitting, setSubmitting] = useState(false);
  const isRegister = mode === 'register';
  const { user, loading, sessionError, signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!loading && user) navigate(`/${user.role}/dashboard`, { replace: true });
  }, [loading, navigate, user]);

  useEffect(() => {
    if (sessionError) {
      setMessage(sessionError);
      setMessageKind('error');
    }
  }, [sessionError]);

  useEffect(() => {
    if ((location.state as { registered?: boolean } | null)?.registered) {
      setMessage('Your patient account is ready. Sign in to continue.');
      setMessageKind('success');
      navigate(location.pathname, { replace: true, state: null });
    }
  }, [location.pathname, location.state, navigate]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage('');
    setMessageKind('error');
    const values = new FormData(event.currentTarget);
    const name = String(values.get('name') ?? '').trim();
    const email = String(values.get('email') ?? '').trim();
    const password = String(values.get('password') ?? '');
    if (isRegister && password !== values.get('confirmPassword')) {
      setMessage('Passwords do not match.');
      return;
    }

    setSubmitting(true);
    try {
      if (isRegister && role === 'patient') {
        await registerPatient(name, email, password);
        navigate('/patient/login', { replace: true, state: { registered: true } });
      } else {
        const account = await signIn(email, password, role);
        navigate(`/${account.role}/dashboard`, { replace: true });
      }
    } catch (cause) {
      if (axios.isAxiosError(cause)) {
        const status = cause.response?.status;
        if (status === 401) {
          setMessage('Email or password is incorrect. Check your details and try again.');
        } else if (status === 403) {
          setMessage(`This account is not permitted to sign in to the ${role} workspace. Contact your administrator if you need access.`);
        } else if (!cause.response) {
          setMessage('ClinOps-AI could not reach the sign-in service. Check the connection and try again.');
        } else {
          setMessage('The sign-in service could not complete your request. Try again later.');
        }
      } else if (cause instanceof Error && cause.message.startsWith('This account uses the ')) {
        setMessage(cause.message);
      } else {
        setMessage('Could not complete your request. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-screen">
      <section className="auth-panel">
        <Link className="auth-brand" to="/login"><span className="brand-symbol"><Activity size={20} /></span><strong>ClinOps<span className="brand-accent">-AI</span></strong></Link>
        <div className="auth-heading">
          <span className="auth-kicker">{role === 'doctor' ? 'DOCTOR WORKSPACE' : 'PATIENT WORKSPACE'}</span>
          <h1>{isRegister ? 'Create your patient account' : role === 'doctor' ? 'Doctor sign in' : 'Patient sign in'}</h1>
          <p>{isRegister
            ? 'Create an account for your own patient workspace.'
            : role === 'doctor'
              ? 'Sign in to manage consultations and patients assigned to your doctor account.'
              : 'Sign in to view care information linked to your patient account.'}</p>
        </div>

        <Link className="auth-role-back" to="/login"><ArrowLeft size={15} /> Choose a different sign-in</Link>

        <form className="auth-form" onSubmit={(event) => { void handleSubmit(event); }}>
          {isRegister && <label>Full name<input name="name" autoComplete="name" required placeholder="Your name" /></label>}
          <label>Email address<input name="email" type="email" autoComplete="email" required placeholder="you@example.com" /></label>
          <label>Password<input name="password" type="password" autoComplete={isRegister ? 'new-password' : 'current-password'} required minLength={8} placeholder="At least 8 characters" /></label>
          {isRegister && <label>Confirm password<input name="confirmPassword" type="password" autoComplete="new-password" required minLength={8} placeholder="Enter your password again" /></label>}
          {isRegister && <div className="auth-unavailable" role="note"><LockKeyhole size={16} /><span><strong>Patient registration only</strong><br />Doctor accounts are created by a trusted administrator.</span></div>}
          <button className="button button-primary auth-submit" type="submit" disabled={submitting}>{submitting ? 'Please wait…' : isRegister ? 'Create patient account' : `Sign in as ${role === 'doctor' ? 'Doctor' : 'Patient'}`} <ArrowRight size={17} /></button>
        </form>

        {message && <p className={messageKind === 'error' ? 'inline-error' : 'inline-message'} role={messageKind === 'error' ? 'alert' : 'status'}>{message}</p>}

        {!isRegister && <div className="auth-unavailable"><LockKeyhole size={16} /><span><strong>Role-verified access</strong><br />Your account role is verified by the ClinOps-AI authentication service.</span></div>}
        {isRegister
          ? <p className="auth-switch">Already have an account? <Link to="/patient/login">Sign in</Link></p>
          : role === 'patient'
            ? <p className="auth-switch">New to ClinOps-AI? <Link to="/patient/register">Create a patient account</Link></p>
            : <p className="auth-switch">Need a doctor account? Contact your administrator.</p>}
      </section>
      <aside className="auth-aside">
        <div className="auth-aside-top"><ShieldCheck size={19} /><span>Designed around responsible care</span></div>
        <div className="auth-aside-copy"><span className="eyebrow">THE {role.toUpperCase()} WORKSPACE</span><h2>{role === 'doctor' ? 'Less time navigating. More time caring.' : 'Your care information, in one place.'}</h2><p>{role === 'doctor' ? 'Review assigned patient records and consultation workflows in a clear, considered space.' : 'Access information that your care team has shared with your patient account.'}</p></div>
        <div className="auth-aside-footer"><span>SECURE ROLE CHECK</span><strong>{role === 'doctor' ? 'Doctor account required' : 'Patient account required'}</strong><p>The backend verifies your actual account role before granting access.</p></div>
      </aside>
    </main>
  );
}
