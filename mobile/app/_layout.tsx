import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { AuthProvider, useAuth } from "../lib/auth";
import { startAutoFlush } from "../lib/queue";
import { registerPushToken, addNotificationTapHandler } from "../lib/notifications";
import { ThemeProvider, useTheme } from "../lib/theme";
import { Redirect, router } from "expo-router";
import { View, ActivityIndicator, useColorScheme } from "react-native";
import { useEffect } from "react";

export default function RootLayout() {
    useEffect(() => { startAutoFlush(); }, []);
    const scheme = useColorScheme();
    return (
        <ThemeProvider systemDark={scheme === "dark"}>
            <AuthProvider>
                <Shell />
            </AuthProvider>
        </ThemeProvider>
    );
}

function Shell() {
    const { isDark, palette } = useTheme();
    return (
        <>
            <StatusBar style={isDark ? "light" : "dark"} />
            <Gate palette={palette} />
        </>
    );
}

function Gate({ palette }: { palette: any }) {
    const { user, loading } = useAuth();

    useEffect(() => {
        if (!user) return;
        registerPushToken().catch(() => {});
        const sub = addNotificationTapHandler((data) => {
            if (data?.url && typeof data.url === "string") {
                const path = data.url.replace(/^\/app/, "").replace(/^\//, "");
                if (path.startsWith("jobs/")) router.push(`/(tabs)/${path}`);
                else router.push("/(tabs)");
            }
        });
        return () => sub?.remove?.();
    }, [user]);

    if (loading) {
        return (
            <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: palette.soft }}>
                <ActivityIndicator color={palette.primary} />
            </View>
        );
    }
    if (!user) return <Redirect href="/(auth)/login" />;
    return (
        <Stack screenOptions={{ headerStyle: { backgroundColor: palette.ink }, headerTintColor: "#fff" }}>
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="(auth)/login" options={{ headerShown: false }} />
        </Stack>
    );
}
