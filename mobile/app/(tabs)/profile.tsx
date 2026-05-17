import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { useAuth } from "../../lib/auth";
import { colors } from "../../lib/theme";

export default function Profile() {
    const { user, signOut } = useAuth();
    return (
        <View style={s.wrap}>
            <View style={s.card}>
                <Text style={s.kicker}>SIGNED IN</Text>
                <Text style={s.name}>{user?.name}</Text>
                <Text style={s.email}>{user?.email}</Text>
                <View style={s.roleBadge}>
                    <Text style={s.roleText}>{user?.role?.toUpperCase()}</Text>
                </View>
            </View>
            <TouchableOpacity onPress={signOut} style={s.btn}>
                <Text style={s.btnText}>Sign out</Text>
            </TouchableOpacity>
            <Text style={s.footer}>A1 Field Pro · Mobile</Text>
        </View>
    );
}

const s = StyleSheet.create({
    wrap: { flex: 1, backgroundColor: colors.soft, padding: 16 },
    card: { backgroundColor: colors.paper, borderColor: colors.line, borderWidth: 1, padding: 24 },
    kicker: { fontSize: 11, letterSpacing: 2, color: colors.accent, fontWeight: "800" },
    name: { fontSize: 24, fontWeight: "800", color: colors.ink, marginTop: 6, letterSpacing: -0.4 },
    email: { fontSize: 14, color: colors.muted, marginTop: 2 },
    roleBadge: { alignSelf: "flex-start", backgroundColor: colors.ink, paddingHorizontal: 8, paddingVertical: 3, marginTop: 14 },
    roleText: { fontSize: 10, color: "#fff", letterSpacing: 1.4, fontWeight: "700" },
    btn: { marginTop: 16, backgroundColor: colors.accent, paddingVertical: 14, alignItems: "center" },
    btnText: { color: "#fff", fontWeight: "800", letterSpacing: 0.5 },
    footer: { textAlign: "center", color: colors.muted, fontSize: 11, marginTop: 32 },
});
