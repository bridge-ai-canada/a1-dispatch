import { useEffect, useState } from "react";
import { onInstallStateChange, promptInstall, isStandalone } from "../lib/pwa";
import { DeviceMobile, X, AppleLogo } from "@phosphor-icons/react";

const DISMISS_KEY = "a1-install-dismissed-v1";
const isIos = () => /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;
const isAndroid = () => /android/i.test(navigator.userAgent);

export default function InstallPrompt({ variant = "banner" }) {
    const [canInstall, setCanInstall] = useState(false);
    const [installed, setInstalled] = useState(isStandalone());
    const [dismissed, setDismissed] = useState(() => {
        try { return localStorage.getItem(DISMISS_KEY) === "1"; } catch { return false; }
    });
    const [showIosHelp, setShowIosHelp] = useState(false);

    useEffect(() => onInstallStateChange((s) => {
        setCanInstall(s.canInstall);
        setInstalled(s.installed);
    }), []);

    if (installed || dismissed) return null;

    const dismiss = () => {
        try { localStorage.setItem(DISMISS_KEY, "1"); } catch (_) {}
        setDismissed(true);
    };

    const install = async () => {
        if (canInstall) {
            const choice = await promptInstall();
            if (choice.outcome === "accepted") dismiss();
            return;
        }
        if (isIos()) setShowIosHelp(true);
    };

    // Don't show on desktop unless we have a real install prompt
    const isMobile = isIos() || isAndroid();
    if (!isMobile && !canInstall) return null;

    if (variant === "card") {
        return (
            <div data-testid="pwa-install-card"
                className="border border-slate-200 bg-white p-5 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                    <DeviceMobile size={28} weight="duotone" className="text-[#1D4ED8]" />
                    <div>
                        <div className="font-display text-lg font-extrabold tracking-tight">Install on your phone</div>
                        <p className="text-xs text-slate-500 mt-0.5">One-tap access to today's route, photos, signatures, and offline jobs.</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <button onClick={install} data-testid="pwa-install-button"
                        className="h-9 px-4 bg-[#1D4ED8] text-white text-sm font-semibold hover:opacity-90">
                        Install
                    </button>
                    <button onClick={dismiss} data-testid="pwa-dismiss-button" aria-label="Dismiss"
                        className="h-9 w-9 border border-slate-300 hover:bg-slate-50 flex items-center justify-center">
                        <X size={14} />
                    </button>
                </div>
                {showIosHelp && <IosHelpModal onClose={() => setShowIosHelp(false)} />}
            </div>
        );
    }

    return (
        <>
            <div data-testid="pwa-install-banner"
                className="fixed bottom-4 left-4 right-4 sm:left-auto sm:right-4 sm:w-[360px] z-40
                    bg-[#0F172A] text-white p-4 shadow-2xl border-l-4 border-[#DC2626]">
                <div className="flex items-start gap-3">
                    <DeviceMobile size={22} weight="duotone" className="text-blue-300 flex-shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                        <div className="font-semibold text-sm">Install A1 Field Pro</div>
                        <p className="text-xs text-slate-300 mt-0.5">Add to your home screen for instant access on the road.</p>
                        <div className="flex items-center gap-2 mt-3">
                            <button onClick={install} data-testid="pwa-install-button"
                                className="px-3 py-1.5 bg-[#DC2626] hover:opacity-90 text-xs font-semibold">
                                Install
                            </button>
                            <button onClick={dismiss} data-testid="pwa-dismiss-button"
                                className="px-3 py-1.5 hover:bg-slate-800 text-xs font-medium text-slate-300">
                                Not now
                            </button>
                        </div>
                    </div>
                    <button onClick={dismiss} aria-label="Close" className="text-slate-400 hover:text-white">
                        <X size={16} />
                    </button>
                </div>
            </div>
            {showIosHelp && <IosHelpModal onClose={() => setShowIosHelp(false)} />}
        </>
    );
}

function IosHelpModal({ onClose }) {
    return (
        <div data-testid="pwa-ios-help"
            className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
            onClick={onClose}>
            <div onClick={(e) => e.stopPropagation()}
                className="bg-white max-w-sm w-full p-6">
                <div className="flex items-center gap-2 mb-3">
                    <AppleLogo size={22} weight="fill" />
                    <div className="font-display text-xl font-extrabold tracking-tight">Add to Home Screen</div>
                </div>
                <ol className="text-sm text-slate-600 space-y-2.5 list-decimal pl-5">
                    <li>Tap the <strong>Share</strong> button at the bottom of Safari.</li>
                    <li>Scroll down and choose <strong>Add to Home Screen</strong>.</li>
                    <li>Tap <strong>Add</strong> in the top-right.</li>
                </ol>
                <button onClick={onClose}
                    className="mt-5 w-full h-10 bg-[#0F172A] text-white text-sm font-semibold hover:opacity-90">
                    Got it
                </button>
            </div>
        </div>
    );
}
