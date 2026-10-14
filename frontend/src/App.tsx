import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import ProtectedRoute from './auth/ProtectedRoute';
import AppLayout from './layouts/AppLayout';
import AuthPage from './pages/AuthPage';
import LoginLandingPage from './pages/LoginLandingPage';
import {
  DoctorDashboard,
  DoctorPatientDirectory,
  DoctorPatientRecord,
  DoctorConsultations,
  DoctorPrescriptions,
  DoctorUnavailablePage,
} from './pages/DoctorPages';
import ConsultationDetailPage from './pages/ConsultationDetailPage';
import HomePage from './pages/HomePage';
import { PatientPortalPage } from './pages/PatientPages';

function DoctorRoutes() {
  return (
    <AppLayout portal="doctor">
      <Routes>
        <Route path="dashboard" element={<DoctorDashboard />} />
        <Route path="patients" element={<DoctorPatientDirectory />} />
        <Route path="patients/:patientId" element={<DoctorPatientRecord />} />
        <Route path="consultations" element={<DoctorConsultations />} />
        <Route path="consultations/new" element={<div className="legacy-workflow"><HomePage /></div>} />
        <Route path="consultations/:consultationId" element={<ConsultationDetailPage />} />
        <Route path="prescriptions" element={<DoctorPrescriptions />} />
        <Route path="appointments" element={<DoctorUnavailablePage feature="Appointments" />} />
        <Route path="tests" element={<DoctorUnavailablePage feature="Tests and results" />} />
        <Route path="settings" element={<DoctorUnavailablePage feature="Settings" />} />
        <Route path="*" element={<Navigate to="/doctor/dashboard" replace />} />
      </Routes>
    </AppLayout>
  );
}

function PatientRoutes() {
  return (
    <AppLayout portal="patient">
      <Routes>
        <Route path="dashboard" element={<PatientPortalPage section="dashboard" />} />
        <Route path="history" element={<PatientPortalPage section="history" />} />
        <Route path="consultations" element={<PatientPortalPage section="consultations" />} />
        <Route path="prescriptions" element={<PatientPortalPage section="prescriptions" />} />
        <Route path="tests" element={<PatientPortalPage section="tests" />} />
        <Route path="appointments" element={<PatientPortalPage section="appointments" />} />
        <Route path="profile" element={<PatientPortalPage section="profile" />} />
        <Route path="*" element={<Navigate to="/patient/dashboard" replace />} />
      </Routes>
    </AppLayout>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginLandingPage />} />
      <Route path="/doctor/login" element={<AuthPage mode="login" role="doctor" />} />
      <Route path="/patient/login" element={<AuthPage mode="login" role="patient" />} />
      <Route path="/patient/register" element={<AuthPage mode="register" role="patient" />} />
      <Route path="/register" element={<Navigate to="/patient/register" replace />} />
      <Route path="/doctor" element={<Navigate to="/doctor/login" replace />} />
      <Route path="/patient" element={<Navigate to="/patient/login" replace />} />
      <Route path="/doctor/*" element={<ProtectedRoute role="doctor"><DoctorRoutes /></ProtectedRoute>} />
      <Route path="/patient/*" element={<ProtectedRoute role="patient"><PatientRoutes /></ProtectedRoute>} />
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
