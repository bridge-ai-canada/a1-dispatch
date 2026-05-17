import { useEffect, useState } from "react";
import {
    View, Text, ScrollView, ActivityIndicator, TouchableOpacity, StyleSheet,
    Linking, Alert, Image, Modal,
} from "react-native";
import { useLocalSearchParams } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import * as ImagePicker from "expo-image-picker";
import SignatureScreen from "react-native-signature-canvas";
import { api, API_URL } from "../../../lib/api";
import { enqueue, flush, queueSize } from "../../../lib/queue";
import { colors } from "../../../lib/theme";

export default function JobDetail() {
    const { id } = useLocalSearchParams<{ id: string }>();
    const [job, setJob] = useState<any>(null);
    const [busy, setBusy] = useState(false);
    const [pendingCount, setPendingCount] = useState(0);
    const [sigOpen, setSigOpen] = useState(false);

    const load = async () => {
        try {
            const { data } = await api.get(`/jobs/${id}`);
            setJob(data);
        } catch (_) {}
    };
    const refreshQ = async () => setPendingCount(await queueSize());

    useEffect(() => { load(); refreshQ(); flush().then(refreshQ); }, [id]);

    if (!job) return <View style={s.center}><ActivityIndicator color={colors.primary} /></View>;

    const setStatus = async (status: string) => {
        setBusy(true);
        setJob({ ...job, status }); // optimistic
        try {
            await api.patch(`/jobs/${id}`, { status });
            await load();
        } catch (e: any) {
            // queue it for later
            await enqueue({ method: "patch", url: `/jobs/${id}`, data: { status } });
            await refreshQ();
            Alert.alert("Saved offline", "Will sync when you're back online.");
        } finally {
            setBusy(false);
        }
    };

    const charge = async () => {
        try {
            const { data } = await api.post("/payments/checkout", {
                job_id: id, origin_url: API_URL,
            });
            await WebBrowser.openBrowserAsync(data.url);
        } catch (e: any) {
            Alert.alert("Checkout failed", e.response?.data?.detail || "Try again");
        }
    };

    const takePhoto = async () => {
        const perm = await ImagePicker.requestCameraPermissionsAsync();
        if (!perm.granted) { Alert.alert("Camera permission denied"); return; }
        const res = await ImagePicker.launchCameraAsync({ quality: 0.7 });
        if (res.canceled || !res.assets?.length) return;
        await uploadPhoto(res.assets[0].uri);
    };

    const pickPhoto = async () => {
        const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (!perm.granted) { Alert.alert("Library permission denied"); return; }
        const res = await ImagePicker.launchImageLibraryAsync({ quality: 0.7 });
        if (res.canceled || !res.assets?.length) return;
        await uploadPhoto(res.assets[0].uri);
    };

    const uploadPhoto = async (uri: string) => {
        const form = new FormData();
        form.append("file", { uri, name: `job-${id}.jpg`, type: "image/jpeg" } as any);
        setBusy(true);
        try {
            await api.post(`/jobs/${id}/photos`, form, { headers: { "Content-Type": "multipart/form-data" } });
            await load();
        } catch (e: any) {
            Alert.alert("Upload failed", e.response?.data?.detail || "Try again");
        } finally { setBusy(false); }
    };

    const handleSignature = async (sigBase64: string) => {
        setSigOpen(false);
        setBusy(true);
        try {
            await api.post(`/jobs/${id}/signature`, { image_base64: sigBase64, signer_name: job.customer_name });
            await load();
            Alert.alert("Signature saved");
        } catch (e: any) {
            Alert.alert("Could not save", e.response?.data?.detail || "Try again");
        } finally { setBusy(false); }
    };

    return (
        <>
            <ScrollView style={{ backgroundColor: colors.soft }} contentContainerStyle={{ padding: 16 }}>
                {pendingCount > 0 && (
                    <View style={s.queueBanner}>
                        <Text style={s.queueText}>{pendingCount} change{pendingCount === 1 ? "" : "s"} pending sync</Text>
                    </View>
                )}
                <Text style={s.kicker}>{job.job_type}</Text>
                <Text style={s.title}>{job.title}</Text>
                <View style={s.row}>
                    <Text style={s.status}>{job.status.replace("_", " ").toUpperCase()}</Text>
                    {job.scheduled_at && <Text style={s.meta}>{new Date(job.scheduled_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</Text>}
                </View>

                <View style={s.section}>
                    <Text style={s.label}>Customer</Text>
                    <Text style={s.value}>{job.customer_name || "—"}</Text>
                    {!!job.customer_phone && <TouchableOpacity onPress={() => Linking.openURL(`tel:${job.customer_phone}`)}><Text style={s.link}>{job.customer_phone}</Text></TouchableOpacity>}
                    {!!job.address && <TouchableOpacity onPress={() => Linking.openURL(`https://maps.apple.com/?q=${encodeURIComponent(job.address)}`)}><Text style={s.link}>{job.address}</Text></TouchableOpacity>}
                </View>

                {!!job.description && (
                    <View style={s.section}>
                        <Text style={s.label}>Notes</Text>
                        <Text style={s.value}>{job.description}</Text>
                    </View>
                )}

                <View style={s.section}>
                    <Text style={s.label}>Photos · {(job.photos || []).length}</Text>
                    <View style={s.photoRow}>
                        {(job.photos || []).slice(0, 6).map((p: any) => (
                            <Image key={p.id} source={{ uri: `${API_URL}/api/files/${p.path}` }} style={s.thumb} />
                        ))}
                    </View>
                    <View style={s.photoBtns}>
                        <TouchableOpacity onPress={takePhoto} style={[s.btnSmall, { backgroundColor: colors.primary }]}>
                            <Text style={s.btnSmallText}>📷 Camera</Text>
                        </TouchableOpacity>
                        <TouchableOpacity onPress={pickPhoto} style={[s.btnSmall, { backgroundColor: colors.ink }]}>
                            <Text style={s.btnSmallText}>🖼 Library</Text>
                        </TouchableOpacity>
                    </View>
                </View>

                <View style={s.section}>
                    <Text style={s.label}>Signature</Text>
                    {job.signature?.path
                        ? <Image source={{ uri: `${API_URL}/api/files/${job.signature.path}` }} style={s.sigImage} />
                        : <Text style={s.value}>Not signed yet</Text>}
                    <TouchableOpacity onPress={() => setSigOpen(true)} style={[s.btnSmall, { backgroundColor: colors.ink, marginTop: 8 }]}>
                        <Text style={s.btnSmallText}>✍️ Capture signature</Text>
                    </TouchableOpacity>
                </View>

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

            <Modal visible={sigOpen} animationType="slide" onRequestClose={() => setSigOpen(false)}>
                <View style={{ flex: 1, backgroundColor: colors.paper }}>
                    <View style={{ padding: 16, borderBottomColor: colors.line, borderBottomWidth: 1 }}>
                        <Text style={{ fontSize: 16, fontWeight: "700", color: colors.ink }}>
                            Have the customer sign below
                        </Text>
                    </View>
                    <SignatureScreen
                        onOK={(sig) => handleSignature(sig)}
                        onEmpty={() => Alert.alert("Please sign first")}
                        descriptionText=""
                        confirmText="Save signature"
                        clearText="Clear"
                        webStyle={`.m-signature-pad--footer { background: ${colors.soft}; }`}
                    />
                    <TouchableOpacity onPress={() => setSigOpen(false)} style={{ padding: 14, backgroundColor: colors.line, alignItems: "center" }}>
                        <Text style={{ fontWeight: "700", color: colors.ink }}>Cancel</Text>
                    </TouchableOpacity>
                </View>
            </Modal>
        </>
    );
}

const s = StyleSheet.create({
    center: { flex: 1, alignItems: "center", justifyContent: "center" },
    queueBanner: { backgroundColor: colors.warn, padding: 8, marginBottom: 12 },
    queueText: { color: "#fff", fontWeight: "700", fontSize: 12, letterSpacing: 0.5, textAlign: "center" },
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
    photoRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 8 },
    thumb: { width: 60, height: 60, borderColor: colors.line, borderWidth: 1 },
    photoBtns: { flexDirection: "row", gap: 8, marginTop: 12 },
    btnSmall: { paddingVertical: 10, paddingHorizontal: 14, alignItems: "center", flex: 1 },
    btnSmallText: { color: "#fff", fontWeight: "700", fontSize: 13 },
    sigImage: { width: "100%", height: 120, borderColor: colors.line, borderWidth: 1, resizeMode: "contain", marginTop: 8 },
    btn: { paddingVertical: 14, alignItems: "center" },
    btnText: { color: "#fff", fontWeight: "800", letterSpacing: 0.5 },
});
