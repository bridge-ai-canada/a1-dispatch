/* WebSocket realtime client for A1 Field Pro dispatch board. */
import { useEffect, useRef, useState } from "react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function getWsUrl(token) {
    const base = BACKEND_URL.replace(/^http/, "ws");
    return `${base}/api/ws?token=${encodeURIComponent(token)}`;
}

export function useDispatchSocket(onEvent) {
    const [connected, setConnected] = useState(false);
    const sockRef = useRef(null);
    const retryRef = useRef(0);
    const onEventRef = useRef(onEvent);
    onEventRef.current = onEvent;

    useEffect(() => {
        let cancelled = false;
        let timer;
        const token = localStorage.getItem("a1.token");
        if (!token) return;

        const connect = () => {
            if (cancelled) return;
            const ws = new WebSocket(getWsUrl(token));
            sockRef.current = ws;
            ws.onopen = () => { retryRef.current = 0; setConnected(true); };
            ws.onclose = () => {
                setConnected(false);
                if (cancelled) return;
                const wait = Math.min(30, 2 ** retryRef.current++) * 1000;
                timer = setTimeout(connect, wait);
            };
            ws.onerror = () => { try { ws.close(); } catch (_) {} };
            ws.onmessage = (e) => {
                try {
                    const msg = JSON.parse(e.data);
                    if (msg.type === "ping") {
                        try { ws.send(JSON.stringify({ type: "pong" })); } catch (_) {}
                        return;
                    }
                    onEventRef.current?.(msg);
                } catch (_) {}
            };
        };
        connect();
        return () => {
            cancelled = true;
            clearTimeout(timer);
            try { sockRef.current?.close(); } catch (_) {}
        };
    }, []);

    return { connected };
}
