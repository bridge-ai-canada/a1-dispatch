import { useAuth } from "../context/AuthContext";

const LOGO_URL = "/brand/a1-field-pro-logo.png";

export default function Brand({ size = "md", subtitle = false, variant = "default" }) {
    const { company } = useAuth?.() || { company: null };
    const branded = company?.branding || {};
    const useCompanyLogo = variant === "company" && branded.logo_path;
    const logoSrc = useCompanyLogo
        ? `${process.env.REACT_APP_BACKEND_URL}/api/files/${branded.logo_path}`
        : LOGO_URL;
    const showCompanyName = variant === "company" && company?.name;

    const h = size === "lg" ? "h-14" : size === "sm" ? "h-9" : "h-11";
    const text = size === "lg" ? "text-2xl" : size === "sm" ? "text-base" : "text-xl";

    return (
        <div className="flex items-center gap-2.5" data-testid="brand-logo">
            <img src={logoSrc} alt="A1 Field Pro" className={`${h} w-auto object-contain`} />
            {showCompanyName ? (
                <div className="leading-none">
                    <div className="font-display font-extrabold tracking-tighter text-lg">{company.name}</div>
                    {subtitle && <div className="overline mt-1">Powered by A1 Field Pro</div>}
                </div>
            ) : (
                <div className="leading-none hidden sm:block">
                    <div className={`font-display font-extrabold tracking-tighter ${text}`}>
                        <span className="text-[#F97316]">A1</span> <span className="text-[#1E3A8A]">field</span><span className="text-[#F97316]">pro</span>
                    </div>
                    {subtitle && <div className="overline mt-1 text-[#1E3A8A]">Field Service App</div>}
                </div>
            )}
        </div>
    );
}
