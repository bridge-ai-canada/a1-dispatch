import { useEffect, useState, useRef } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import {
    Coffee, CarSimple, Wrench, MoonStars, CheckCircle, NavigationArrow,
} from "@phosphor-icons/react";

const STATUSES = [
    { key: "available",  label: "Available",  icon: CheckCircle,    color: "#16A34A" },
    { key: "on_route",   label: "On route",   icon: CarSimple,      color: "#1D4ED8" },
    { key: "on_site",    label: "On site",    icon: Wrench,         color: "#D97706" },
    { key: "break",      label: "Break",      icon: Coffee,         color: "#94A3B8" },
    { key: "off_duty",   label: "Off duty",   icon: MoonStars,      color: "#475569" },
];

const GPS_KEY = "a1.gps.on";

export default function TechStatusBar({ jobs }) {
    const [status, setStatus] = useState("available");
    const [gpsOn, setGpsOn] = useState(() => {
        try { return localStorage.getItem(GPS_KEY) === "1"; } catch { return false; }
    });
    const watchIdRef = useRef(null);
    const intervalRef = useRef(null);
    const lastPingRef = useRef(0);

    const hasInProgress = (jobs || []).some((j) => j.status === "in_progress");

    useEffect(() => {
        api.get("/auth/me").then((r) => setStatus(r.data.user.tech_status || "available")).catch(() => {});
    }, []);

    const setRemoteStatus = async (s) => {
        setStatus(s);
        try { await api.post("/me/status", { status: s }); }
        catch { toast.error("Could not update status"); }
    };

    // GPS — only ping while at least one job is in_progress AND opt-in flag is on
    useEffect(() => {
        const shouldTrack = gpsOn && hasInProgress;
        const stop = () => {
            if (watchIdRef.current && navigator.geolocation) {
                navigator.geolocation.clearWatch(watchIdRef.current);
                watchIdRef.current = null;
            }
            if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
        };
        if (!shouldTrack || !("geolocation" in navigator)) { stop(); return; }

        const ping = (lat, lng, acc) => {
            const now = Date.now();
            if (now - lastPingRef.current < 30_000) return; // throttle to ~30s
            lastPingRef.current = now;
            api.post("/me/location", { latitude: lat, longitude: lng, accuracy_m: acc }).catch(() => {});
        };

        watchIdRef.current = navigator.geolocation.watchPosition(
            (pos) => ping(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy),
            () => {}, { enableHighAccuracy: true, maximumAge: 30_000 },
        );
        // also fallback poll every 60s
        intervalRef.current = setInterval(() => {
            navigator.geolocation.getCurrentPosition(
                (pos) => ping(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy),
                () => {},
            );
        }, 60_000);
        return stop;
    }, [gpsOn, hasInProgress]);

    const toggleGps = () => {
        const next = !gpsOn;
        try { localStorage.setItem(GPS_KEY, next ? "1" : "0"); } catch (_) {}
        if (next && "geolocation" in navigator) {
            // prompt for permission immediately
            navigator.geolocation.getCurrentPosition(() => {}, () => {
                toast.error("Location permission denied");
            });
        }
        setGpsOn(next);
    };

    return (
        <div data-testid="tech-status-bar"
            className="border border-slate-200 bg-white p-4">
            <div className="overline mb-3">My status</div>
            <div className="flex flex-wrap gap-2">
                {STATUSES.map((s) => {
                    const Icon = s.icon;
                    const active = status === s.key;
                    return (
                        <button key={s.key} onClick={() => setRemoteStatus(s.key)}
                            data-testid={`tech-status-${s.key}`}
                            style={active ? { backgroundColor: s.color, color: "#fff", borderColor: s.color } : {}}
                            className={`flex items-center gap-1.5 px-3 py-2 border text-xs font-semibold transition-colors
                                ${active ? "" : "border-slate-300 hover:bg-slate-50 text-slate-700"}`}>
                            <Icon size={14} weight={active ? "fill" : "regular"} />
                            {s.label}
                        </button>
                    );
                })}
            </div>
            <div className="mt-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <NavigationArrow size={16} className={gpsOn && hasInProgress ? "text-emerald-600" : "text-slate-400"} weight="duotone" />
                    <div>
                        <div className="text-xs font-semibold">Live GPS</div>
                        <div className="text-[11px] text-slate-500">
                            {gpsOn ? (hasInProgress ? "Sharing while a job is in progress" : "On — will share when you start a job") : "Off"}
                        </div>
                    </div>
                </div>
                <button onClick={toggleGps} data-testid="tech-gps-toggle"
                    className={`relative w-11 h-6 transition-colors ${gpsOn ? "bg-emerald-600" : "bg-slate-300"}`}>
                    <span className={`absolute top-0.5 ${gpsOn ? "left-6" : "left-0.5"} w-5 h-5 bg-white transition-all`} />
                </button>
            </div>
        </div>
    );
}
