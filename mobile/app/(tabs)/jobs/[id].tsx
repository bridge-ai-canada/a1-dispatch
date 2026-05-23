import { useEffect, useState, useCallback } from "react";
import {
    View, Text, ScrollView, ActivityIndicator, TouchableOpacity, StyleSheet,
    Linking, Alert, Image, Modal, TextInput, Platform,
} from "react-native";
import { useLocalSearchParams, useFocusEffect } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import * as ImagePicker from "expo-image-picker";
import SignatureScreen from "react-native-signature-canvas";
import { api, API_URL } from "../../../lib/api";
import { enqueue, flush, queueSize } from "../../../lib/queue";
import { useTheme } from "../../../lib/theme";

type TimeLog = { id: string; user_id: string; started_at: string; ended_at?: string | null; duration_min: number };
type Material = { id: string; name: string; qty: number; unit_cost: number; unit_price: number; added_at: string; added_by_name?: string };
type ChecklistItem = { id: string; title: string; required: boolean; completed: boolean; completed_at?: string | null };
type VoiceNote = { id: string; text: string; author_name: string; created_at: string };

function fmtTime(iso?: string | null) {
    if (!iso) return "";
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
function fmtDuration(min: number) {
    if (!min) return "0m";
    const h = Math.floor(min / 60); const m = min % 60;
    return h ? `${h}h ${m}m` : `${m}m`;
}
function liveDur(started: string) {
    return Math.max(0, Math.floor((Date.now() - new Date(started).getTime()) / 60_000));
}

export default function JobDetail() {
    const { id } = useLocalSearchParams<{ id: string }>();
    const { palette, isDark } = useTheme();
    const [job, setJob] = useState<any>(null);
    const [busy, setBusy] = useState(false);
    const [pendingCount, setPendingCount] = useState(0);
    const [sigOpen, setSigOpen] = useState(false);
    const [voiceOpen, setVoiceOpen] = useState(false);
    const [voiceText, setVoiceText] = useState("");
    const [materialOpen, setMaterialOpen] = useState(false);
    const [materialName, setMaterialName] = useState("");
    const [materialQty, setMaterialQty] = useState("1");
    const [materialPrice, setMaterialPrice] = useState("");
    const [catalog, setCatalog] = useState<any[]>([]);
    const [templates, setTemplates] = useState<any[]>([]);
    const [tplOpen, setTplOpen] = useState(false);
    const [tick, setTick] = useState(0);

    const load = useCallback(async () => {
        try {
            const { data } = await api.get(`/jobs/${id}`);
            setJob(data);
        } catch (_) {}
    }, [id]);

    const loadAux = useCallback(async () => {
        try {
            const [c, t] = await Promise.all([
                api.get("/materials"),
                api.get("/checklist-templates"),
            ]);
            setCatalog(c.data || []);
            setTemplates(t.data || []);
        } catch (_) {}
    }, []);

    const refreshQ = async () => setPendingCount(await queueSize());

    useEffect(() => { load(); refreshQ(); flush().then(refreshQ); loadAux(); }, [id, load, loadAux]);
    useFocusEffect(useCallback(() => { load(); refreshQ(); }, [load]));

    // tick for live duration display when timer is on
    useEffect(() => {
        const myActive = (job?.time_logs || []).some((l: TimeLog) => !l.ended_at);
        if (!myActive) return;
        const t = setInterval(() => setTick((x) => x + 1), 30_000);
        return () => clearInterval(t);
    }, [job?.time_logs]);

    if (!job) return <View style={[s.center, { backgroundColor: palette.soft }]}><ActivityIndicator color={palette.primary} /></View>;

    const setStatus = async (status: string) => {
        setBusy(true);
        setJob({ ...job, status });
        try {
            await api.patch(`/jobs/${id}`, { status });
            await load();
        } catch (_) {
            await enqueue({ method: "patch", url: `/jobs/${id}`, data: { status } });
            await refreshQ();
            Alert.alert("Saved offline", "Will sync when you're back online.");
        } finally { setBusy(false); }
    };

    const charge = async () => {
        try {
            const { data } = await api.post("/payments/checkout", { job_id: id, origin_url: API_URL });
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
        await uploadMedia(res.assets[0].uri, "photo");
    };
    const pickPhoto = async () => {
        const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (!perm.granted) { Alert.alert("Library permission denied"); return; }
        const res = await ImagePicker.launchImageLibraryAsync({ quality: 0.7 });
        if (res.canceled || !res.assets?.length) return;
        await uploadMedia(res.assets[0].uri, "photo");
    };
    const takeVideo = async () => {
        const perm = await ImagePicker.requestCameraPermissionsAsync();
        if (!perm.granted) { Alert.alert("Camera permission denied"); return; }
        const res = await ImagePicker.launchCameraAsync({
            mediaTypes: ImagePicker.MediaTypeOptions.Videos,
            videoMaxDuration: 60,
            quality: 0.6,
        });
        if (res.canceled || !res.assets?.length) return;
        await uploadMedia(res.assets[0].uri, "video");
    };
    const uploadMedia = async (uri: string, kind: "photo" | "video") => {
        const form = new FormData();
        const ext = kind === "video" ? "mp4" : "jpg";
        const mime = kind === "video" ? "video/mp4" : "image/jpeg";
        form.append("file", { uri, name: `job-${id}.${ext}`, type: mime } as any);
        form.append("taken_at", new Date().toISOString());
        setBusy(true);
        try {
            await api.post(`/jobs/${id}/${kind === "video" ? "videos" : "photos"}`, form, {
                headers: { "Content-Type": "multipart/form-data" },
                timeout: 60_000,
            });
            await load();
        } catch (e: any) {
            Alert.alert("Upload failed", e.response?.data?.detail || "Try again");
        } finally { setBusy(false); }
    };

    const saveSignature = async (sigBase64: string) => {
        setSigOpen(false); setBusy(true);
        try {
            await api.post(`/jobs/${id}/signature`, { image_base64: sigBase64, signer_name: job.customer_name });
            await load();
            Alert.alert("Signature saved");
        } catch (e: any) {
            Alert.alert("Could not save", e.response?.data?.detail || "Try again");
        } finally { setBusy(false); }
    };

    const navigate = () => {
        if (!job.address) return;
        const q = encodeURIComponent(job.address);
        const url = Platform.OS === "ios" ? `maps://?q=${q}` : `google.navigation:q=${q}`;
        Linking.openURL(url).catch(() => Linking.openURL(`https://maps.google.com/?q=${q}`));
    };

    const myActiveTimer = (job.time_logs || []).find((l: TimeLog) => !l.ended_at);
    const startTimer = async () => {
        try { await api.post(`/jobs/${id}/time/start`); await load(); }
        catch (e: any) { Alert.alert("Failed", e.response?.data?.detail || "Try again"); }
    };
    const stopTimer = async () => {
        try { await api.post(`/jobs/${id}/time/stop`); await load(); }
        catch (e: any) { Alert.alert("Failed", e.response?.data?.detail || "Try again"); }
    };
    const totalTimerMin = (job.time_logs || []).reduce((sum: number, l: TimeLog) => sum + (l.duration_min || 0), 0)
        + (myActiveTimer ? liveDur(myActiveTimer.started_at) : 0);

    const saveVoiceNote = async () => {
        if (!voiceText.trim()) return;
        setBusy(true);
        try {
            await api.post(`/jobs/${id}/voice-notes`, { text: voiceText.trim() });
            setVoiceText(""); setVoiceOpen(false); await load();
        } catch (e: any) {
            await enqueue({ method: "post", url: `/jobs/${id}/voice-notes`, data: { text: voiceText.trim() } });
            setVoiceText(""); setVoiceOpen(false); await refreshQ();
            Alert.alert("Saved offline");
        } finally { setBusy(false); }
    };

    const toggleChecklist = async (item: ChecklistItem) => {
        const items = (job.checklist || []).map((it: ChecklistItem) =>
            it.id === item.id ? { ...it, completed: !it.completed } : it);
        setJob({ ...job, checklist: items });
        try {
            await api.post(`/jobs/${id}/checklist/toggle`, { item_id: item.id, completed: !item.completed });
        } catch (_) {
            await enqueue({ method: "post", url: `/jobs/${id}/checklist/toggle`, data: { item_id: item.id, completed: !item.completed } });
            await refreshQ();
        }
    };
    const applyTemplate = async (templateId: string) => {
        setTplOpen(false); setBusy(true);
        try {
            await api.post(`/jobs/${id}/checklist/apply`, { template_id: templateId });
            await load();
        } catch (e: any) {
            Alert.alert("Failed", e.response?.data?.detail || "Try again");
        } finally { setBusy(false); }
    };

    const addMaterial = async (catalogId?: string) => {
        const body: any = {};
        if (catalogId) body.material_id = catalogId;
        else {
            if (!materialName.trim()) return;
            body.name = materialName.trim();
            body.unit_price = parseFloat(materialPrice) || 0;
        }
        body.qty = parseFloat(materialQty) || 1;
        setBusy(true);
        try {
            await api.post(`/jobs/${id}/materials`, body);
            setMaterialOpen(false); setMaterialName(""); setMaterialQty("1"); setMaterialPrice("");
            await load();
        } catch (e: any) {
            Alert.alert("Failed", e.response?.data?.detail || "Try again");
        } finally { setBusy(false); }
    };
    const removeMaterial = async (entryId: string) => {
        try {
            await api.delete(`/jobs/${id}/materials/${entryId}`);
            await load();
        } catch (e: any) {
            Alert.alert("Failed", e.response?.data?.detail || "Try again");
        }
    };

    const photos = job.photos || [];
    const videos = job.videos || [];
    const voiceNotes: VoiceNote[] = job.voice_notes || [];
    const checklist: ChecklistItem[] = job.checklist || [];
    const materials: Material[] = job.materials_used || [];

    return (
        <>
            <ScrollView style={{ backgroundColor: palette.soft }} contentContainerStyle={{ padding: 16, paddingBottom: 80 }}>
                {pendingCount > 0 && (
                    <View style={[s.queueBanner, { backgroundColor: palette.warn }]}>
                        <Text style={s.queueText}>{pendingCount} change{pendingCount === 1 ? "" : "s"} pending sync</Text>
                    </View>
                )}

                <Text style={[s.kicker, { color: palette.accent }]}>{job.job_type}</Text>
                <Text style={[s.title, { color: palette.ink }]}>{job.title}</Text>
                <View style={s.row}>
                    <Text style={[s.status, { color: palette.primary }]}>{job.status.replace("_", " ").toUpperCase()}</Text>
                    {job.scheduled_at && <Text style={[s.meta, { color: palette.muted }]}>
                        {new Date(job.scheduled_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
                    </Text>}
                </View>

                {/* Customer + Navigate */}
                <View style={[s.section, { backgroundColor: palette.paper, borderColor: palette.line }]}>
                    <Text style={[s.label, { color: palette.muted }]}>CUSTOMER</Text>
                    <Text style={[s.value, { color: palette.ink }]}>{job.customer_name || "—"}</Text>
                    {!!job.customer_phone && (
                        <TouchableOpacity onPress={() => Linking.openURL(`tel:${job.customer_phone}`)} style={[s.tap, { borderColor: palette.line }]}>
                            <Text style={[s.tapText, { color: palette.primary }]}>📞  {job.customer_phone}</Text>
                        </TouchableOpacity>
                    )}
                    {!!job.address && (
                        <>
                            <Text style={[s.address, { color: palette.ink }]}>{job.address}</Text>
                            <TouchableOpacity onPress={navigate} style={[s.bigBtn, { backgroundColor: palette.primary, marginTop: 10 }]}>
                                <Text style={s.bigBtnText}>🧭  Navigate</Text>
                            </TouchableOpacity>
                        </>
                    )}
                </View>

                {!!job.description && (
                    <View style={[s.section, { backgroundColor: palette.paper, borderColor: palette.line }]}>
                        <Text style={[s.label, { color: palette.muted }]}>JOB NOTES</Text>
                        <Text style={[s.value, { color: palette.ink }]}>{job.description}</Text>
                    </View>
                )}

                {/* Time tracking */}
                <View style={[s.section, { backgroundColor: palette.paper, borderColor: palette.line }]}>
                    <Text style={[s.label, { color: palette.muted }]}>TIME TRACKING</Text>
                    <View style={s.timerRow}>
                        <Text style={[s.bigNum, { color: palette.ink }]}>{fmtDuration(totalTimerMin)}</Text>
                        <View style={{ flex: 1, alignItems: "flex-end" }}>
                            {myActiveTimer
                                ? <TouchableOpacity onPress={stopTimer} style={[s.timerBtn, { backgroundColor: palette.accent }]}>
                                      <Text style={s.timerBtnText}>⏸  Stop</Text>
                                  </TouchableOpacity>
                                : <TouchableOpacity onPress={startTimer} style={[s.timerBtn, { backgroundColor: palette.ok }]}>
                                      <Text style={s.timerBtnText}>▶  Start</Text>
                                  </TouchableOpacity>}
                        </View>
                    </View>
                    {myActiveTimer && (
                        <Text style={[s.helper, { color: palette.muted }]}>
                            Started {fmtTime(myActiveTimer.started_at)} · {fmtDuration(liveDur(myActiveTimer.started_at))} so far
                        </Text>
                    )}
                </View>

                {/* Checklist */}
                <View style={[s.section, { backgroundColor: palette.paper, borderColor: palette.line }]}>
                    <View style={s.sectionHeadRow}>
                        <Text style={[s.label, { color: palette.muted }]}>CHECKLIST · {checklist.filter(c=>c.completed).length}/{checklist.length}</Text>
                        <TouchableOpacity onPress={() => setTplOpen(true)}>
                            <Text style={[s.linkAction, { color: palette.primary }]}>
                                {checklist.length ? "Replace" : "Apply template"}
                            </Text>
                        </TouchableOpacity>
                    </View>
                    {checklist.length === 0 ? (
                        <Text style={[s.value, { color: palette.muted }]}>No checklist applied to this job.</Text>
                    ) : (
                        checklist.map((it) => (
                            <TouchableOpacity key={it.id} onPress={() => toggleChecklist(it)}
                                style={[s.checkRow, { borderColor: palette.line }]}>
                                <View style={[s.checkBox, {
                                    borderColor: it.completed ? palette.ok : palette.line,
                                    backgroundColor: it.completed ? palette.ok : "transparent",
                                }]}>
                                    {it.completed && <Text style={s.checkMark}>✓</Text>}
                                </View>
                                <Text style={[s.checkText, {
                                    color: it.completed ? palette.muted : palette.ink,
                                    textDecorationLine: it.completed ? "line-through" : "none",
                                }]}>
                                    {it.title}{it.required ? " *" : ""}
                                </Text>
                            </TouchableOpacity>
                        ))
                    )}
                </View>

                {/* Materials */}
                <View style={[s.section, { backgroundColor: palette.paper, borderColor: palette.line }]}>
                    <View style={s.sectionHeadRow}>
                        <Text style={[s.label, { color: palette.muted }]}>MATERIALS · {materials.length}</Text>
                        <TouchableOpacity onPress={() => setMaterialOpen(true)}>
                            <Text style={[s.linkAction, { color: palette.primary }]}>+ Add</Text>
                        </TouchableOpacity>
                    </View>
                    {materials.length === 0 ? (
                        <Text style={[s.value, { color: palette.muted }]}>No materials logged yet.</Text>
                    ) : (
                        materials.map((m) => (
                            <View key={m.id} style={[s.matRow, { borderColor: palette.line }]}>
                                <View style={{ flex: 1 }}>
                                    <Text style={[s.matName, { color: palette.ink }]}>{m.name}</Text>
                                    <Text style={[s.matMeta, { color: palette.muted }]}>
                                        {m.qty} × ${(m.unit_price || 0).toFixed(2)}
                                    </Text>
                                </View>
                                <Text style={[s.matAmount, { color: palette.ink }]}>
                                    ${(m.qty * (m.unit_price || 0)).toFixed(2)}
                                </Text>
                                <TouchableOpacity onPress={() => removeMaterial(m.id)} style={{ marginLeft: 8 }}>
                                    <Text style={{ color: palette.accent, fontSize: 18 }}>×</Text>
                                </TouchableOpacity>
                            </View>
                        ))
                    )}
                </View>

                {/* Voice notes */}
                <View style={[s.section, { backgroundColor: palette.paper, borderColor: palette.line }]}>
                    <View style={s.sectionHeadRow}>
                        <Text style={[s.label, { color: palette.muted }]}>VOICE NOTES · {voiceNotes.length}</Text>
                        <TouchableOpacity onPress={() => setVoiceOpen(true)}>
                            <Text style={[s.linkAction, { color: palette.primary }]}>+ Add</Text>
                        </TouchableOpacity>
                    </View>
                    {voiceNotes.length === 0 ? (
                        <Text style={[s.value, { color: palette.muted }]}>No notes yet. Tap "+ Add" and use your keyboard's mic.</Text>
                    ) : (
                        voiceNotes.slice().reverse().map((n) => (
                            <View key={n.id} style={[s.noteRow, { borderColor: palette.line }]}>
                                <Text style={[s.noteText, { color: palette.ink }]}>{n.text}</Text>
                                <Text style={[s.noteMeta, { color: palette.muted }]}>
                                    {n.author_name} · {new Date(n.created_at).toLocaleString()}
                                </Text>
                            </View>
                        ))
                    )}
                </View>

                {/* Media */}
                <View style={[s.section, { backgroundColor: palette.paper, borderColor: palette.line }]}>
                    <Text style={[s.label, { color: palette.muted }]}>PHOTOS · {photos.length}  ·  VIDEOS · {videos.length}</Text>
                    <View style={s.photoRow}>
                        {photos.slice(0, 8).map((p: any) => (
                            <View key={p.id} style={s.thumbWrap}>
                                <Image source={{ uri: `${API_URL}/api/files/${p.path}` }} style={[s.thumb, { borderColor: palette.line }]} />
                                {p.taken_at && (
                                    <View style={s.thumbStamp}>
                                        <Text style={s.thumbStampText}>{fmtTime(p.taken_at)}</Text>
                                    </View>
                                )}
                            </View>
                        ))}
                        {videos.slice(0, 4).map((v: any) => (
                            <TouchableOpacity key={v.id} onPress={() => WebBrowser.openBrowserAsync(`${API_URL}/api/files/${v.path}`)}
                                style={[s.videoThumb, { backgroundColor: palette.ink, borderColor: palette.line }]}>
                                <Text style={s.videoIcon}>▶</Text>
                                {v.taken_at && (
                                    <View style={s.thumbStamp}>
                                        <Text style={s.thumbStampText}>{fmtTime(v.taken_at)}</Text>
                                    </View>
                                )}
                            </TouchableOpacity>
                        ))}
                    </View>
                    <View style={s.photoBtns}>
                        <TouchableOpacity onPress={takePhoto} style={[s.mediaBtn, { backgroundColor: palette.primary }]}>
                            <Text style={s.mediaBtnText}>📷  Photo</Text>
                        </TouchableOpacity>
                        <TouchableOpacity onPress={takeVideo} style={[s.mediaBtn, { backgroundColor: palette.ink }]}>
                            <Text style={s.mediaBtnText}>🎥  Video</Text>
                        </TouchableOpacity>
                        <TouchableOpacity onPress={pickPhoto} style={[s.mediaBtn, { backgroundColor: palette.surface2 }]}>
                            <Text style={[s.mediaBtnText, { color: palette.ink }]}>🖼  Library</Text>
                        </TouchableOpacity>
                    </View>
                </View>

                {/* Signature */}
                <View style={[s.section, { backgroundColor: palette.paper, borderColor: palette.line }]}>
                    <Text style={[s.label, { color: palette.muted }]}>SIGNATURE</Text>
                    {job.signature?.path
                        ? <Image source={{ uri: `${API_URL}/api/files/${job.signature.path}` }}
                            style={[s.sigImage, { borderColor: palette.line }]} />
                        : <Text style={[s.value, { color: palette.muted }]}>Not signed yet</Text>}
                    <TouchableOpacity onPress={() => setSigOpen(true)}
                        style={[s.bigBtn, { backgroundColor: palette.ink, marginTop: 12 }]}>
                        <Text style={s.bigBtnText}>✍️  Capture signature</Text>
                    </TouchableOpacity>
                </View>

                {/* Price + actions */}
                <View style={[s.section, { backgroundColor: palette.paper, borderColor: palette.line }]}>
                    <Text style={[s.label, { color: palette.muted }]}>INVOICE</Text>
                    <Text style={[s.price, { color: palette.ink }]}>
                        ${(job.price || 0).toFixed(2)}{job.paid ? "  ·  PAID" : ""}
                    </Text>
                    {!job.paid && job.price > 0 && (
                        <TouchableOpacity onPress={charge}
                            style={[s.bigBtn, { backgroundColor: palette.ok, marginTop: 10 }]}>
                            <Text style={s.bigBtnText}>💳  Collect ${(job.price).toFixed(2)}</Text>
                        </TouchableOpacity>
                    )}
                </View>

                <View style={{ marginTop: 12, gap: 10 }}>
                    {job.status !== "completed" && (
                        <>
                            {job.status !== "in_progress" && (
                                <TouchableOpacity disabled={busy} onPress={() => setStatus("in_progress")}
                                    style={[s.bigBtn, { backgroundColor: palette.warn }]}>
                                    <Text style={s.bigBtnText}>▶  Start job</Text>
                                </TouchableOpacity>
                            )}
                            <TouchableOpacity disabled={busy} onPress={() => setStatus("completed")}
                                style={[s.bigBtn, { backgroundColor: palette.ok }]}>
                                <Text style={s.bigBtnText}>✓  Mark complete</Text>
                            </TouchableOpacity>
                        </>
                    )}
                </View>
            </ScrollView>

            {/* Signature modal */}
            <Modal visible={sigOpen} animationType="slide" onRequestClose={() => setSigOpen(false)}>
                <View style={{ flex: 1, backgroundColor: palette.paper }}>
                    <View style={{ padding: 16, borderBottomColor: palette.line, borderBottomWidth: 1 }}>
                        <Text style={{ fontSize: 16, fontWeight: "700", color: palette.ink }}>
                            Have the customer sign below
                        </Text>
                    </View>
                    <SignatureScreen
                        onOK={saveSignature}
                        onEmpty={() => Alert.alert("Please sign first")}
                        descriptionText=""
                        confirmText="Save signature"
                        clearText="Clear"
                        webStyle={`.m-signature-pad--footer { background: ${palette.soft}; }`}
                    />
                    <TouchableOpacity onPress={() => setSigOpen(false)}
                        style={{ padding: 16, backgroundColor: palette.line, alignItems: "center" }}>
                        <Text style={{ fontWeight: "700", color: palette.ink }}>Cancel</Text>
                    </TouchableOpacity>
                </View>
            </Modal>

            {/* Voice note modal */}
            <Modal visible={voiceOpen} animationType="slide" transparent onRequestClose={() => setVoiceOpen(false)}>
                <View style={s.modalBackdrop}>
                    <View style={[s.modalCard, { backgroundColor: palette.paper }]}>
                        <Text style={[s.modalTitle, { color: palette.ink }]}>Add voice note</Text>
                        <Text style={[s.modalSub, { color: palette.muted }]}>
                            Tap the mic on your keyboard 🎤 to dictate, or type below.
                        </Text>
                        <TextInput
                            multiline
                            placeholder="Tell us what happened on site…"
                            placeholderTextColor={palette.muted}
                            value={voiceText}
                            onChangeText={setVoiceText}
                            style={[s.textArea, { borderColor: palette.line, color: palette.ink }]}
                            autoFocus
                        />
                        <View style={{ flexDirection: "row", gap: 8, marginTop: 12 }}>
                            <TouchableOpacity onPress={() => { setVoiceOpen(false); setVoiceText(""); }}
                                style={[s.modalBtn, { backgroundColor: palette.surface2 }]}>
                                <Text style={[s.modalBtnText, { color: palette.ink }]}>Cancel</Text>
                            </TouchableOpacity>
                            <TouchableOpacity onPress={saveVoiceNote}
                                disabled={busy || !voiceText.trim()}
                                style={[s.modalBtn, { backgroundColor: palette.primary, opacity: busy || !voiceText.trim() ? 0.5 : 1 }]}>
                                <Text style={s.modalBtnText}>Save note</Text>
                            </TouchableOpacity>
                        </View>
                    </View>
                </View>
            </Modal>

            {/* Material modal */}
            <Modal visible={materialOpen} animationType="slide" transparent onRequestClose={() => setMaterialOpen(false)}>
                <View style={s.modalBackdrop}>
                    <View style={[s.modalCard, { backgroundColor: palette.paper, maxHeight: "80%" }]}>
                        <Text style={[s.modalTitle, { color: palette.ink }]}>Add material</Text>
                        {catalog.length > 0 && (
                            <ScrollView style={{ maxHeight: 240, marginVertical: 12 }}>
                                {catalog.map((m: any) => (
                                    <TouchableOpacity key={m.id} onPress={() => addMaterial(m.id)}
                                        style={[s.catalogRow, { borderColor: palette.line }]}>
                                        <View style={{ flex: 1 }}>
                                            <Text style={[s.matName, { color: palette.ink }]}>{m.name}</Text>
                                            <Text style={[s.matMeta, { color: palette.muted }]}>
                                                ${(m.unit_price || 0).toFixed(2)} · {m.unit || "each"}
                                                {m.stock != null ? `  · ${m.stock} in stock` : ""}
                                            </Text>
                                        </View>
                                        <Text style={[s.linkAction, { color: palette.primary }]}>+</Text>
                                    </TouchableOpacity>
                                ))}
                            </ScrollView>
                        )}
                        <Text style={[s.modalSub, { color: palette.muted, marginTop: 12 }]}>Or add custom:</Text>
                        <TextInput placeholder="Material name" placeholderTextColor={palette.muted}
                            value={materialName} onChangeText={setMaterialName}
                            style={[s.input, { borderColor: palette.line, color: palette.ink }]} />
                        <View style={{ flexDirection: "row", gap: 8, marginTop: 8 }}>
                            <TextInput placeholder="Qty" placeholderTextColor={palette.muted} keyboardType="decimal-pad"
                                value={materialQty} onChangeText={setMaterialQty}
                                style={[s.input, { borderColor: palette.line, color: palette.ink, flex: 1 }]} />
                            <TextInput placeholder="Price each" placeholderTextColor={palette.muted} keyboardType="decimal-pad"
                                value={materialPrice} onChangeText={setMaterialPrice}
                                style={[s.input, { borderColor: palette.line, color: palette.ink, flex: 1 }]} />
                        </View>
                        <View style={{ flexDirection: "row", gap: 8, marginTop: 12 }}>
                            <TouchableOpacity onPress={() => setMaterialOpen(false)}
                                style={[s.modalBtn, { backgroundColor: palette.surface2 }]}>
                                <Text style={[s.modalBtnText, { color: palette.ink }]}>Close</Text>
                            </TouchableOpacity>
                            <TouchableOpacity onPress={() => addMaterial()}
                                disabled={!materialName.trim()}
                                style={[s.modalBtn, { backgroundColor: palette.primary, opacity: materialName.trim() ? 1 : 0.5 }]}>
                                <Text style={s.modalBtnText}>Add custom</Text>
                            </TouchableOpacity>
                        </View>
                    </View>
                </View>
            </Modal>

            {/* Template picker modal */}
            <Modal visible={tplOpen} animationType="slide" transparent onRequestClose={() => setTplOpen(false)}>
                <View style={s.modalBackdrop}>
                    <View style={[s.modalCard, { backgroundColor: palette.paper, maxHeight: "70%" }]}>
                        <Text style={[s.modalTitle, { color: palette.ink }]}>Apply checklist template</Text>
                        {templates.length === 0 ? (
                            <Text style={[s.modalSub, { color: palette.muted }]}>
                                No templates yet. Create one from the web admin.
                            </Text>
                        ) : (
                            <ScrollView style={{ maxHeight: 360, marginTop: 8 }}>
                                {templates.map((t: any) => (
                                    <TouchableOpacity key={t.id} onPress={() => applyTemplate(t.id)}
                                        style={[s.catalogRow, { borderColor: palette.line }]}>
                                        <View style={{ flex: 1 }}>
                                            <Text style={[s.matName, { color: palette.ink }]}>{t.name}</Text>
                                            <Text style={[s.matMeta, { color: palette.muted }]}>{(t.items || []).length} items</Text>
                                        </View>
                                        <Text style={[s.linkAction, { color: palette.primary }]}>›</Text>
                                    </TouchableOpacity>
                                ))}
                            </ScrollView>
                        )}
                        <TouchableOpacity onPress={() => setTplOpen(false)}
                            style={[s.modalBtn, { backgroundColor: palette.surface2, marginTop: 12 }]}>
                            <Text style={[s.modalBtnText, { color: palette.ink }]}>Close</Text>
                        </TouchableOpacity>
                    </View>
                </View>
            </Modal>
        </>
    );
}

const s = StyleSheet.create({
    center: { flex: 1, alignItems: "center", justifyContent: "center" },
    queueBanner: { padding: 10, marginBottom: 12, borderRadius: 8 },
    queueText: { color: "#fff", fontWeight: "700", fontSize: 12, letterSpacing: 0.5, textAlign: "center" },
    kicker: { fontSize: 11, letterSpacing: 2, fontWeight: "800" },
    title: { fontSize: 28, fontWeight: "800", letterSpacing: -0.5, marginTop: 4 },
    row: { flexDirection: "row", alignItems: "center", marginTop: 8, gap: 12 },
    status: { fontSize: 10, fontWeight: "800", letterSpacing: 1 },
    meta: { fontSize: 12 },
    section: { marginTop: 16, borderWidth: 1, padding: 16, borderRadius: 12 },
    sectionHeadRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
    label: { fontSize: 10, letterSpacing: 1.4, fontWeight: "800" },
    linkAction: { fontSize: 13, fontWeight: "700" },
    value: { fontSize: 15, lineHeight: 22 },
    tap: { marginTop: 8, padding: 10, borderWidth: 1, borderRadius: 8 },
    tapText: { fontSize: 15, fontWeight: "600" },
    address: { fontSize: 15, marginTop: 8 },
    helper: { fontSize: 12, marginTop: 8 },
    timerRow: { flexDirection: "row", alignItems: "center" },
    bigNum: { fontSize: 36, fontWeight: "900", letterSpacing: -1, fontVariant: ["tabular-nums"] },
    timerBtn: { paddingVertical: 14, paddingHorizontal: 24, borderRadius: 12, minWidth: 120, alignItems: "center" },
    timerBtnText: { color: "#fff", fontWeight: "800", fontSize: 16 },
    checkRow: { flexDirection: "row", alignItems: "center", paddingVertical: 12, gap: 12, borderTopWidth: 1 },
    checkBox: { width: 28, height: 28, borderWidth: 2, borderRadius: 8, alignItems: "center", justifyContent: "center" },
    checkMark: { color: "#fff", fontWeight: "900", fontSize: 16 },
    checkText: { flex: 1, fontSize: 15 },
    matRow: { flexDirection: "row", alignItems: "center", paddingVertical: 10, borderTopWidth: 1 },
    matName: { fontSize: 14, fontWeight: "700" },
    matMeta: { fontSize: 12, marginTop: 2 },
    matAmount: { fontSize: 15, fontWeight: "800", fontVariant: ["tabular-nums"] },
    catalogRow: { flexDirection: "row", alignItems: "center", paddingVertical: 12, borderTopWidth: 1 },
    noteRow: { paddingVertical: 10, borderTopWidth: 1 },
    noteText: { fontSize: 14, lineHeight: 20 },
    noteMeta: { fontSize: 11, marginTop: 4 },
    photoRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 8, marginBottom: 12 },
    thumbWrap: { position: "relative" },
    thumb: { width: 72, height: 72, borderWidth: 1, borderRadius: 8 },
    videoThumb: { width: 72, height: 72, borderWidth: 1, borderRadius: 8, alignItems: "center", justifyContent: "center", position: "relative" },
    videoIcon: { color: "#fff", fontSize: 22 },
    thumbStamp: { position: "absolute", bottom: 0, left: 0, right: 0, backgroundColor: "rgba(0,0,0,0.6)", paddingVertical: 2, alignItems: "center" },
    thumbStampText: { color: "#fff", fontSize: 9, fontWeight: "700" },
    photoBtns: { flexDirection: "row", gap: 8 },
    mediaBtn: { flex: 1, paddingVertical: 14, alignItems: "center", borderRadius: 10 },
    mediaBtnText: { color: "#fff", fontWeight: "800", fontSize: 13 },
    sigImage: { width: "100%", height: 120, borderWidth: 1, borderRadius: 8, resizeMode: "contain", marginTop: 8 },
    price: { fontSize: 28, fontWeight: "900", letterSpacing: -0.5, fontVariant: ["tabular-nums"] },
    bigBtn: { paddingVertical: 16, alignItems: "center", borderRadius: 12 },
    bigBtnText: { color: "#fff", fontWeight: "800", letterSpacing: 0.5, fontSize: 16 },
    // modal
    modalBackdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.6)", justifyContent: "flex-end" },
    modalCard: { borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 24, paddingBottom: 32 },
    modalTitle: { fontSize: 20, fontWeight: "800", letterSpacing: -0.3 },
    modalSub: { fontSize: 13, marginTop: 4 },
    textArea: { borderWidth: 1, borderRadius: 10, padding: 14, marginTop: 12, minHeight: 120, fontSize: 16, textAlignVertical: "top" },
    input: { borderWidth: 1, borderRadius: 10, padding: 12, marginTop: 8, fontSize: 15 },
    modalBtn: { flex: 1, paddingVertical: 14, alignItems: "center", borderRadius: 10 },
    modalBtnText: { color: "#fff", fontWeight: "800", letterSpacing: 0.3 },
});
