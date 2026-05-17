import { Tabs } from "expo-router";
import { colors } from "../../lib/theme";

export default function TabsLayout() {
    return (
        <Tabs
            screenOptions={{
                tabBarActiveTintColor: colors.primary,
                tabBarInactiveTintColor: colors.muted,
                tabBarStyle: { borderTopColor: colors.line },
                headerStyle: { backgroundColor: colors.ink },
                headerTintColor: "#fff",
                headerTitleStyle: { letterSpacing: 0.5 },
            }}>
            <Tabs.Screen name="index" options={{ title: "Today" }} />
            <Tabs.Screen name="all" options={{ title: "All jobs" }} />
            <Tabs.Screen name="profile" options={{ title: "Profile" }} />
            <Tabs.Screen name="jobs/[id]" options={{ href: null, title: "Job" }} />
        </Tabs>
    );
}
