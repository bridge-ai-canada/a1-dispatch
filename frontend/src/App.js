import "@/App.css";
import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { CommandPaletteProvider } from "./context/CommandPaletteContext";
import { Toaster } from "sonner";
import Layout, { Protected } from "./components/Layout";
import RouteErrorBoundary from "./components/RouteErrorBoundary";

// --- Eager: auth + public pages (small, needed on first paint) ---
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import SetupMFA from "./pages/SetupMFA";
import VerifyEmail from "./pages/VerifyEmail";
import AuthCallback from "./pages/AuthCallback";

// --- Lazy: everything authenticated. Bundle-split per page route. ---
const Dashboard          = lazy(() => import("./pages/Dashboard"));
const Jobs               = lazy(() => import("./pages/Jobs"));
const JobDetail          = lazy(() => import("./pages/JobDetail"));
const Schedule           = lazy(() => import("./pages/Schedule"));
const Team               = lazy(() => import("./pages/Team"));
const Customers          = lazy(() => import("./pages/Customers"));
const CustomerDetail     = lazy(() => import("./pages/CustomerDetail"));
const MyJobs             = lazy(() => import("./pages/MyJobs"));
const Settings           = lazy(() => import("./pages/Settings"));
const AdminUsers         = lazy(() => import("./pages/AdminUsers"));
const Activity           = lazy(() => import("./pages/Activity"));
const RecurringJobs      = lazy(() => import("./pages/RecurringJobs"));
const Reports            = lazy(() => import("./pages/Reports"));
const Dispatch           = lazy(() => import("./pages/Dispatch"));
const NotificationPrefs  = lazy(() => import("./pages/NotificationPrefs"));
const Estimates          = lazy(() => import("./pages/Estimates"));
const EstimateBuilder    = lazy(() => import("./pages/EstimateBuilder"));
const EstimateDetail     = lazy(() => import("./pages/EstimateDetail"));
const Invoices           = lazy(() => import("./pages/Invoices"));
const InvoiceBuilder     = lazy(() => import("./pages/InvoiceBuilder"));
const InvoiceDetail      = lazy(() => import("./pages/InvoiceDetail"));
const Templates          = lazy(() => import("./pages/Templates"));
const Checklists         = lazy(() => import("./pages/Checklists"));
const AICenter           = lazy(() => import("./pages/AICenter"));
const Pipeline           = lazy(() => import("./pages/Pipeline"));
const BrandingSettings   = lazy(() => import("./pages/BrandingSettings"));
const Branches           = lazy(() => import("./pages/Branches"));
const MessageTemplates   = lazy(() => import("./pages/MessageTemplates"));
const Subscription       = lazy(() => import("./pages/Subscription"));
const SuperTenants       = lazy(() => import("./pages/SuperTenants"));
const ApiKeys            = lazy(() => import("./pages/ApiKeys"));
const FinancingContractor= lazy(() => import("./pages/FinancingContractor"));
const FinancingAdmin     = lazy(() => import("./pages/FinancingAdmin"));
const FinancingPrograms  = lazy(() => import("./pages/FinancingPrograms"));
const Analytics          = lazy(() => import("./pages/Analytics"));
const Integrations       = lazy(() => import("./pages/Integrations"));
const Webhooks           = lazy(() => import("./pages/Webhooks"));

// --- Lazy public pages (heavy but rare) ---
const Portal          = lazy(() => import("./pages/Portal"));
const PaymentResult   = lazy(() => import("./pages/PaymentResult"));
const BookingWidget   = lazy(() => import("./pages/BookingWidget"));
const PublicEstimate  = lazy(() => import("./pages/PublicEstimate"));
const PublicInvoice   = lazy(() => import("./pages/PublicInvoice"));
const Pricing         = lazy(() => import("./pages/Pricing"));
const TenantLanding   = lazy(() => import("./pages/TenantLanding"));
const FinancingApply  = lazy(() => import("./pages/FinancingApply"));

function HashGuard({ children }) {
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

function RouteFallback() {
    return (
        <div className="min-h-[40vh] flex items-center justify-center" data-testid="route-loading">
            <div className="h-9 w-9 border-2 border-slate-200 border-t-[#1D4ED8] rounded-full animate-spin" />
        </div>
    );
}

function App() {
    return (
        <AuthProvider>
            <CommandPaletteProvider>
            <BrowserRouter>
                <Toaster position="top-right" richColors closeButton />
                <HashGuard>
                <RouteErrorBoundary>
                <Suspense fallback={<RouteFallback />}>
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
                        element={<Protected><Layout /></Protected>}
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
                        <Route path="analytics" element={<Analytics />} />
                        <Route path="integrations" element={<Integrations />} />
                        <Route path="integrations/webhooks" element={<Webhooks />} />
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
                        <Route path="checklists" element={<Checklists />} />
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
                        <Route path="financing/programs" element={<FinancingPrograms />} />
                        <Route path="admin/financing" element={<FinancingAdmin />} />
                    </Route>

                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
                </Suspense>
                </RouteErrorBoundary>
                </HashGuard>
            </BrowserRouter>
            </CommandPaletteProvider>
        </AuthProvider>
    );
}

export default App;
