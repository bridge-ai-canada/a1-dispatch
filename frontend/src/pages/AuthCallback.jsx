// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";
import { redirectFor } from "./Login";
import Brand from "../components/Brand";

export default function AuthCallback() {
    const navigate = useNavigate();
    const processed = useRef(false);
    const [error, setError] = useState("");

    useEffect(() => {
        if (processed.current) return;
        processed.current = true;
        const hash = window.location.hash || "";
        const m = hash.match(/session_id=([^&]+)/);
        const sessionId = m ? decodeURIComponent(m[1]) : null;
        // Strip fragment from URL
        window.history.replaceState({}, document.title, window.location.pathname + window.location.search);
        if (!sessionId) { navigate("/login", { replace: true }); return; }
        (async () => {
            try {
                const { data } = await api.post("/auth/google/exchange", { session_id: sessionId });
                window.location.href = redirectFor(data.user); // hard redirect to refresh AuthContext
            } catch (err) {
                const detail = err.response?.data?.detail || "";
                if (detail === "mfa_required") {
                    setError("Two-factor required. Please sign in with your password to verify.");
                    setTimeout(() => navigate("/login", { replace: true }), 2000);
                } else {
                    setError(detail || "Sign-in failed");
                    setTimeout(() => navigate("/login", { replace: true }), 2500);
                }
            }
        })();
    }, [navigate]);

    return (
        <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
            <div className="text-center">
                <div className="mb-6 flex justify-center"><Brand /></div>
                {error ? (
                    <div className="text-sm text-[#DC2626] border-l-2 border-[#DC2626] pl-3 py-1 max-w-sm mx-auto">{error}</div>
                ) : (
                    <>
                        <div className="h-10 w-10 mx-auto border-2 border-slate-200 border-t-[#1D4ED8] rounded-full animate-spin" />
                        <div className="mt-4 text-sm text-slate-500">Completing sign-in...</div>
                    </>
                )}
            </div>
        </div>
    );
}

export function startGoogleLogin(targetPath = "/auth/callback") {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + targetPath;
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
}
