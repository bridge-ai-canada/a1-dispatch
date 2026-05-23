import { useEffect, useState } from "react";
import { View, Text, StyleSheet, Switch, TouchableOpacity, Alert, ScrollView } from "react-native";
import { useTheme } from "../../lib/theme";
import { useAuth } from "../../lib/auth";
import * as Notifications from "expo-notifications";
import { router } from "expo-router";
import { queueSize, flush } from "../../lib/queue";

export default function Settings() {
    const { palette, mode, setMode, isDark } = useTheme();
    const { signOut } = useAuth();
    const [pushOn, setPushOn] = useState(false);
    const [pending, setPending] = useState(0);

    useEffect(() => {
        Notifications.getPermissionsAsync().then((p) => setPushOn(p.granted));
        queueSize().then(setPending);
    }, []);

    const togglePush = async (v: boolean) => {
        if (v) {
            const r = await Notifications.requestPermissionsAsync();
            setPushOn(r.granted);
            if (!r.granted) Alert.alert("Permission denied", "Enable notifications in your device settings.");
        } else {
            Alert.alert("Disable push", "To turn off notifications, change permissions in your device's Settings app.");
        }
    };

    const sync = async () => {
        const r = await flush();
        setPending(r.remaining);
        Alert.alert("Sync", r.sent ? `Sent ${r.sent}, ${r.remaining} remaining` : "Nothing to sync");
    };

    return (
        <ScrollView style={{ backgroundColor: palette.soft }} contentContainerStyle={{ padding: 16, paddingBottom: 32 }}>
            {/* Theme */}
            <Text style={[s.section, { color: palette.muted }]}>APPEARANCE</Text>
            <View style={[s.card, { backgroundColor: palette.paper, borderColor: palette.line }]}>
                {(["light", "dark", "system"] as const).map((m) => (
                    <TouchableOpacity key={m} onPress={() => setMode(m)}
                        style={[s.optionRow, { borderColor: palette.line }]}
                        accessibilityLabel={`Set theme ${m}`}>
                        <Text style={[s.optionLabel, { color: palette.ink }]}>
                            {m === "light" ? "☀️  Light" : m === "dark" ? "🌙  Dark" : "📱  Follow system"}
                        </Text>
                        {mode === m && <View style={[s.dot, { backgroundColor: palette.primary }]} />}
                    </TouchableOpacity>
                ))}
            </View>

            {/* Notifications */}
            <Text style={[s.section, { color: palette.muted }]}>NOTIFICATIONS</Text>
            <View style={[s.card, { backgroundColor: palette.paper, borderColor: palette.line }]}>
                <View style={s.optionRow}>
                    <Text style={[s.optionLabel, { color: palette.ink }]}>🔔  Push notifications</Text>
                    <Switch value={pushOn} onValueChange={togglePush} />
                </View>
                <Text style={[s.helpText, { color: palette.muted }]}>
                    Get notified when jobs are assigned, updated, or payments come in.
                </Text>
            </View>

            {/* Offline / Sync */}
            <Text style={[s.section, { color: palette.muted }]}>OFFLINE & SYNC</Text>
            <View style={[s.card, { backgroundColor: palette.paper, borderColor: palette.line }]}>
                <View style={s.optionRow}>
                    <Text style={[s.optionLabel, { color: palette.ink }]}>📦  Pending changes</Text>
                    <Text style={[s.metaPill, { backgroundColor: pending > 0 ? palette.warn : palette.surface2, color: pending > 0 ? "#fff" : palette.muted }]}>
                        {pending}
                    </Text>
                </View>
                <TouchableOpacity onPress={sync}
                    style={[s.bigBtn, { backgroundColor: palette.primary }]}>
                    <Text style={s.bigBtnText}>Sync now</Text>
                </TouchableOpacity>
            </View>

            {/* About */}
            <Text style={[s.section, { color: palette.muted }]}>ABOUT</Text>
            <View style={[s.card, { backgroundColor: palette.paper, borderColor: palette.line, padding: 16 }]}>
                <Text style={[s.aboutTitle, { color: palette.ink }]}>A1 Field Pro Mobile</Text>
                <Text style={[s.aboutMeta, { color: palette.muted }]}>v1.0 · For field technicians</Text>
            </View>

            <TouchableOpacity onPress={signOut}
                style={[s.bigBtn, { backgroundColor: palette.accent, marginTop: 24 }]}>
                <Text style={s.bigBtnText}>Sign out</Text>
            </TouchableOpacity>
        </ScrollView>
    );
}

const s = StyleSheet.create({
    section: { fontSize: 11, letterSpacing: 1.5, fontWeight: "800", marginTop: 16, marginBottom: 8, paddingHorizontal: 4 },
    card: { borderRadius: 12, borderWidth: 1, overflow: "hidden" },
    optionRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 16, borderTopWidth: 1, borderTopColor: "transparent" },
    optionLabel: { fontSize: 15, fontWeight: "600" },
    helpText: { fontSize: 12, padding: 12, paddingTop: 0 },
    dot: { width: 12, height: 12, borderRadius: 6 },
    metaPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, fontSize: 12, fontWeight: "800", overflow: "hidden" },
    bigBtn: { paddingVertical: 16, alignItems: "center", borderRadius: 0, margin: 0 },
    bigBtnText: { color: "#fff", fontWeight: "800", letterSpacing: 0.5, fontSize: 15 },
    aboutTitle: { fontSize: 16, fontWeight: "800" },
    aboutMeta: { fontSize: 12, marginTop: 2 },
});
