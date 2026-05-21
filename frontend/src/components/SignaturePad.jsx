import { useEffect, useRef, useState } from "react";

/**
 * SignaturePad — touch + mouse drawable canvas.
 * Calls onChange(dataUrl) when the user lifts their pointer.
 */
export default function SignaturePad({ onChange, height = 180 }) {
    const canvasRef = useRef(null);
    const drawingRef = useRef(false);
    const lastRef = useRef({ x: 0, y: 0 });
    const [empty, setEmpty] = useState(true);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ratio = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * ratio;
        canvas.height = rect.height * ratio;
        const ctx = canvas.getContext("2d");
        ctx.scale(ratio, ratio);
        ctx.lineWidth = 2.2;
        ctx.lineCap = "round";
        ctx.strokeStyle = "#0F172A";
    }, []);

    const pos = (e) => {
        const r = canvasRef.current.getBoundingClientRect();
        const p = e.touches ? e.touches[0] : e;
        return { x: p.clientX - r.left, y: p.clientY - r.top };
    };

    const start = (e) => {
        e.preventDefault();
        drawingRef.current = true;
        lastRef.current = pos(e);
    };
    const move = (e) => {
        if (!drawingRef.current) return;
        e.preventDefault();
        const ctx = canvasRef.current.getContext("2d");
        const p = pos(e);
        ctx.beginPath();
        ctx.moveTo(lastRef.current.x, lastRef.current.y);
        ctx.lineTo(p.x, p.y);
        ctx.stroke();
        lastRef.current = p;
        if (empty) setEmpty(false);
    };
    const end = () => {
        if (!drawingRef.current) return;
        drawingRef.current = false;
        const data = canvasRef.current.toDataURL("image/png");
        onChange?.(data);
    };

    const clear = () => {
        const c = canvasRef.current;
        const ctx = c.getContext("2d");
        ctx.clearRect(0, 0, c.width, c.height);
        setEmpty(true);
        onChange?.("");
    };

    return (
        <div className="rounded-xl border-2 border-dashed border-slate-300 bg-slate-50/50 overflow-hidden">
            <canvas
                ref={canvasRef}
                style={{ width: "100%", height: `${height}px`, touchAction: "none" }}
                onMouseDown={start} onMouseMove={move} onMouseUp={end} onMouseLeave={end}
                onTouchStart={start} onTouchMove={move} onTouchEnd={end}
                data-testid="signature-canvas"
            />
            <div className="flex items-center justify-between px-3 py-2 bg-white border-t border-slate-200">
                <span className="text-xs text-slate-500">
                    {empty ? "Sign with your finger or mouse" : "Signature captured"}
                </span>
                <button
                    type="button" onClick={clear}
                    className="text-xs font-semibold text-slate-600 hover:text-[#DC2626]"
                    data-testid="signature-clear-button"
                >
                    Clear
                </button>
            </div>
        </div>
    );
}
