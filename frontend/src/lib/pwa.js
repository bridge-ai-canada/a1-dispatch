/* Service worker registration + install-prompt brokering. */

let deferredInstall = null;
const listeners = new Set();

export function onInstallStateChange(cb) {
    listeners.add(cb);
    cb({ canInstall: !!deferredInstall, installed: isStandalone() });
    return () => listeners.delete(cb);
}

function notify() {
    const state = { canInstall: !!deferredInstall, installed: isStandalone() };
    listeners.forEach((cb) => cb(state));
}

export function isStandalone() {
    if (typeof window === "undefined") return false;
    return (
        window.matchMedia?.("(display-mode: standalone)").matches ||
        window.navigator.standalone === true
    );
}

export async function promptInstall() {
    if (!deferredInstall) return { outcome: "unavailable" };
    deferredInstall.prompt();
    const choice = await deferredInstall.userChoice;
    deferredInstall = null;
    notify();
    return choice;
}

export function registerServiceWorker() {
    if (typeof window === "undefined" || !("serviceWorker" in navigator)) return;

    window.addEventListener("beforeinstallprompt", (e) => {
        e.preventDefault();
        deferredInstall = e;
        notify();
    });

    window.addEventListener("appinstalled", () => {
        deferredInstall = null;
        notify();
    });

    window.addEventListener("load", () => {
        navigator.serviceWorker
            .register("/sw.js", { scope: "/" })
            .catch((err) => {
                // Non-fatal — app still works without SW
                // eslint-disable-next-line no-console
                console.warn("SW registration failed:", err);
            });
    });
}
