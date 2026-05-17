/* Expo Notifications wiring: request perms, get push token, register with backend. */
import * as Notifications from "expo-notifications";
import * as Device from "expo-device";
import Constants from "expo-constants";
import { Platform } from "react-native";
import { api } from "./api";

// Show notification banners while app is foregrounded too
Notifications.setNotificationHandler({
    handleNotification: async () => ({
        shouldShowBanner: true,
        shouldShowList: true,
        shouldPlaySound: true,
        shouldSetBadge: false,
        shouldShowAlert: true,
    } as any),
});

export async function registerPushToken(): Promise<string | null> {
    if (!Device.isDevice) {
        // Push works on real devices only
        return null;
    }
    if (Platform.OS === "android") {
        await Notifications.setNotificationChannelAsync("default", {
            name: "default",
            importance: Notifications.AndroidImportance.HIGH,
            vibrationPattern: [0, 250, 250, 250],
            lightColor: "#1D4ED8",
        });
    }
    let { status } = await Notifications.getPermissionsAsync();
    if (status !== "granted") {
        const r = await Notifications.requestPermissionsAsync();
        status = r.status;
    }
    if (status !== "granted") return null;

    const projectId =
        (Constants?.expoConfig as any)?.extra?.eas?.projectId ||
        (Constants as any)?.easConfig?.projectId;
    try {
        const tokenData = await Notifications.getExpoPushTokenAsync(projectId ? { projectId } : undefined);
        const token = tokenData.data;
        await api.post("/push/expo-token", {
            token,
            device: `${Platform.OS} ${Device.modelName || ""}`,
            app_version: (Constants?.expoConfig as any)?.version || "",
        });
        return token;
    } catch (e) {
        return null;
    }
}

export function addNotificationTapHandler(onTap: (data: any) => void) {
    return Notifications.addNotificationResponseReceivedListener((response) => {
        const data = response.notification.request.content.data;
        onTap(data);
    });
}
