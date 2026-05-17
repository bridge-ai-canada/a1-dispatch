import { useEffect, useState, useCallback } from "react";
import { View, Text, FlatList, RefreshControl, StyleSheet, TouchableOpacity, ActivityIndicator } from "react-native";
import { api } from "../../lib/api";
import { colors } from "../../lib/theme";
import { useRouter } from "expo-router";

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
};

export default function TodayScreen() {
    return <JobList scope="today" emptyLabel="Nothing on the schedule today. Enjoy the breather." />;
}

export function JobList({ scope, emptyLabel }: { scope: "today" | "all"; emptyLabel: string }) {
    const [jobs, setJobs] = useState<Job[]>([]);
    const [refreshing, setRefreshing] = useState(false);
    const [loading, setLoading] = useState(true);
    const router = useRouter();

    const load = useCallback(async () => {
        try {
            const { data } = await api.get<Job[]>("/jobs", { params: { mine: true } });
            setJobs(data);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const onRefresh = () => { setRefreshing(true); load(); };

    const todayStr = new Date().toISOString().slice(0, 10);
    const filtered = scope === "today"
        ? jobs.filter((j) => j.scheduled_at?.startsWith(todayStr))
        : jobs;
    const sorted = [...filtered].sort((a, b) => (a.scheduled_at || "").localeCompare(b.scheduled_at || ""));

    if (loading) {
        return <View style={s.center}><ActivityIndicator color={colors.primary} /></View>;
    }

    return (
        <FlatList
            data={sorted}
            keyExtractor={(j) => j.id}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
            contentContainerStyle={sorted.length === 0 ? s.empty : { padding: 16 }}
            ListEmptyComponent={<Text style={s.emptyText}>{emptyLabel}</Text>}
            renderItem={({ item }) => <JobCard job={item} onPress={() => router.push(`/jobs/${item.id}`)} />}
        />
    );
}

function JobCard({ job, onPress }: { job: Job; onPress: () => void }) {
    const time = job.scheduled_at
        ? new Date(job.scheduled_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
        : "";
    const statusColor: any = {
        scheduled: { bg: "#EFF6FF", fg: colors.primary },
        in_progress: { bg: "#FEF3C7", fg: colors.warn },
        completed: { bg: "#DCFCE7", fg: colors.ok },
        unscheduled: { bg: "#F1F5F9", fg: colors.muted },
        cancelled: { bg: "#FEE2E2", fg: colors.accent },
    }[job.status] || { bg: "#F1F5F9", fg: colors.muted };
    return (
        <TouchableOpacity onPress={onPress} style={s.card}>
            <View style={s.row}>
                <Text style={s.cardTitle}>{job.title}</Text>
                <View style={[s.badge, { backgroundColor: statusColor.bg }]}>
                    <Text style={[s.badgeText, { color: statusColor.fg }]}>{job.status.replace("_", " ").toUpperCase()}</Text>
                </View>
            </View>
            {!!time && <Text style={s.cardMeta}>{time}{job.duration_min ? ` · ${job.duration_min} min` : ""}</Text>}
            {!!job.customer_name && <Text style={s.cardMeta}>{job.customer_name}</Text>}
            {!!job.address && <Text style={s.cardAddr}>{job.address}</Text>}
            {!!job.price && <Text style={s.cardPrice}>${job.price.toFixed(2)}</Text>}
        </TouchableOpacity>
    );
}

const s = StyleSheet.create({
    center: { flex: 1, alignItems: "center", justifyContent: "center" },
    empty: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
    emptyText: { color: colors.muted, textAlign: "center", fontSize: 14 },
    card: { backgroundColor: colors.paper, borderColor: colors.line, borderWidth: 1, padding: 16, marginBottom: 12 },
    row: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
    cardTitle: { fontSize: 18, fontWeight: "800", color: colors.ink, letterSpacing: -0.3, flex: 1, marginRight: 8 },
    badge: { paddingHorizontal: 8, paddingVertical: 3 },
    badgeText: { fontSize: 9, fontWeight: "800", letterSpacing: 1 },
    cardMeta: { fontSize: 13, color: colors.muted, marginTop: 4 },
    cardAddr: { fontSize: 13, color: colors.ink, marginTop: 4 },
    cardPrice: { fontSize: 14, color: colors.ink, fontVariant: ["tabular-nums"], marginTop: 8, fontWeight: "700" },
});
