import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { AuthProvider, useAuth } from "../lib/auth";
import { startAutoFlush } from "../lib/queue";
import { Redirect } from "expo-router";
import { View, ActivityIndicator } from "react-native";
import { useEffect } from "react";
import { colors } from "../lib/theme";

export default function RootLayout() {
    useEffect(() => { startAutoFlush(); }, []);
    return (
        <AuthProvider>
            <StatusBar style="dark" />
            <Gate />
        </AuthProvider>
    );
}

function Gate() {
    const { user, loading } = useAuth();
    if (loading) {
        return (
            <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.soft }}>
                <ActivityIndicator color={colors.primary} />
            </View>
        );
    }
    if (!user) return <Redirect href="/(auth)/login" />;
    return (
        <Stack screenOptions={{ headerStyle: { backgroundColor: colors.ink }, headerTintColor: "#fff" }}>
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="(auth)/login" options={{ headerShown: false }} />
        </Stack>
    );
}
