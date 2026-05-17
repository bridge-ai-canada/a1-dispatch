/* A1 Field Pro service worker — offline cache + network-first API. */
const VERSION = "v1";
const SHELL_CACHE = `a1-shell-${VERSION}`;
const RUNTIME_CACHE = `a1-runtime-${VERSION}`;

const SHELL_ASSETS = ["/", "/manifest.json", "/offline.html"];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(SHELL_CACHE).then((c) => c.addAll(SHELL_ASSETS).catch(() => {}))
    );
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys
                    .filter((k) => k !== SHELL_CACHE && k !== RUNTIME_CACHE)
                    .map((k) => caches.delete(k))
            )
        )
    );
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    const req = event.request;
    if (req.method !== "GET") return;

    const url = new URL(req.url);

    // Never cache auth-sensitive backend calls or 3rd-party scripts.
    if (url.pathname.startsWith("/api/auth/") || url.pathname.startsWith("/api/payments/")) {
        return;
    }

    // API: network-first, fall back to cache (so a technician on flaky LTE still sees /api/jobs).
    if (url.pathname.startsWith("/api/")) {
        event.respondWith(
            fetch(req)
                .then((resp) => {
                    if (resp.ok && resp.status === 200) {
                        const clone = resp.clone();
                        caches.open(RUNTIME_CACHE).then((c) => c.put(req, clone));
                    }
                    return resp;
                })
                .catch(() => caches.match(req).then((r) => r || new Response("[]", {
                    status: 200, headers: { "Content-Type": "application/json" }
                })))
        );
        return;
    }

    // Navigation requests: network-first, fall back to cached shell, then offline.
    if (req.mode === "navigate") {
        event.respondWith(
            fetch(req).catch(() =>
                caches.match(req).then((r) => r || caches.match("/offline.html"))
            )
        );
        return;
    }

    // Static assets: cache-first.
    event.respondWith(
        caches.match(req).then((cached) =>
            cached ||
            fetch(req).then((resp) => {
                if (resp.ok && resp.type === "basic") {
                    const clone = resp.clone();
                    caches.open(RUNTIME_CACHE).then((c) => c.put(req, clone));
                }
                return resp;
            }).catch(() => cached)
        )
    );
});

// Push-notification scaffolding (backend not yet sending — ready for future Twilio/Resend/Web-Push integration).
self.addEventListener("push", (event) => {
    let data = { title: "A1 Field Pro", body: "You have an update" };
    try { data = event.data ? event.data.json() : data; } catch (_) {}
    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: data.icon || "https://customer-assets.emergentagent.com/job_a1-dispatch/artifacts/fpgawcoi_1000287215.png",
            badge: "https://customer-assets.emergentagent.com/job_a1-dispatch/artifacts/fpgawcoi_1000287215.png",
            data: { url: data.url || "/app/my-jobs" },
            tag: data.tag || "a1-update",
            renotify: true,
        })
    );
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    const target = event.notification.data?.url || "/app/my-jobs";
    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true }).then((all) => {
            for (const c of all) {
                if (c.url.includes(target) && "focus" in c) return c.focus();
            }
            return clients.openWindow(target);
        })
    );
});
