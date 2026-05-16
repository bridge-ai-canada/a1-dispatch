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
                <Routes>
                    <Route path="/" element={<HomeRouter />} />
                    <Route path="/login" element={<Login />} />
                    <Route path="/register" element={<Register />} />
                    <Route path="/forgot" element={<ForgotPassword />} />
                    <Route path="/reset" element={<ResetPassword />} />
                    <Route path="/setup-mfa" element={<SetupMFA />} />
                    <Route path="/payment/result" element={<PaymentResult />} />
                    <Route path="/book/:companyId" element={<BookingWidget />} />

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
                        <Route path="my-jobs" element={<MyJobs />} />
                        <Route path="settings" element={<Settings />} />
                        <Route path="admin/users" element={<AdminUsers />} />
                        <Route path="admin/activity" element={<Activity />} />
                    </Route>

                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </BrowserRouter>
        </AuthProvider>
    );
}

export default App;
