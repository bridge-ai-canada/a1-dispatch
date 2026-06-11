"""Public legal documents (privacy policy, terms of service).
Served via /api/legal/* and rendered as HTML — required by Google Play Console
for app submission. Static, no-auth, cacheable for 1 hour.
"""
from __future__ import annotations
import os
from datetime import datetime, timezone
from functools import lru_cache
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

router = APIRouter()

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "docs", "templates")
DOCS_DIR = os.path.normpath(DOCS_DIR)

# Map URL path -> (markdown filename, display title)
LEGAL_DOCS = {
    "privacy": ("PRIVACY_POLICY.md", "Privacy Policy"),
    "terms": ("TERMS_OF_SERVICE.md", "Terms of Service"),
}

_HTML_SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title} · A1 Field Pro</title>
<meta name="description" content="{title} for A1 Field Pro, the field-service management platform."/>
<style>
  :root {{ color-scheme: light; }}
  body {{
    margin: 0; padding: 0;
    background: #F8FAFC;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, sans-serif;
    color: #0F172A; line-height: 1.6;
  }}
  header {{
    background: linear-gradient(135deg, #1D4ED8, #0F172A);
    padding: 56px 24px; color: white;
  }}
  header .wrap {{ max-width: 760px; margin: 0 auto; }}
  header .badge {{
    display: inline-block; padding: 4px 10px;
    background: rgba(255,255,255,.16); border-radius: 4px;
    font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px;
  }}
  header h1 {{
    font-size: 40px; line-height: 1.1; margin: 12px 0 0;
    font-weight: 800; letter-spacing: -0.5px;
  }}
  header p {{ margin: 8px 0 0; color: rgba(255,255,255,.78); font-size: 14px; }}
  main {{ max-width: 760px; margin: 0 auto; padding: 40px 24px 96px; }}
  main h1, main h2, main h3 {{ color: #0F172A; line-height: 1.25; }}
  main h1 {{ font-size: 28px; margin-top: 32px; }}
  main h2 {{ font-size: 20px; margin-top: 32px; padding-top: 8px; border-top: 1px solid #E2E8F0; }}
  main h3 {{ font-size: 16px; margin-top: 20px; color: #1E293B; }}
  main p, main li {{ font-size: 15px; color: #334155; }}
  main code {{ background: #E2E8F0; padding: 1px 6px; border-radius: 3px; font-size: 13px; }}
  main hr {{ border: 0; border-top: 1px solid #E2E8F0; margin: 32px 0; }}
  main strong {{ color: #0F172A; }}
  footer {{
    border-top: 1px solid #E2E8F0; padding: 24px;
    text-align: center; color: #94A3B8; font-size: 13px;
  }}
  footer a {{ color: #1D4ED8; text-decoration: none; }}
  footer a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
  <header><div class="wrap">
    <span class="badge">{badge}</span>
    <h1>{title}</h1>
    <p>A1 Field Pro · Effective {effective}</p>
  </div></header>
  <main>{body}</main>
  <footer>
    A1 Field Pro · <a href="/api/legal/privacy">Privacy</a> · <a href="/api/legal/terms">Terms</a> · privacy@a1fieldpro.com
  </footer>
</body>
</html>
"""


def _md_to_html(md: str) -> str:
    """Very small inline markdown -> HTML converter (no external dep).
    Handles: # headings, **bold**, `code`, lists, --- hr, blank-line paragraphs, links.
    Sufficient for our maintained policy docs.
    """
    import re, html as _html
    lines = md.splitlines()
    out: list[str] = []
    in_ul = False
    buf: list[str] = []

    def flush_para():
        nonlocal buf
        if buf:
            text = " ".join(buf).strip()
            if text:
                out.append(f"<p>{_inline(text)}</p>")
            buf = []

    def _inline(s: str) -> str:
        s = _html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        return s

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            if in_ul:
                out.append("</ul>"); in_ul = False
            flush_para()
            continue
        if line.startswith("### "):
            if in_ul: out.append("</ul>"); in_ul = False
            flush_para(); out.append(f"<h3>{_inline(line[4:])}</h3>"); continue
        if line.startswith("## "):
            if in_ul: out.append("</ul>"); in_ul = False
            flush_para(); out.append(f"<h2>{_inline(line[3:])}</h2>"); continue
        if line.startswith("# "):
            if in_ul: out.append("</ul>"); in_ul = False
            flush_para(); out.append(f"<h1>{_inline(line[2:])}</h1>"); continue
        if line.strip() == "---":
            if in_ul: out.append("</ul>"); in_ul = False
            flush_para(); out.append("<hr/>"); continue
        if line.lstrip().startswith("- "):
            flush_para()
            if not in_ul: out.append("<ul>"); in_ul = True
            out.append(f"<li>{_inline(line.lstrip()[2:])}</li>")
            continue
        if in_ul: out.append("</ul>"); in_ul = False
        buf.append(line)
    if in_ul: out.append("</ul>")
    flush_para()
    return "\n".join(out)


@lru_cache(maxsize=8)
def _load(slug: str) -> tuple[str, str]:
    if slug not in LEGAL_DOCS:
        raise FileNotFoundError(slug)
    fname, title = LEGAL_DOCS[slug]
    path = os.path.join(DOCS_DIR, fname)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        md = f.read()
    today = datetime.now(timezone.utc).strftime("%B %Y")
    md = md.replace("[DATE]", today)
    return title, _md_to_html(md)


@router.get("/legal/{slug}.txt", response_class=PlainTextResponse)
async def legal_text(slug: str):
    if slug not in LEGAL_DOCS:
        raise HTTPException(status_code=404, detail="Document not found")
    fname, _ = LEGAL_DOCS[slug]
    path = os.path.join(DOCS_DIR, fname)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Document not found")
    with open(path, "r", encoding="utf-8") as f:
        return Response(content=f.read(), media_type="text/plain; charset=utf-8",
                        headers={"Cache-Control": "public, max-age=3600"})


@router.get("/legal/{slug}", response_class=HTMLResponse)
async def legal_html(slug: str):
    try:
        title, body = _load(slug)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    effective = datetime.now(timezone.utc).strftime("%B %Y")
    badge = "LEGAL" if slug == "terms" else "PRIVACY"
    html = _HTML_SHELL.format(title=title, badge=badge, effective=effective, body=body)
    return HTMLResponse(content=html, headers={"Cache-Control": "public, max-age=3600"})
