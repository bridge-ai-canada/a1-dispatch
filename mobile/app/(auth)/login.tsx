import { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator, KeyboardAvoidingView, Platform } from "react-native";
import { useAuth } from "../../lib/auth";
import { useTheme } from "../../lib/theme";
import { router } from "expo-router";

export default function LoginScreen() {
    const { signIn } = useAuth();
    const { palette } = useTheme();
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
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"}
            style={[s.wrap, { backgroundColor: palette.soft }]}>
            <View style={[s.card, { backgroundColor: palette.paper, borderColor: palette.line }]}>
                <Text style={[s.kicker, { color: palette.accent }]}>A1 FIELD PRO</Text>
                <Text style={[s.title, { color: palette.ink }]}>Welcome back</Text>
                <Text style={[s.sub, { color: palette.muted }]}>Sign in to see today's route.</Text>

                <Text style={[s.label, { color: palette.ink }]}>Email</Text>
                <TextInput value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address"
                    style={[s.input, { borderColor: palette.line, color: palette.ink }]}
                    placeholder="you@company.com" placeholderTextColor={palette.muted}
                    accessibilityLabel="email-input" />

                <Text style={[s.label, { color: palette.ink }]}>Password</Text>
                <TextInput value={password} onChangeText={setPassword} secureTextEntry
                    style={[s.input, { borderColor: palette.line, color: palette.ink }]}
                    placeholder="••••••••" placeholderTextColor={palette.muted}
                    accessibilityLabel="password-input" />

                {!!err && <Text style={[s.err, { color: palette.accent }]}>{err}</Text>}

                <TouchableOpacity onPress={submit} disabled={busy}
                    style={[s.btn, { backgroundColor: palette.primary }, busy && { opacity: 0.6 }]}
                    accessibilityLabel="sign-in-button">
                    {busy ? <ActivityIndicator color="#fff" /> : <Text style={s.btnText}>Sign in</Text>}
                </TouchableOpacity>
            </View>
        </KeyboardAvoidingView>
    );
}

const s = StyleSheet.create({
    wrap: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
    card: { width: "100%", maxWidth: 380, padding: 32, borderWidth: 1, borderRadius: 12 },
    kicker: { fontSize: 11, letterSpacing: 2, fontWeight: "800" },
    title: { fontSize: 32, fontWeight: "800", letterSpacing: -0.5, marginTop: 8 },
    sub: { fontSize: 14, marginTop: 4, marginBottom: 24 },
    label: { fontSize: 11, fontWeight: "700", marginTop: 12, marginBottom: 6, letterSpacing: 0.4 },
    input: { borderWidth: 1, paddingHorizontal: 14, paddingVertical: 14, fontSize: 16, borderRadius: 10 },
    err: { fontSize: 13, marginTop: 12, fontWeight: "600" },
    btn: { marginTop: 24, paddingVertical: 18, alignItems: "center", borderRadius: 12 },
    btnText: { color: "#fff", fontWeight: "800", letterSpacing: 0.5, fontSize: 16 },
});
