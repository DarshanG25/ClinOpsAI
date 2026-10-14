import api from './api';
export {
  clearAccessToken,
  getAccessToken,
  storeAccessToken,
} from './authToken';

export type AccountRole = 'doctor' | 'patient';

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: AccountRole;
  is_active: boolean;
}

interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
  user: AuthUser;
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>('/auth/login', { email, password });
  return data;
}

export async function registerPatient(
  name: string,
  email: string,
  password: string,
): Promise<AuthUser> {
  const { data } = await api.post<AuthUser>('/auth/register', {
    name,
    email,
    password,
    role: 'patient',
  });
  return data;
}

export async function getCurrentUser(): Promise<AuthUser> {
  const { data } = await api.get<AuthUser>('/auth/me');
  return data;
}
