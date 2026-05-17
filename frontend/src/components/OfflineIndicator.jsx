import { useEffect, useState } from "react";
import { CloudSlash } from "@phosphor-icons/react";

export default function OfflineIndicator() {
    const [online, setOnline] = useState(
        typeof navigator !== "undefined" ? navigator.onLine : true
    );

    useEffect(() => {
        const up = () => setOnline(true);
        const down = () => setOnline(false);
        window.addEventListener("online", up);
        window.addEventListener("offline", down);
        return () => {
            window.removeEventListener("online", up);
            window.removeEventListener("offline", down);
        };
    }, []);

    if (online) return null;
    return (
        <div data-testid="offline-indicator"
            className="bg-[#DC2626] text-white text-xs font-semibold tracking-wider uppercase
                px-4 py-1.5 flex items-center justify-center gap-2">
            <CloudSlash size={14} weight="bold" />
            Offline · showing last-synced jobs
        </div>
    );
}
