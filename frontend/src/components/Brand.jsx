import { Lightning } from "@phosphor-icons/react";

export default function Brand({ size = "md", subtitle = false }) {
    const text = size === "lg" ? "text-2xl" : size === "sm" ? "text-base" : "text-xl";
    return (
        <div className="flex items-center gap-2" data-testid="brand-logo">
            <div className="relative flex h-9 w-9 items-center justify-center bg-[#1D4ED8] text-white">
                <Lightning weight="fill" size={20} />
                <span className="absolute -bottom-0 -right-0 h-2 w-2 bg-[#DC2626]" />
            </div>
            <div className="leading-none">
                <div className={`font-display font-extrabold tracking-tighter ${text}`}>
                    A1 <span className="text-[#DC2626]">Field</span> Pro
                </div>
                {subtitle && (
                    <div className="overline mt-1">by A1 HVAC N DE-GO</div>
                )}
            </div>
        </div>
    );
}
