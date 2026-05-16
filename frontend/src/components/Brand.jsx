import { useAuth } from "../context/AuthContext";

const LOGO_URL = "https://customer-assets.emergentagent.com/job_a1-dispatch/artifacts/fpgawcoi_1000287215.png";

export default function Brand({ size = "md", subtitle = false, variant = "default" }) {
    const { company } = useAuth?.() || { company: null };
    const branded = company?.branding || {};
    const logoSrc = branded.logo_path
        ? `${process.env.REACT_APP_BACKEND_URL}/api/files/${branded.logo_path}`
        : LOGO_URL;
    const showCompanyName = variant === "company" && company?.name;

    const h = size === "lg" ? "h-12" : size === "sm" ? "h-7" : "h-9";

    return (
        <div className="flex items-center gap-3" data-testid="brand-logo">
            <img src={logoSrc} alt="A1 Field Pro" className={`${h} w-auto`} />
            {showCompanyName ? (
                <div className="leading-none">
                    <div className="font-display font-extrabold tracking-tighter text-lg">{company.name}</div>
                    {subtitle && <div className="overline mt-1">Powered by A1 Field Pro</div>}
                </div>
            ) : (
                subtitle && <div className="overline">by A1 HVAC N DE-GO</div>
            )}
        </div>
    );
}
