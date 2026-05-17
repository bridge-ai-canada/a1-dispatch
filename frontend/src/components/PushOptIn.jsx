import { useEffect, useState } from "react";
import { toast } from "sonner";
import { BellRinging, BellSlash } from "@phosphor-icons/react";
import {
    isPushSupported, getPushPermission, subscribeToPush,
    unsubscribeFromPush, currentSubscription,
} from "../lib/push";
import api from "../lib/api";

export default function PushOptIn() {
    const [supported] = useState(isPushSupported());
    const [enabled, setEnabled] = useState(false);
    const [busy, setBusy] = useState(false);
    const [perm, setPerm] = useState("default");

    const refresh = async () => {
        if (!supported) return;
        setPerm(await getPushPermission());
        const sub = await currentSubscription();
        setEnabled(!!sub);
    };

    useEffect(() => { refresh(); }, []);

    const enable = async () => {
        setBusy(true);
        try {
            await subscribeToPush();
            toast.success("Push notifications on. You'll be alerted for new jobs.");
            refresh();
        } catch (err) {
            toast.error(err.message || "Could not enable push");
        } finally {
            setBusy(false);
        }
    };

    const disable = async () => {
        setBusy(true);
        try {
            await unsubscribeFromPush();
            toast.info("Push notifications off");
            refresh();
        } catch (err) {
            toast.error("Could not disable push");
        } finally {
            setBusy(false);
        }
    };

    const sendTest = async () => {
        try {
            const { data } = await api.post("/push/test", { title: "Test push", body: "If you see this, you're all set." });
            toast.success(`Sent to ${data.sent} device(s)`);
        } catch (err) {
            toast.error(err.response?.data?.detail || "Test failed");
        }
    };

    if (!supported) return null;

    if (perm === "denied") {
        return (
            <div data-testid="push-blocked" className="border border-slate-200 bg-amber-50 p-4 text-sm text-amber-900">
                <strong>Notifications blocked.</strong> Enable them in your browser site settings to get new-job alerts.
            </div>
        );
    }

    return (
        <div data-testid="push-optin"
            className="border border-slate-200 bg-white p-4 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
                {enabled
                    ? <BellRinging size={22} weight="duotone" className="text-emerald-600 flex-shrink-0" />
                    : <BellSlash size={22} weight="duotone" className="text-slate-400 flex-shrink-0" />}
                <div className="min-w-0">
                    <div className="font-semibold text-sm">
                        {enabled ? "Push alerts on" : "Turn on push alerts"}
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">
                        {enabled
                            ? "You'll be pinged the second dispatch assigns or reschedules a job."
                            : "Get a notification on this device when a new job lands."}
                    </p>
                </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
                {enabled ? (
                    <>
                        <a href="/app/notifications" data-testid="push-prefs-link"
                            className="px-3 h-9 border border-slate-300 hover:bg-slate-50 text-xs font-semibold flex items-center">
                            Prefs
                        </a>
                        <button onClick={sendTest} data-testid="push-test"
                            className="px-3 h-9 border border-slate-300 hover:bg-slate-50 text-xs font-semibold">
                            Test
                        </button>
                        <button onClick={disable} disabled={busy} data-testid="push-disable"
                            className="px-3 h-9 border border-slate-300 hover:bg-red-50 hover:text-[#DC2626] text-xs font-semibold disabled:opacity-50">
                            Turn off
                        </button>
                    </>
                ) : (
                    <button onClick={enable} disabled={busy} data-testid="push-enable"
                        className="px-4 h-9 bg-[#1D4ED8] text-white text-xs font-semibold hover:opacity-90 disabled:opacity-50">
                        {busy ? "…" : "Enable"}
                    </button>
                )}
            </div>
        </div>
    );
}
