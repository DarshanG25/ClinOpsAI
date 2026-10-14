import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider } from '../auth/AuthContext';
import { AppRoutes } from '../App';
import type { AuthUser } from '../services/auth';

const auth = vi.hoisted(() => ({
  clearAccessToken: vi.fn(),
  getAccessToken: vi.fn(),
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  registerPatient: vi.fn(),
  storeAccessToken: vi.fn(),
}));

vi.mock('../services/auth', () => auth);
vi.mock('../services/api', () => ({
  listPatients: vi.fn().mockResolvedValue([]),
  listConsultations: vi.fn().mockResolvedValue([]),
  getPrescription: vi.fn(),
}));

const doctor: AuthUser = {
  id: 'doctor-1',
  name: 'Dr Example',
  email: 'doctor@example.test',
  role: 'doctor',
  is_active: true,
};

const patient: AuthUser = {
  id: 'patient-1',
  name: 'Patient Example',
  email: 'patient@example.test',
  role: 'patient',
  is_active: true,
};

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </MemoryRouter>,
  );
}

function axiosFailure(status?: number) {
  return Object.assign(new Error('request failed'), {
    isAxiosError: true,
    ...(status ? { response: { status, data: { detail: 'Backend detail that should not be shown for this status.' } } } : {}),
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  auth.getAccessToken.mockReturnValue(null);
  auth.getCurrentUser.mockResolvedValue(doctor);
});

afterEach(() => {
  window.sessionStorage.clear();
});

describe('role-specific authentication routes', () => {
  it('offers two separate login choices from the login landing page', () => {
    renderRoute('/login');

    expect(screen.getByRole('heading', { name: 'How would you like to continue?' })).toBeTruthy();
    expect(screen.getByRole('link', { name: /Continue as Doctor/ }).getAttribute('href')).toBe('/doctor/login');
    expect(screen.getByRole('link', { name: /Continue as Patient/ }).getAttribute('href')).toBe('/patient/login');
  });

  it('renders doctor login without a role selector', () => {
    renderRoute('/doctor/login');

    expect(screen.getByRole('heading', { name: 'Doctor sign in' })).toBeTruthy();
    expect(screen.getByLabelText('Email address')).toBeTruthy();
    expect(screen.getByLabelText('Password')).toBeTruthy();
    expect(screen.queryByRole('group')).toBeNull();
    expect(screen.getByRole('link', { name: 'Choose a different sign-in' })).toBeTruthy();
  });

  it('renders a separate patient login and patient-only registration route', () => {
    renderRoute('/patient/login');

    expect(screen.getByRole('heading', { name: 'Patient sign in' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Create a patient account' }).getAttribute('href')).toBe('/patient/register');
  });

  it('keeps the legacy registration URL patient-only and removes role selection', () => {
    renderRoute('/register');

    expect(screen.getByRole('heading', { name: 'Create your patient account' })).toBeTruthy();
    expect(screen.queryByRole('group')).toBeNull();
    expect(screen.getByText('Patient registration only')).toBeTruthy();
  });

  it.each([
    [doctor, '/doctor/login', /Good to see you/i],
    [patient, '/patient/login', /your health, in one place/i],
  ])('navigates the authenticated %s account to its own portal', async (account, path, destination) => {
    const user = userEvent.setup();
    auth.login.mockResolvedValue({ access_token: 'test-token', token_type: 'bearer', user: account });
    renderRoute(path);

    await user.type(screen.getByLabelText('Email address'), account.email);
    await user.type(screen.getByLabelText('Password'), 'example-password');
    await user.click(screen.getByRole('button', { name: /Sign in as/ }));

    expect(await screen.findByText(destination)).toBeTruthy();
    expect(auth.login).toHaveBeenCalledWith(account.email, 'example-password');
    expect(auth.storeAccessToken).toHaveBeenCalledWith('test-token');
  });

  it.each([
    [doctor, '/patient/login', /uses the doctor workspace/i],
    [patient, '/doctor/login', /uses the patient workspace/i],
  ])('rejects the wrong authenticated account role without storing its token', async (account, path, message) => {
    const user = userEvent.setup();
    auth.login.mockResolvedValue({ access_token: 'not-stored', token_type: 'bearer', user: account });
    renderRoute(path);

    await user.type(screen.getByLabelText('Email address'), account.email);
    await user.type(screen.getByLabelText('Password'), 'example-password');
    await user.click(screen.getByRole('button', { name: /Sign in as/ }));

    expect((await screen.findByRole('alert')).textContent).toMatch(message);
    expect(auth.storeAccessToken).not.toHaveBeenCalled();
  });

  it('shows a safe invalid-credentials message for HTTP 401', async () => {
    const user = userEvent.setup();
    auth.login.mockRejectedValue(axiosFailure(401));
    renderRoute('/doctor/login');

    await user.type(screen.getByLabelText('Email address'), 'wrong@example.test');
    await user.type(screen.getByLabelText('Password'), 'wrong-password');
    await user.click(screen.getByRole('button', { name: /Sign in as Doctor/ }));

    expect((await screen.findByRole('alert')).textContent).toContain('Email or password is incorrect.');
    expect(screen.queryByText(/Backend detail/)).toBeNull();
  });

  it('shows a connection-specific message when the login API cannot be reached', async () => {
    const user = userEvent.setup();
    auth.login.mockRejectedValue(axiosFailure());
    renderRoute('/patient/login');

    await user.type(screen.getByLabelText('Email address'), 'patient@example.test');
    await user.type(screen.getByLabelText('Password'), 'example-password');
    await user.click(screen.getByRole('button', { name: /Sign in as Patient/ }));

    expect((await screen.findByRole('alert')).textContent).toContain('could not reach the sign-in service');
  });

  it('shows the safe backend permission message for HTTP 403', async () => {
    const user = userEvent.setup();
    auth.login.mockRejectedValue(axiosFailure(403));
    renderRoute('/doctor/login');

    await user.type(screen.getByLabelText('Email address'), 'doctor@example.test');
    await user.type(screen.getByLabelText('Password'), 'example-password');
    await user.click(screen.getByRole('button', { name: /Sign in as Doctor/ }));

    expect((await screen.findByRole('alert')).textContent).toContain('not permitted to sign in to the doctor workspace');
  });

  it('restores the saved session on a direct dashboard visit', async () => {
    auth.getAccessToken.mockReturnValue('saved-session');
    auth.getCurrentUser.mockResolvedValue(patient);
    renderRoute('/patient/dashboard');

    expect(await screen.findByText(/Your health, in one place/)).toBeTruthy();
    expect(auth.getCurrentUser).toHaveBeenCalledOnce();
  });

  it('clears the session and returns to role selection on logout', async () => {
    const user = userEvent.setup();
    auth.getAccessToken.mockReturnValue('saved-session');
    auth.getCurrentUser.mockResolvedValue(doctor);
    renderRoute('/doctor/dashboard');

    await user.click((await screen.findAllByRole('button', { name: 'Sign out' }))[0]);

    expect(await screen.findByRole('heading', { name: 'How would you like to continue?' })).toBeTruthy();
    expect(auth.clearAccessToken).toHaveBeenCalledOnce();
  });

  it.each([
    ['/doctor/patients', 'Doctor sign in'],
    ['/patient/prescriptions', 'Patient sign in'],
  ])('redirects unauthenticated direct visits to the matching login route', async (path, heading) => {
    renderRoute(path);

    await waitFor(() => expect(screen.getByRole('heading', { name: heading })).toBeTruthy());
  });
});
