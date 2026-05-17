/* Push subscription helpers for the frontend. */
import api from "./api";

function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const b64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    const raw = atob(b64);
    const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
}

export function isPushSupported() {
    return (
        typeof window !== "undefined" &&
        "serviceWorker" in navigator &&
        "PushManager" in window &&
        "Notification" in window
    );
}

export async function getPushPermission() {
    if (!isPushSupported()) return "unsupported";
    return Notification.permission;
}

export async function subscribeToPush() {
    if (!isPushSupported()) throw new Error("Push not supported in this browser");
    const reg = await navigator.serviceWorker.ready;
    const existing = await reg.pushManager.getSubscription();
    if (existing) {
        await api.post("/push/subscribe", {
            endpoint: existing.endpoint,
            keys: {
                p256dh: arrayBufferToBase64Url(existing.getKey("p256dh")),
                auth: arrayBufferToBase64Url(existing.getKey("auth")),
            },
            user_agent: navigator.userAgent,
        });
        return existing;
    }

    const perm = await Notification.requestPermission();
    if (perm !== "granted") throw new Error("Permission denied");

    const { data } = await api.get("/push/public-key");
    if (!data.public_key) throw new Error("Server not configured for push");

    const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(data.public_key),
    });

    await api.post("/push/subscribe", {
        endpoint: sub.endpoint,
        keys: {
            p256dh: arrayBufferToBase64Url(sub.getKey("p256dh")),
            auth: arrayBufferToBase64Url(sub.getKey("auth")),
        },
        user_agent: navigator.userAgent,
    });
    return sub;
}

export async function unsubscribeFromPush() {
    if (!isPushSupported()) return;
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (!sub) return;
    await api.delete(`/push/subscribe?endpoint=${encodeURIComponent(sub.endpoint)}`).catch(() => {});
    await sub.unsubscribe();
}

export async function currentSubscription() {
    if (!isPushSupported()) return null;
    const reg = await navigator.serviceWorker.ready;
    return reg.pushManager.getSubscription();
}

function arrayBufferToBase64Url(buf) {
    const bytes = new Uint8Array(buf);
    let str = "";
    for (let i = 0; i < bytes.byteLength; i++) str += String.fromCharCode(bytes[i]);
    return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
