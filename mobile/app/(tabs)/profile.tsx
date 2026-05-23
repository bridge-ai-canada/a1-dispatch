import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from "react-native";
import { useAuth } from "../../lib/auth";
import { useTheme } from "../../lib/theme";

export default function Profile() {
    const { user, signOut } = useAuth();
    const { palette } = useTheme();
    return (
        <ScrollView style={{ backgroundColor: palette.soft }} contentContainerStyle={{ padding: 16 }}>
            <View style={[s.card, { backgroundColor: palette.paper, borderColor: palette.line }]}>
                <Text style={[s.kicker, { color: palette.accent }]}>SIGNED IN</Text>
                <Text style={[s.name, { color: palette.ink }]}>{user?.name}</Text>
                <Text style={[s.email, { color: palette.muted }]}>{user?.email}</Text>
                <View style={[s.roleBadge, { backgroundColor: palette.ink }]}>
                    <Text style={s.roleText}>{user?.role?.toUpperCase()}</Text>
                </View>
            </View>
            <TouchableOpacity onPress={signOut} style={[s.btn, { backgroundColor: palette.accent }]}>
                <Text style={s.btnText}>Sign out</Text>
            </TouchableOpacity>
            <Text style={[s.footer, { color: palette.muted }]}>A1 Field Pro · Mobile</Text>
        </ScrollView>
    );
}

const s = StyleSheet.create({
    card: { padding: 24, borderWidth: 1, borderRadius: 12 },
    kicker: { fontSize: 11, letterSpacing: 2, fontWeight: "800" },
    name: { fontSize: 24, fontWeight: "800", marginTop: 6, letterSpacing: -0.4 },
    email: { fontSize: 14, marginTop: 2 },
    roleBadge: { alignSelf: "flex-start", paddingHorizontal: 10, paddingVertical: 4, marginTop: 14, borderRadius: 4 },
    roleText: { fontSize: 10, color: "#fff", letterSpacing: 1.4, fontWeight: "700" },
    btn: { marginTop: 16, paddingVertical: 16, alignItems: "center", borderRadius: 12 },
    btnText: { color: "#fff", fontWeight: "800", letterSpacing: 0.5 },
    footer: { textAlign: "center", fontSize: 11, marginTop: 32 },
});
