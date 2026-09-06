import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import AppShell from "./components/AppShell";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ChatPage from "./pages/ChatPage";
import BrokerPage from "./pages/BrokerPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import NewsDigestPage from "./pages/NewsDigestPage";
import ThemedBasketsPage from "./pages/ThemedBasketsPage";
import AlertsPage from "./pages/AlertsPage";
import OptimizePage from "./pages/OptimizePage";

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return null;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
}

function PublicOnly({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return null;
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/" element={<PublicOnly><LandingPage /></PublicOnly>} />
      <Route path="/login" element={<PublicOnly><LoginPage /></PublicOnly>} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      {/* Protected — wrapped in AppShell */}
      <Route
        path="/dashboard"
        element={<ProtectedRoute><AppShell><DashboardPage /></AppShell></ProtectedRoute>}
      />
      <Route
        path="/chat"
        element={<ProtectedRoute><AppShell><ChatPage /></AppShell></ProtectedRoute>}
      />
      <Route
        path="/broker"
        element={<ProtectedRoute><AppShell><BrokerPage /></AppShell></ProtectedRoute>}
      />
      <Route
        path="/news"
        element={<ProtectedRoute><AppShell><NewsDigestPage /></AppShell></ProtectedRoute>}
      />
      <Route
        path="/baskets"
        element={<ProtectedRoute><AppShell><ThemedBasketsPage /></AppShell></ProtectedRoute>}
      />
      <Route
        path="/alerts"
        element={<ProtectedRoute><AppShell><AlertsPage /></AppShell></ProtectedRoute>}
      />
      <Route
        path="/optimize"
        element={<ProtectedRoute><AppShell><OptimizePage /></AppShell></ProtectedRoute>}
      />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
