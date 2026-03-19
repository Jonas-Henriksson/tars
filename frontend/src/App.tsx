/**
 * TARS — Main app component with routing.
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useStore } from './store';
import AppLayout from './layouts/AppLayout';
import Login from './pages/Login';
import CommandCenter from './pages/CommandCenter';
import Work from './pages/Work';
import Strategy from './pages/Strategy';
import People from './pages/People';
import SettingsPage from './pages/SettingsPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token } = useStore();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<CommandCenter />} />
          <Route path="/work" element={<Work />} />
          <Route path="/strategy" element={<Strategy />} />
          <Route path="/people" element={<People />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
