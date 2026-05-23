import { Tabs } from "expo-router";
import { useTheme } from "../../lib/theme";

export default function TabsLayout() {
    const { palette } = useTheme();
    return (
        <Tabs
            screenOptions={{
                tabBarActiveTintColor: palette.primary,
                tabBarInactiveTintColor: palette.muted,
                tabBarStyle: {
                    borderTopColor: palette.line,
                    backgroundColor: palette.paper,
                    height: 64,
                    paddingTop: 6,
                    paddingBottom: 8,
                },
                tabBarLabelStyle: { fontSize: 11, fontWeight: "700", letterSpacing: 0.3 },
                headerStyle: { backgroundColor: palette.ink },
                headerTintColor: "#fff",
                headerTitleStyle: { letterSpacing: 0.5, fontWeight: "800" },
            }}>
            <Tabs.Screen name="index" options={{ title: "Today" }} />
            <Tabs.Screen name="all" options={{ title: "All jobs" }} />
            <Tabs.Screen name="timesheet" options={{ title: "Timesheet" }} />
            <Tabs.Screen name="settings" options={{ title: "Settings" }} />
            <Tabs.Screen name="profile" options={{ title: "Profile" }} />
            <Tabs.Screen name="jobs/[id]" options={{ href: null, title: "Job" }} />
        </Tabs>
    );
}
