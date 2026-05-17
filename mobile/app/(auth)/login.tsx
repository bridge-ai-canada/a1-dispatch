import { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator, KeyboardAvoidingView, Platform } from "react-native";
import { useAuth } from "../../lib/auth";
import { colors } from "../../lib/theme";
import { router } from "expo-router";

export default function LoginScreen() {
    const { signIn } = useAuth();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [err, setErr] = useState("");
    const [busy, setBusy] = useState(false);

    const submit = async () => {
        setErr(""); setBusy(true);
        try {
            await signIn(email.trim(), password);
            router.replace("/(tabs)");
        } catch (e: any) {
            setErr(e.response?.data?.detail || "Sign-in failed");
        } finally {
            setBusy(false);
        }
    };

    return (
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={s.wrap}>
            <View style={s.card}>
                <Text style={s.kicker}>A1 FIELD PRO</Text>
                <Text style={s.title}>Welcome back</Text>
                <Text style={s.sub}>Sign in to see today's route.</Text>

                <Text style={s.label}>Email</Text>
                <TextInput value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address"
                    style={s.input} placeholder="you@company.com" placeholderTextColor={colors.muted} />

                <Text style={s.label}>Password</Text>
                <TextInput value={password} onChangeText={setPassword} secureTextEntry
                    style={s.input} placeholder="••••••••" placeholderTextColor={colors.muted} />

                {!!err && <Text style={s.err}>{err}</Text>}

                <TouchableOpacity onPress={submit} disabled={busy} style={[s.btn, busy && { opacity: 0.6 }]}>
                    {busy ? <ActivityIndicator color="#fff" /> : <Text style={s.btnText}>Sign in</Text>}
                </TouchableOpacity>
            </View>
        </KeyboardAvoidingView>
    );
}

const s = StyleSheet.create({
    wrap: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.soft, padding: 24 },
    card: { width: "100%", maxWidth: 380, backgroundColor: colors.paper, padding: 32, borderColor: colors.line, borderWidth: 1 },
    kicker: { fontSize: 11, letterSpacing: 2, color: colors.accent, fontWeight: "800" },
    title: { fontSize: 28, fontWeight: "800", letterSpacing: -0.5, color: colors.ink, marginTop: 8 },
    sub: { fontSize: 13, color: colors.muted, marginTop: 4, marginBottom: 24 },
    label: { fontSize: 11, fontWeight: "600", color: colors.ink, marginTop: 12, marginBottom: 4 },
    input: { borderWidth: 1, borderColor: colors.line, paddingHorizontal: 12, paddingVertical: 12, color: colors.ink, fontSize: 15 },
    err: { color: colors.accent, fontSize: 12, marginTop: 12 },
    btn: { marginTop: 24, backgroundColor: colors.primary, paddingVertical: 14, alignItems: "center" },
    btnText: { color: "#fff", fontWeight: "700", letterSpacing: 0.5 },
});
