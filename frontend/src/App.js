import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { Toaster } from "sonner";
import Layout, { Protected } from "./components/Layout";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Jobs from "./pages/Jobs";
import Schedule from "./pages/Schedule";
import Team from "./pages/Team";
import Customers from "./pages/Customers";
import CustomerDetail from "./pages/CustomerDetail";
import MyJobs from "./pages/MyJobs";
import Settings from "./pages/Settings";
import PaymentResult from "./pages/PaymentResult";
import JobDetail from "./pages/JobDetail";
import BookingWidget from "./pages/BookingWidget";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import SetupMFA from "./pages/SetupMFA";
import AdminUsers from "./pages/AdminUsers";
import Activity from "./pages/Activity";
import AuthCallback from "./pages/AuthCallback";
import VerifyEmail from "./pages/VerifyEmail";
import Portal from "./pages/Portal";
import RecurringJobs from "./pages/RecurringJobs";
import Reports from "./pages/Reports";
import Dispatch from "./pages/Dispatch";
import NotificationPrefs from "./pages/NotificationPrefs";
import Estimates from "./pages/Estimates";
import EstimateBuilder from "./pages/EstimateBuilder";
import EstimateDetail from "./pages/EstimateDetail";
import Invoices from "./pages/Invoices";
import InvoiceBuilder from "./pages/InvoiceBuilder";
import InvoiceDetail from "./pages/InvoiceDetail";
import Templates from "./pages/Templates";
import AICenter from "./pages/AICenter";
import Pipeline from "./pages/Pipeline";
import PublicEstimate from "./pages/PublicEstimate";
import PublicInvoice from "./pages/PublicInvoice";
import BrandingSettings from "./pages/BrandingSettings";
import Branches from "./pages/Branches";
import MessageTemplates from "./pages/MessageTemplates";
import Subscription from "./pages/Subscription";
import SuperTenants from "./pages/SuperTenants";
import ApiKeys from "./pages/ApiKeys";
import Pricing from "./pages/Pricing";
import TenantLanding from "./pages/TenantLanding";
import FinancingApply from "./pages/FinancingApply";
import FinancingContractor from "./pages/FinancingContractor";
import FinancingAdmin from "./pages/FinancingAdmin";

function HashGuard({ children }) {
    // Per Emergent Auth playbook: detect session_id synchronously during render
    if (typeof window !== "undefined" && window.location.hash?.includes("session_id=")) {
        return <AuthCallback />;
    }
    return children;
}

function HomeRouter() {
    const { user, loading } = useAuth();
    if (loading) return null;
    if (user) return <Navigate to="/app/dashboard" replace />;
    return <Landing />;
}

function App() {
    return (
        <AuthProvider>
            <BrowserRouter>
                <Toaster position="top-right" richColors />
                <HashGuard>
                <Routes>
                    <Route path="/" element={<HomeRouter />} />
                    <Route path="/login" element={<Login />} />
                    <Route path="/register" element={<Register />} />
                    <Route path="/forgot" element={<ForgotPassword />} />
                    <Route path="/reset" element={<ResetPassword />} />
                    <Route path="/setup-mfa" element={<SetupMFA />} />
                    <Route path="/verify" element={<VerifyEmail />} />
                    <Route path="/auth/callback" element={<AuthCallback />} />
                    <Route path="/portal" element={<Portal />} />
                    <Route path="/payment/result" element={<PaymentResult />} />
                    <Route path="/book/:companyId" element={<BookingWidget />} />
                    <Route path="/proposal/:token" element={<PublicEstimate />} />
                    <Route path="/pay/:token" element={<PublicInvoice />} />
                    <Route path="/pricing" element={<Pricing />} />
                    <Route path="/site/:companyId" element={<TenantLanding />} />
                    <Route path="/site" element={<TenantLanding />} />
                    <Route path="/finance/:token" element={<FinancingApply />} />

                    <Route
                        path="/app"
                        element={
                            <Protected>
                                <Layout />
                            </Protected>
                        }
                    >
                        <Route index element={<Navigate to="dashboard" replace />} />
                        <Route path="dashboard" element={<Dashboard />} />
                        <Route path="jobs" element={<Jobs />} />
                        <Route path="jobs/:id" element={<JobDetail />} />
                        <Route path="schedule" element={<Schedule />} />
                        <Route path="team" element={<Team />} />
                        <Route path="customers" element={<Customers />} />
                        <Route path="customers/:id" element={<CustomerDetail />} />
                        <Route path="my-jobs" element={<MyJobs />} />
                        <Route path="settings" element={<Settings />} />
                        <Route path="admin/users" element={<AdminUsers />} />
                        <Route path="admin/activity" element={<Activity />} />
                        <Route path="recurring" element={<RecurringJobs />} />
                        <Route path="reports" element={<Reports />} />
                        <Route path="dispatch" element={<Dispatch />} />
                        <Route path="estimates" element={<Estimates />} />
                        <Route path="estimates/new" element={<EstimateBuilder />} />
                        <Route path="estimates/:id" element={<EstimateDetail />} />
                        <Route path="estimates/:id/edit" element={<EstimateBuilder />} />
                        <Route path="invoices" element={<Invoices />} />
                        <Route path="invoices/new" element={<InvoiceBuilder />} />
                        <Route path="invoices/:id" element={<InvoiceDetail />} />
                        <Route path="invoices/:id/edit" element={<InvoiceBuilder />} />
                        <Route path="templates" element={<Templates />} />
                        <Route path="ai" element={<AICenter />} />
                        <Route path="pipeline" element={<Pipeline />} />
                        <Route path="notifications" element={<NotificationPrefs />} />
                        <Route path="settings/branding" element={<BrandingSettings />} />
                        <Route path="settings/branches" element={<Branches />} />
                        <Route path="settings/templates" element={<MessageTemplates />} />
                        <Route path="settings/subscription" element={<Subscription />} />
                        <Route path="settings/api-keys" element={<ApiKeys />} />
                        <Route path="super/tenants" element={<SuperTenants />} />
                        <Route path="financing" element={<FinancingContractor />} />
                        <Route path="admin/financing" element={<FinancingAdmin />} />
                    </Route>

                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
                </HashGuard>
            </BrowserRouter>
        </AuthProvider>
    );
}

export default App;
