import { useEffect, useState, useCallback } from "react";
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, ActivityIndicator, Alert } from "react-native";
import { api } from "../../lib/api";
import { useTheme } from "../../lib/theme";
import { useFocusEffect } from "expo-router";

type Shift = {
    id: string;
    started_at: string;
    ended_at?: string | null;
    break_minutes: number;
    total_minutes: number;
};

function fmtTime(iso?: string | null) {
    if (!iso) return "—";
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
function fmtDate(iso?: string | null) {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
}
function fmtMinutes(m: number) {
    const h = Math.floor(m / 60);
    const mm = m % 60;
    return `${h}h ${mm}m`;
}

function liveElapsed(iso: string, breakMin: number) {
    const start = new Date(iso).getTime();
    return Math.max(0, Math.floor((Date.now() - start) / 60_000) - (breakMin || 0));
}

export default function Timesheet() {
    const { palette } = useTheme();
    const [active, setActive] = useState<Shift | null>(null);
    const [history, setHistory] = useState<Shift[]>([]);
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);
    const [tick, setTick] = useState(0);

    const load = useCallback(async () => {
        try {
            const [a, h] = await Promise.all([
                api.get("/timesheets/active"),
                api.get("/timesheets"),
            ]);
            setActive(a.data.active);
            setHistory(h.data || []);
        } catch (_) {}
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);
    useFocusEffect(useCallback(() => { load(); }, [load]));

    useEffect(() => {
        if (!active) return;
        const t = setInterval(() => setTick((x) => x + 1), 30_000);
        return () => clearInterval(t);
    }, [active]);

    const clockIn = async () => {
        setBusy(true);
        try {
            await api.post("/timesheets/clock-in");
            await load();
        } catch (e: any) {
            Alert.alert("Failed", e.response?.data?.detail || "Try again");
        } finally { setBusy(false); }
    };
    const clockOut = async () => {
        setBusy(true);
        try {
            await api.post("/timesheets/clock-out");
            await load();
        } catch (e: any) {
            Alert.alert("Failed", e.response?.data?.detail || "Try again");
        } finally { setBusy(false); }
    };
    const addBreak = async (mins: number) => {
        try {
            await api.post("/timesheets/break", { minutes: mins });
            await load();
        } catch (e: any) {
            Alert.alert("Failed", e.response?.data?.detail || "Try again");
        }
    };

    if (loading) {
        return <View style={[s.center, { backgroundColor: palette.soft }]}><ActivityIndicator color={palette.primary} /></View>;
    }

    const today = new Date().toISOString().slice(0, 10);
    const todayMin = history
        .filter((sh) => sh.ended_at && sh.started_at.startsWith(today))
        .reduce((sum, sh) => sum + (sh.total_minutes || 0), 0)
        + (active ? liveElapsed(active.started_at, active.break_minutes) : 0);

    const weekStart = new Date(); weekStart.setDate(weekStart.getDate() - weekStart.getDay()); weekStart.setHours(0, 0, 0, 0);
    const weekMin = history
        .filter((sh) => sh.ended_at && new Date(sh.started_at) >= weekStart)
        .reduce((sum, sh) => sum + (sh.total_minutes || 0), 0)
        + (active && new Date(active.started_at) >= weekStart ? liveElapsed(active.started_at, active.break_minutes) : 0);

    return (
        <ScrollView style={{ backgroundColor: palette.soft }} contentContainerStyle={{ padding: 16, paddingBottom: 32 }}>
            {/* Big clock-in / clock-out */}
            {active ? (
                <View style={[s.heroCard, { backgroundColor: palette.ok, borderColor: palette.ok }]}>
                    <Text style={s.heroKicker}>ON THE CLOCK</Text>
                    <Text style={s.heroBigTime}>{fmtMinutes(liveElapsed(active.started_at, active.break_minutes))}</Text>
                    <Text style={s.heroMeta}>Started at {fmtTime(active.started_at)}{active.break_minutes ? `  ·  ${active.break_minutes}m break` : ""}</Text>
                    <View style={{ flexDirection: "row", gap: 8, marginTop: 16 }}>
                        <TouchableOpacity onPress={() => addBreak(15)} style={[s.heroBtnGhost]}>
                            <Text style={s.heroBtnGhostText}>+ 15m break</Text>
                        </TouchableOpacity>
                        <TouchableOpacity onPress={() => addBreak(30)} style={[s.heroBtnGhost]}>
                            <Text style={s.heroBtnGhostText}>+ 30m break</Text>
                        </TouchableOpacity>
                    </View>
                    <TouchableOpacity onPress={clockOut} disabled={busy}
                        style={[s.heroBtnSolid, { backgroundColor: "#fff", marginTop: 12 }]}
                        accessibilityLabel="Clock out">
                        <Text style={[s.heroBtnSolidText, { color: palette.ok }]}>
                            {busy ? "Clocking out…" : "🛑  Clock out"}
                        </Text>
                    </TouchableOpacity>
                </View>
            ) : (
                <View style={[s.heroCard, { backgroundColor: palette.paper, borderColor: palette.line, borderWidth: 1 }]}>
                    <Text style={[s.heroKickerDark, { color: palette.accent }]}>OFF THE CLOCK</Text>
                    <Text style={[s.heroBigTime, { color: palette.ink }]}>Ready to start?</Text>
                    <TouchableOpacity onPress={clockIn} disabled={busy}
                        style={[s.heroBtnSolid, { backgroundColor: palette.ok, marginTop: 16 }]}>
                        <Text style={[s.heroBtnSolidText, { color: "#fff" }]}>
                            {busy ? "Clocking in…" : "▶  Clock in"}
                        </Text>
                    </TouchableOpacity>
                </View>
            )}

            {/* Totals */}
            <View style={s.totalsRow}>
                <View style={[s.totalCard, { backgroundColor: palette.paper, borderColor: palette.line }]}>
                    <Text style={[s.totalLabel, { color: palette.muted }]}>TODAY</Text>
                    <Text style={[s.totalValue, { color: palette.ink }]}>{fmtMinutes(todayMin)}</Text>
                </View>
                <View style={[s.totalCard, { backgroundColor: palette.paper, borderColor: palette.line }]}>
                    <Text style={[s.totalLabel, { color: palette.muted }]}>THIS WEEK</Text>
                    <Text style={[s.totalValue, { color: palette.ink }]}>{fmtMinutes(weekMin)}</Text>
                </View>
            </View>

            <Text style={[s.sectionHead, { color: palette.muted }]}>RECENT SHIFTS</Text>
            {history.length === 0 ? (
                <Text style={[s.emptyText, { color: palette.muted }]}>No shifts logged yet.</Text>
            ) : (
                history.slice(0, 14).map((sh) => (
                    <View key={sh.id} style={[s.rowItem, { backgroundColor: palette.paper, borderColor: palette.line }]}>
                        <View>
                            <Text style={[s.rowTitle, { color: palette.ink }]}>{fmtDate(sh.started_at)}</Text>
                            <Text style={[s.rowMeta, { color: palette.muted }]}>
                                {fmtTime(sh.started_at)} – {fmtTime(sh.ended_at)}
                                {sh.break_minutes ? `  ·  ${sh.break_minutes}m break` : ""}
                            </Text>
                        </View>
                        <Text style={[s.rowAmount, { color: sh.ended_at ? palette.ink : palette.warn }]}>
                            {sh.ended_at ? fmtMinutes(sh.total_minutes || 0) : "ACTIVE"}
                        </Text>
                    </View>
                ))
            )}
        </ScrollView>
    );
}

const s = StyleSheet.create({
    center: { flex: 1, alignItems: "center", justifyContent: "center" },
    heroCard: { padding: 24, borderRadius: 16, alignItems: "center" },
    heroKicker: { fontSize: 11, letterSpacing: 2, color: "#fff", fontWeight: "800" },
    heroKickerDark: { fontSize: 11, letterSpacing: 2, fontWeight: "800" },
    heroBigTime: { fontSize: 44, fontWeight: "900", color: "#fff", letterSpacing: -1, marginTop: 6 },
    heroMeta: { fontSize: 13, color: "#fff", opacity: 0.85, marginTop: 4 },
    heroBtnGhost: { flex: 1, paddingVertical: 12, alignItems: "center", borderWidth: 1, borderColor: "rgba(255,255,255,0.6)", borderRadius: 10 },
    heroBtnGhostText: { color: "#fff", fontWeight: "700", fontSize: 13 },
    heroBtnSolid: { width: "100%", paddingVertical: 16, alignItems: "center", borderRadius: 12 },
    heroBtnSolidText: { fontSize: 16, fontWeight: "800", letterSpacing: 0.5 },
    totalsRow: { flexDirection: "row", gap: 12, marginTop: 16 },
    totalCard: { flex: 1, padding: 14, borderRadius: 12, borderWidth: 1 },
    totalLabel: { fontSize: 10, letterSpacing: 1.4, fontWeight: "800" },
    totalValue: { fontSize: 22, fontWeight: "800", marginTop: 4, letterSpacing: -0.4, fontVariant: ["tabular-nums"] },
    sectionHead: { fontSize: 11, letterSpacing: 1.5, fontWeight: "800", marginTop: 24, marginBottom: 8 },
    rowItem: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 14, borderWidth: 1, borderRadius: 10, marginBottom: 8 },
    rowTitle: { fontSize: 14, fontWeight: "700" },
    rowMeta: { fontSize: 12, marginTop: 2 },
    rowAmount: { fontSize: 16, fontWeight: "800", fontVariant: ["tabular-nums"] },
    emptyText: { textAlign: "center", padding: 24, fontSize: 13 },
});
