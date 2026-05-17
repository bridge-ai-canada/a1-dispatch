import { useEffect, useState } from "react";
import { View, Text, ScrollView, ActivityIndicator, TouchableOpacity, StyleSheet, Linking, Alert } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { api } from "../../../lib/api";
import { colors } from "../../../lib/theme";

export default function JobDetail() {
    const { id } = useLocalSearchParams<{ id: string }>();
    const router = useRouter();
    const [job, setJob] = useState<any>(null);
    const [busy, setBusy] = useState(false);

    const load = async () => {
        const { data } = await api.get(`/jobs/${id}`);
        setJob(data);
    };
    useEffect(() => { load(); }, [id]);

    if (!job) return <View style={s.center}><ActivityIndicator color={colors.primary} /></View>;

    const setStatus = async (status: string) => {
        setBusy(true);
        try {
            await api.patch(`/jobs/${id}`, { status });
            await load();
        } catch (e: any) {
            Alert.alert("Could not update", e.response?.data?.detail || "Try again");
        } finally {
            setBusy(false);
        }
    };

    const charge = async () => {
        try {
            const { data } = await api.post("/payments/checkout", {
                job_id: id, origin_url: "https://a1-dispatch.preview.emergentagent.com",
            });
            await WebBrowser.openBrowserAsync(data.url);
        } catch (e: any) {
            Alert.alert("Checkout failed", e.response?.data?.detail || "Try again");
        }
    };

    const callCustomer = () => {
        if (job.customer_phone) Linking.openURL(`tel:${job.customer_phone}`);
    };

    const openMap = () => {
        if (job.address) Linking.openURL(`https://maps.apple.com/?q=${encodeURIComponent(job.address)}`);
    };

    return (
        <ScrollView style={{ backgroundColor: colors.soft }} contentContainerStyle={{ padding: 16 }}>
            <Text style={s.kicker}>{job.job_type}</Text>
            <Text style={s.title}>{job.title}</Text>
            <View style={s.row}>
                <Text style={s.status}>{job.status.replace("_", " ").toUpperCase()}</Text>
                {job.scheduled_at && <Text style={s.meta}>{new Date(job.scheduled_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</Text>}
            </View>

            <View style={s.section}>
                <Text style={s.label}>Customer</Text>
                <Text style={s.value}>{job.customer_name || "—"}</Text>
                {!!job.customer_phone && <TouchableOpacity onPress={callCustomer}><Text style={s.link}>{job.customer_phone}</Text></TouchableOpacity>}
                {!!job.address && <TouchableOpacity onPress={openMap}><Text style={s.link}>{job.address}</Text></TouchableOpacity>}
            </View>

            {!!job.description && (
                <View style={s.section}>
                    <Text style={s.label}>Notes</Text>
                    <Text style={s.value}>{job.description}</Text>
                </View>
            )}

            <View style={s.section}>
                <Text style={s.label}>Price</Text>
                <Text style={s.price}>${(job.price || 0).toFixed(2)}{job.paid ? "  ·  PAID" : ""}</Text>
            </View>

            <View style={{ marginTop: 24, gap: 10 }}>
                {job.status !== "completed" && (
                    <>
                        {job.status !== "in_progress" && (
                            <TouchableOpacity disabled={busy} onPress={() => setStatus("in_progress")} style={[s.btn, { backgroundColor: colors.warn }]}>
                                <Text style={s.btnText}>Start job</Text>
                            </TouchableOpacity>
                        )}
                        <TouchableOpacity disabled={busy} onPress={() => setStatus("completed")} style={[s.btn, { backgroundColor: colors.ok }]}>
                            <Text style={s.btnText}>Mark complete</Text>
                        </TouchableOpacity>
                    </>
                )}
                {!job.paid && job.price > 0 && (
                    <TouchableOpacity onPress={charge} style={[s.btn, { backgroundColor: colors.primary }]}>
                        <Text style={s.btnText}>Charge ${(job.price).toFixed(2)}</Text>
                    </TouchableOpacity>
                )}
            </View>
        </ScrollView>
    );
}

const s = StyleSheet.create({
    center: { flex: 1, alignItems: "center", justifyContent: "center" },
    kicker: { fontSize: 11, letterSpacing: 2, color: colors.accent, fontWeight: "800" },
    title: { fontSize: 28, fontWeight: "800", letterSpacing: -0.5, color: colors.ink, marginTop: 4 },
    row: { flexDirection: "row", alignItems: "center", marginTop: 8, gap: 12 },
    status: { fontSize: 10, color: colors.primary, fontWeight: "800", letterSpacing: 1 },
    meta: { fontSize: 12, color: colors.muted },
    section: { marginTop: 20, backgroundColor: colors.paper, borderColor: colors.line, borderWidth: 1, padding: 14 },
    label: { fontSize: 10, letterSpacing: 1.4, color: colors.muted, fontWeight: "700", marginBottom: 6 },
    value: { fontSize: 15, color: colors.ink, lineHeight: 22 },
    link: { fontSize: 15, color: colors.primary, marginTop: 4 },
    price: { fontSize: 22, color: colors.ink, fontWeight: "800", fontVariant: ["tabular-nums"] },
    btn: { paddingVertical: 14, alignItems: "center" },
    btnText: { color: "#fff", fontWeight: "800", letterSpacing: 0.5 },
});
