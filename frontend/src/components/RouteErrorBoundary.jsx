import { Component } from "react";

/**
 * Tiny error boundary used to catch lazy-chunk load failures (network flakes,
 * stale builds after a deploy). Shows a retry button instead of a forever-spinner.
 */
export default class RouteErrorBoundary extends Component {
    constructor(props) {
        super(props);
        this.state = { error: null };
    }

    static getDerivedStateFromError(error) {
        return { error };
    }

    componentDidCatch(error, info) {
        // eslint-disable-next-line no-console
        console.error("Route error:", error, info);
    }

    handleRetry = () => {
        this.setState({ error: null });
        // Force a fresh fetch of the chunk by reloading.
        window.location.reload();
    };

    render() {
        if (!this.state.error) return this.props.children;
        const msg = String(this.state.error?.message || this.state.error);
        const isChunk = /chunk|Loading.*failed|Failed to fetch dynamically/i.test(msg);
        return (
            <div className="min-h-[40vh] flex flex-col items-center justify-center gap-4 p-8 text-center" data-testid="route-error">
                <div className="text-3xl">⚠</div>
                <div className="font-bold text-lg">{isChunk ? "Could not load page" : "Something went wrong"}</div>
                <div className="text-sm text-slate-500 max-w-md">
                    {isChunk
                        ? "This usually means a new version was deployed. Reloading will pull the latest."
                        : msg.slice(0, 200)}
                </div>
                <button
                    onClick={this.handleRetry}
                    className="px-4 py-2 rounded-lg bg-[#1D4ED8] text-white text-sm font-bold hover:opacity-90 transition-opacity"
                    data-testid="route-error-retry"
                >
                    Reload
                </button>
            </div>
        );
    }
}
