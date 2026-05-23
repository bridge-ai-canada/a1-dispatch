"""AI service powered by the Emergent Universal LLM key.

All AI features in A1 Field Pro funnel through this module so we can:
- Centralize prompts
- Log token usage to the `ai_logs` collection
- Swap models per use-case (cost vs. quality)
- Gracefully degrade if the LLM is unavailable
"""
import os
import json
import re
import uuid
import logging
from typing import Optional, List, Dict, Any

from emergentintegrations.llm.chat import LlmChat, UserMessage

from deps import db, now_iso

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

MODEL_PRIMARY = "gpt-4o"           # high-value, structured outputs
MODEL_LIGHT = "gpt-4o-mini"        # high-volume chat & quick suggestions


# -------------------- Prompt library --------------------
SYSTEM_DISPATCHER = (
    "You are A1 Field Pro's AI dispatcher assistant. You help schedule field service jobs. "
    "Be concise. Answer in plain English. Use bullet lists where helpful. "
    "When suggesting a technician/time, name them and explain why in 1 sentence. "
    "Never invent technicians or jobs that aren't in the provided context."
)

SYSTEM_TECH_NOTES = (
    "You are a field-service technician's writing assistant. Rewrite rough on-site notes into "
    "a clean, professional 3-5 sentence summary suitable for a customer-facing invoice. "
    "Be factual. Use past tense. Do NOT add details that weren't in the original notes."
)

SYSTEM_JOB_SUMMARY = (
    "You are a field-service technician's writing assistant. Given the job context, "
    "produce a single-paragraph job summary (≤80 words) suitable to appear on the invoice. "
    "Be factual; only use information provided. Use clear, friendly homeowner language."
)

SYSTEM_CALL_SUMMARY = (
    "You are an admin AI assistant. Convert a phone-call transcript or notes into a structured "
    "JSON summary. Be conservative — never invent data."
)

SYSTEM_ESTIMATE_GEN = (
    "You are A1 Field Pro's AI estimator. Given a homeowner's described problem and the "
    "service business context, generate THREE pricing tiers (good, better, best) with realistic "
    "line items and prices for the US market. Output JSON only.\n\n"
    "EXACT output schema:\n"
    "{\n"
    "  \"title\": str,\n"
    "  \"intro\": str (1 sentence customer-facing intro),\n"
    "  \"tiers\": [\n"
    "    { \"key\": \"good\",   \"name\": str, \"summary\": str, \"featured\": false, \"line_items\": [...], \"addons\": [] },\n"
    "    { \"key\": \"better\", \"name\": str, \"summary\": str, \"featured\": true,  \"line_items\": [...], \"addons\": [...] },\n"
    "    { \"key\": \"best\",   \"name\": str, \"summary\": str, \"featured\": false, \"line_items\": [...], \"addons\": [] }\n"
    "  ]\n"
    "}\n"
    "Each line_item: { description, qty, unit_price, taxable: true, kind: one of (service|material|labor|fee) }\n"
    "Each addon (only in better tier, 1-3 items): { description, qty, unit_price, taxable: true, selected: false, kind: material }\n\n"
    "Rules:\n"
    "- 'good' = minimal/repair-focused, lowest price.\n"
    "- 'better' = featured solution with mid-range materials, set featured=true.\n"
    "- 'best' = premium solution with top materials and longest warranty.\n"
    "- Each tier needs 2-5 line_items.\n"
    "- Prices in USD, sensible for the trade/region."
)

SYSTEM_UPSELL = (
    "You are A1 Field Pro's AI sales coach. Given a job's context and the customer history, "
    "suggest exactly ONE high-relevance upsell or maintenance recommendation. "
    "Output JSON only: { \"title\": str, \"reason\": str, \"suggested_price\": number, \"confidence\": float 0-1 }. "
    "Confidence < 0.5 if data is sparse. Never fabricate equipment that isn't implied."
)

SYSTEM_MAINTENANCE = (
    "You are A1 Field Pro's AI maintenance scheduler. Given a list of past jobs for one customer, "
    "decide whether they're due for a recurring service. Output JSON only: "
    "{ \"is_due\": bool, \"service_type\": str, \"reason\": str, \"recommended_cadence\": "
    "\"monthly|quarterly|biannual|annual\" }. is_due=true only if the gap since the last "
    "comparable service exceeds the typical industry cadence for the trade."
)

SYSTEM_CHATBOT_HYBRID = (
    "You are A1 Field Pro's friendly customer assistant for {company_name}. Detect intent "
    "from the user's message:\n"
    "- SALES intent (e.g. asking for prices, hours, areas served, wanting to book): be helpful, "
    "answer FAQs in 1-3 sentences, and end with a soft CTA to book.\n"
    "- SUPPORT intent (existing customer asking about their job, invoice, schedule): tell them "
    "they can look it up in their customer portal and offer to text them the link.\n"
    "Keep responses warm, under 80 words. Never invent specific prices. Never claim to be a human."
)


# -------------------- Logging helper --------------------
async def _log(company_id: Optional[str], user_id: Optional[str], feature: str,
               model: str, success: bool, error: Optional[str] = None,
               input_chars: int = 0, output_chars: int = 0):
    try:
        await db.ai_logs.insert_one({
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "user_id": user_id,
            "feature": feature,
            "model": model,
            "success": bool(success),
            "error": (error or "")[:500],
            "input_chars": int(input_chars),
            "output_chars": int(output_chars),
            "created_at": now_iso(),
        })
    except Exception:
        pass


# -------------------- Core call --------------------
async def _call(
    *, system: str, prompt: str, session_id: str,
    model: str = MODEL_PRIMARY, feature: str,
    company_id: Optional[str] = None, user_id: Optional[str] = None,
    json_output: bool = False,
) -> str:
    if not EMERGENT_LLM_KEY:
        raise RuntimeError("AI is not configured (missing EMERGENT_LLM_KEY)")
    full_system = system + ("\n\nRespond with valid JSON only." if json_output else "")
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=full_system,
    ).with_model("openai", model)
    try:
        result = await chat.send_message(UserMessage(text=prompt))
        text = result if isinstance(result, str) else str(result)
        await _log(company_id, user_id, feature, model, True,
                   input_chars=len(prompt), output_chars=len(text))
        return text
    except Exception as e:
        await _log(company_id, user_id, feature, model, False, error=str(e),
                   input_chars=len(prompt))
        raise


def _extract_json(text: str) -> Dict[str, Any]:
    """LLMs occasionally wrap JSON in code fences — strip them defensively."""
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.S)
    if m:
        text = m.group(1).strip()
    # Try direct parse, then trim to outermost braces if needed
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


# -------------------- Public AI feature APIs --------------------
async def generate_estimate(*, prompt: str, company: dict, user_id: str) -> dict:
    """Returns {title, intro, tiers:[3]} ready to feed into the Estimate model."""
    context = (
        f"Business: {company.get('name','A1 Field Pro')}\n"
        f"Industry: {company.get('industry','HVAC')}\n"
    )
    full_prompt = f"{context}\nHomeowner described:\n{prompt}\n\nGenerate the proposal JSON."
    text = await _call(
        system=SYSTEM_ESTIMATE_GEN, prompt=full_prompt,
        session_id=f"estimate-gen-{user_id}-{uuid.uuid4().hex[:8]}",
        feature="estimate_generator", model=MODEL_PRIMARY,
        company_id=company.get("id"), user_id=user_id, json_output=True,
    )
    data = _extract_json(text)
    # Tolerate both {"tiers": [...]} and {"good":{},"better":{},"best":{}} shapes
    raw_tiers = data.get("tiers")
    if not raw_tiers and any(k in data for k in ("good", "better", "best")):
        raw_tiers = []
        for k in ("good", "better", "best"):
            if k in data and isinstance(data[k], dict):
                raw_tiers.append({**data[k], "key": k,
                                  "name": data[k].get("name") or k.title(),
                                  "featured": data[k].get("featured", k == "better")})
    tiers = raw_tiers or []
    # Defensive normalization
    for t in tiers:
        t.setdefault("addons", [])
        t.setdefault("line_items", [])
        t.setdefault("featured", t.get("key") == "better")
        for li in t["line_items"]:
            li.setdefault("taxable", True)
            li.setdefault("kind", "service")
        for a in t["addons"]:
            a.setdefault("taxable", True)
            a.setdefault("selected", False)
            a.setdefault("kind", "material")
    return {
        "title": data.get("title", "AI-generated proposal"),
        "intro": data.get("intro", ""),
        "tiers": tiers,
    }


async def summarize_call(*, notes: str, company_id: str, user_id: str) -> dict:
    """Convert raw call notes/transcript into structured summary."""
    text = await _call(
        system=SYSTEM_CALL_SUMMARY,
        prompt=(
            "Convert these notes to JSON with shape:\n"
            "{ \"summary\": str (≤60 words), \"intent\": one of [book, quote, complaint, info, other], "
            "\"sentiment\": one of [positive, neutral, negative], "
            "\"action_items\": [str, …], \"next_step\": str }\n\nNotes:\n" + notes
        ),
        session_id=f"call-{user_id}-{uuid.uuid4().hex[:8]}",
        feature="call_summary", model=MODEL_PRIMARY,
        company_id=company_id, user_id=user_id, json_output=True,
    )
    return _extract_json(text)


async def polish_tech_notes(*, notes: str, company_id: str, user_id: str) -> str:
    if not notes.strip():
        return ""
    return (await _call(
        system=SYSTEM_TECH_NOTES, prompt=notes,
        session_id=f"polish-{user_id}-{uuid.uuid4().hex[:8]}",
        feature="tech_notes_polish", model=MODEL_LIGHT,
        company_id=company_id, user_id=user_id,
    )).strip()


async def summarize_job(*, job: dict, company_id: str, user_id: str) -> str:
    items = job.get("materials_used") or []
    items_text = ", ".join(f"{m.get('qty',1)}×{m.get('name','')}" for m in items) or "n/a"
    voice_notes = "\n".join(n.get("text", "") for n in (job.get("voice_notes") or [])[:5])
    checklist_done = [c.get("title") for c in (job.get("checklist") or []) if c.get("completed")]
    prompt = (
        f"Job: {job.get('title','')}\n"
        f"Type: {job.get('job_type','')}\n"
        f"Description: {job.get('description','') or '—'}\n"
        f"Materials used: {items_text}\n"
        f"Completed checklist: {'; '.join(checklist_done) or '—'}\n"
        f"Field notes:\n{voice_notes or '—'}\n\n"
        "Write the customer-facing job summary paragraph."
    )
    return (await _call(
        system=SYSTEM_JOB_SUMMARY, prompt=prompt,
        session_id=f"jobsummary-{job.get('id','x')[:8]}",
        feature="job_summary", model=MODEL_LIGHT,
        company_id=company_id, user_id=user_id,
    )).strip()


async def upsell_for_job(*, job: dict, customer_jobs: list, company: dict, user_id: str) -> dict:
    history = "\n".join(
        f"- {j.get('scheduled_at','')[:10]} · {j.get('job_type','')} · {j.get('title','')}"
        for j in customer_jobs[:8]
    ) or "No prior jobs."
    prompt = (
        f"Trade: {company.get('industry','HVAC')}\n"
        f"Current job: {job.get('title')} ({job.get('job_type')})\n"
        f"Customer history (most recent first):\n{history}\n\n"
        "Suggest one upsell or maintenance add-on."
    )
    text = await _call(
        system=SYSTEM_UPSELL, prompt=prompt,
        session_id=f"upsell-{job.get('id','x')[:8]}",
        feature="upsell", model=MODEL_LIGHT,
        company_id=company.get("id"), user_id=user_id, json_output=True,
    )
    return _extract_json(text)


async def maintenance_check(*, customer: dict, jobs: list, trade: str) -> dict:
    history = "\n".join(
        f"- {j.get('scheduled_at','')[:10] or j.get('created_at','')[:10]} · "
        f"{j.get('job_type','')} · {j.get('title','')}"
        for j in jobs[:12]
    ) or "No prior jobs."
    prompt = (
        f"Customer: {customer.get('name')}\n"
        f"Trade: {trade}\n"
        f"Jobs history:\n{history}\n\n"
        "Is this customer due for recurring service?"
    )
    text = await _call(
        system=SYSTEM_MAINTENANCE, prompt=prompt,
        session_id=f"maint-{customer.get('id','x')[:8]}",
        feature="maintenance_check", model=MODEL_LIGHT,
        company_id=customer.get("company_id"),
        user_id=None, json_output=True,
    )
    return _extract_json(text)


async def dispatcher_ask(*, question: str, jobs: list, team: list,
                         company_id: str, user_id: str, session_id: str) -> str:
    today = "; ".join(
        f"#{i+1} {j.get('title','')} · {(j.get('scheduled_at') or '—')[:16]} · "
        f"{(j.get('address') or '')[:40]} · {j.get('status','')} · "
        f"assigned={j.get('assigned_to') or 'none'}"
        for i, j in enumerate(jobs[:30])
    )
    techs = "; ".join(f"{t.get('id')}={t.get('name')} ({t.get('role')})" for t in team[:30])
    prompt = (
        f"You have this team: {techs or 'none'}\n\n"
        f"Today/upcoming jobs (first 30):\n{today or 'none'}\n\n"
        f"Dispatcher's question:\n{question}"
    )
    return (await _call(
        system=SYSTEM_DISPATCHER, prompt=prompt,
        session_id=session_id, feature="dispatcher_assistant",
        model=MODEL_PRIMARY, company_id=company_id, user_id=user_id,
    )).strip()


async def chatbot_reply(*, message: str, company: dict, session_id: str,
                        history: Optional[List[Dict[str, str]]] = None) -> str:
    system = SYSTEM_CHATBOT_HYBRID.format(company_name=company.get("name", "A1 Field Pro"))
    context_lines: List[str] = []
    if company.get("industry"):
        context_lines.append(f"Trade: {company['industry']}")
    if company.get("service_area"):
        context_lines.append(f"Service area: {company['service_area']}")
    if company.get("hours"):
        context_lines.append(f"Hours: {company['hours']}")
    convo = ""
    for h in (history or [])[-6:]:
        who = "Customer" if h.get("role") == "user" else "Assistant"
        convo += f"{who}: {h.get('content','')}\n"
    prompt = (
        ("Business context:\n" + "\n".join(context_lines) + "\n\n" if context_lines else "")
        + (f"Previous turns:\n{convo}\n" if convo else "")
        + f"Customer: {message}\nAssistant:"
    )
    return (await _call(
        system=system, prompt=prompt,
        session_id=session_id, feature="customer_chatbot",
        model=MODEL_LIGHT, company_id=company.get("id"), user_id=None,
    )).strip()
