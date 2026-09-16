import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import { useAuth } from "./hooks/useAuth";
import type { UserRole } from "./types";

import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import AdminDashboardPage from "./pages/AdminDashboardPage";
import TransactionsPage from "./pages/TransactionsPage";
import TransactionDetailPage from "./pages/TransactionDetailPage";
import AlertsPage from "./pages/AlertsPage";
import InvestigationPage from "./pages/InvestigationPage";
import CustomersPage from "./pages/CustomersPage";
import CustomerProfilePage from "./pages/CustomerProfilePage";
import FraudNetworkPage from "./pages/FraudNetworkPage";
import ReportsPage from "./pages/ReportsPage";
import RulesPage from "./pages/RulesPage";
import ApiKeysPage from "./pages/ApiKeysPage";
import AuditLogsPage from "./pages/AuditLogsPage";

function ProtectedRoute({ children }: { children: JSX.Element }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function RoleRoute({ roles, children }: { roles: UserRole[]; children: JSX.Element }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!roles.includes(user.role)) return <Navigate to="/dashboard" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route
          path="/admin-dashboard"
          element={
            <RoleRoute roles={["ADMIN"]}>
              <AdminDashboardPage />
            </RoleRoute>
          }
        />
        <Route path="/transactions" element={<TransactionsPage />} />
        <Route path="/transactions/:id" element={<TransactionDetailPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/alerts/:id" element={<InvestigationPage />} />
        <Route path="/customers" element={<CustomersPage />} />
        <Route path="/customers/:customerId" element={<CustomerProfilePage />} />
        <Route path="/fraud-network" element={<FraudNetworkPage />} />
        <Route path="/fraud-network/:customerId" element={<FraudNetworkPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route
          path="/rules"
          element={
            <RoleRoute roles={["ADMIN"]}>
              <RulesPage />
            </RoleRoute>
          }
        />
        <Route
          path="/api-keys"
          element={
            <RoleRoute roles={["ADMIN"]}>
              <ApiKeysPage />
            </RoleRoute>
          }
        />
        <Route
          path="/audit-logs"
          element={
            <RoleRoute roles={["ADMIN"]}>
              <AuditLogsPage />
            </RoleRoute>
          }
        />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
