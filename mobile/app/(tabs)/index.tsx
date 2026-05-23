import { useEffect, useState, useCallback } from "react";
import { View, Text, FlatList, RefreshControl, StyleSheet, TouchableOpacity, ActivityIndicator } from "react-native";
import { api } from "../../lib/api";
import { useTheme } from "../../lib/theme";
import { useRouter, useFocusEffect } from "expo-router";
import { queueSize, flush } from "../../lib/queue";

type Job = {
    id: string;
    title: string;
    status: string;
    address?: string;
    customer_name?: string;
    customer_phone?: string;
    scheduled_at?: string;
    duration_min?: number;
    price?: number;
    priority?: string;
};

export default function TodayScreen() {
    return <JobList scope="today" emptyLabel="Nothing on your schedule today. Enjoy the breather." />;
}

export function JobList({ scope, emptyLabel }: { scope: "today" | "all"; emptyLabel: string }) {
    const { palette, isDark } = useTheme();
    const [jobs, setJobs] = useState<Job[]>([]);
    const [refreshing, setRefreshing] = useState(false);
    const [loading, setLoading] = useState(true);
    const [pending, setPending] = useState(0);
    const router = useRouter();

    const load = useCallback(async () => {
        try {
            const { data } = await api.get<Job[]>("/jobs", { params: { mine: true } });
            setJobs(data);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
        setPending(await queueSize());
    }, []);

    useEffect(() => { load(); }, [load]);

    useFocusEffect(useCallback(() => {
        load();
        flush().then(() => queueSize().then(setPending));
        const t = setInterval(load, 30_000);
        return () => clearInterval(t);
    }, [load]));

    const onRefresh = () => { setRefreshing(true); load(); };

    const todayStr = new Date().toISOString().slice(0, 10);
    const filtered = scope === "today"
        ? jobs.filter((j) => j.scheduled_at?.startsWith(todayStr))
        : jobs;
    const sorted = [...filtered].sort((a, b) => (a.scheduled_at || "").localeCompare(b.scheduled_at || ""));

    if (loading) {
        return <View style={[s.center, { backgroundColor: palette.soft }]}><ActivityIndicator color={palette.primary} /></View>;
    }

    return (
        <View style={{ flex: 1, backgroundColor: palette.soft }}>
            {pending > 0 && (
                <View style={[s.queueBanner, { backgroundColor: palette.warn }]}>
                    <Text style={s.queueText}>{pending} change{pending === 1 ? "" : "s"} pending sync</Text>
                </View>
            )}
            <FlatList
                data={sorted}
                keyExtractor={(j) => j.id}
                refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={palette.primary} />}
                contentContainerStyle={sorted.length === 0 ? s.empty : { padding: 16 }}
                ListEmptyComponent={<Text style={[s.emptyText, { color: palette.muted }]}>{emptyLabel}</Text>}
                renderItem={({ item }) => <JobCard job={item} palette={palette} isDark={isDark} onPress={() => router.push(`/jobs/${item.id}`)} />}
            />
        </View>
    );
}

function JobCard({ job, palette, isDark, onPress }: any) {
    const time = job.scheduled_at
        ? new Date(job.scheduled_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
        : "";
    const isEmergency = job.priority === "emergency" || job.priority === "high";
    const statusColor: any = {
        scheduled: { bg: isDark ? "#1E3A8A" : "#EFF6FF", fg: palette.primary },
        in_progress: { bg: isDark ? "#78350F" : "#FEF3C7", fg: palette.warn },
        completed: { bg: isDark ? "#14532D" : "#DCFCE7", fg: palette.ok },
        unscheduled: { bg: palette.surface2, fg: palette.muted },
        cancelled: { bg: isDark ? "#7F1D1D" : "#FEE2E2", fg: palette.accent },
    }[job.status] || { bg: palette.surface2, fg: palette.muted };
    return (
        <TouchableOpacity onPress={onPress}
            activeOpacity={0.7}
            style={[s.card, {
                backgroundColor: palette.paper,
                borderColor: isEmergency ? palette.accent : palette.line,
                borderWidth: isEmergency ? 2 : 1,
            }]}>
            {isEmergency && (
                <View style={[s.priorityStripe, { backgroundColor: palette.accent }]}>
                    <Text style={s.priorityText}>{job.priority?.toUpperCase()}</Text>
                </View>
            )}
            <View style={s.row}>
                <Text style={[s.cardTitle, { color: palette.ink }]} numberOfLines={2}>{job.title}</Text>
                <View style={[s.badge, { backgroundColor: statusColor.bg }]}>
                    <Text style={[s.badgeText, { color: statusColor.fg }]}>{job.status.replace("_", " ").toUpperCase()}</Text>
                </View>
            </View>
            {!!time && <Text style={[s.cardMeta, { color: palette.muted }]}>{time}{job.duration_min ? ` · ${job.duration_min} min` : ""}</Text>}
            {!!job.customer_name && <Text style={[s.cardMeta, { color: palette.muted }]}>{job.customer_name}</Text>}
            {!!job.address && <Text style={[s.cardAddr, { color: palette.ink }]}>{job.address}</Text>}
            {!!job.price && <Text style={[s.cardPrice, { color: palette.ink }]}>${job.price.toFixed(2)}</Text>}
        </TouchableOpacity>
    );
}

const s = StyleSheet.create({
    center: { flex: 1, alignItems: "center", justifyContent: "center" },
    empty: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
    emptyText: { textAlign: "center", fontSize: 14 },
    queueBanner: { padding: 10 },
    queueText: { color: "#fff", fontWeight: "700", fontSize: 12, letterSpacing: 0.5, textAlign: "center" },
    card: { padding: 16, marginBottom: 12, borderRadius: 12 },
    priorityStripe: { alignSelf: "flex-start", paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4, marginBottom: 8 },
    priorityText: { color: "#fff", fontSize: 9, fontWeight: "900", letterSpacing: 1 },
    row: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
    cardTitle: { fontSize: 18, fontWeight: "800", letterSpacing: -0.3, flex: 1, marginRight: 8 },
    badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 },
    badgeText: { fontSize: 9, fontWeight: "800", letterSpacing: 1 },
    cardMeta: { fontSize: 13, marginTop: 4 },
    cardAddr: { fontSize: 13, marginTop: 4 },
    cardPrice: { fontSize: 14, fontVariant: ["tabular-nums"], marginTop: 8, fontWeight: "700" },
});
