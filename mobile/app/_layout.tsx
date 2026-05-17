import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { AuthProvider, useAuth } from "../lib/auth";
import { startAutoFlush } from "../lib/queue";
import { registerPushToken, addNotificationTapHandler } from "../lib/notifications";
import { Redirect, router } from "expo-router";
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

    useEffect(() => {
        if (!user) return;
        // Register with Expo Push + backend on every sign-in
        registerPushToken().catch(() => {});
        // Tap a notification → deep-link if it has a `url`
        const sub = addNotificationTapHandler((data) => {
            if (data?.url && typeof data.url === "string") {
                // strip leading '/app' or '/' to fit Expo Router shape; default to home
                const path = data.url.replace(/^\/app/, "").replace(/^\//, "");
                if (path.startsWith("jobs/")) router.push(`/(tabs)/${path}`);
                else router.push("/(tabs)");
            }
        });
        return () => sub?.remove?.();
    }, [user]);

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
