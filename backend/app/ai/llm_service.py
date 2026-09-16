"""
Provider-independent LLM service used for:
  1. Generating human-readable fraud explanations from structured evidence.
  2. Powering the AI investigation assistant.

CRITICAL RULE: the LLM is only ever given structured facts computed by the
risk engine / database queries. It must never be allowed to invent
transaction facts - it explains and summarizes, it does not decide.

Supports: "claude" | "openai" | "gemini" | "local" | "none" (LLM_PROVIDER env var).
When set to "none" (default for a fresh install with no API key configured),
a deterministic template-based explanation is used instead, so the product
works end-to-end even before an LLM key is added.
"""
from __future__ import annotations

from app.core.config import settings


def _template_explanation(risk_score: float, risk_factors: list[str]) -> str:
    lines = [f"Risk Score: {risk_score:.0f}/100"]
    if risk_factors:
        lines.append("High Risk because:" if risk_score >= 71 else "Flagged for review because:")
        lines.extend(f"- {factor}" for factor in risk_factors)
    else:
        lines.append("No specific risk factors were triggered.")
    return "\n".join(lines)


def _build_explanation_prompt(risk_score: float, risk_level: str, risk_factors: list[str]) -> str:
    factors_block = "\n".join(f"- {f}" for f in risk_factors) or "- None"
    return (
        "You are a fraud-analysis assistant. Using ONLY the structured evidence below, "
        "write a short, clear explanation (max 5 bullet points) of why this transaction "
        "received its risk score. Do not invent any facts not listed below.\n\n"
        f"Risk Score: {risk_score:.0f}/100\n"
        f"Risk Level: {risk_level}\n"
        f"Evidence:\n{factors_block}\n"
    )


def generate_explanation(risk_score: float, risk_level: str, risk_factors: list[str]) -> str:
    """Generate a human-readable explanation for a transaction's risk score."""
    if settings.LLM_PROVIDER == "none" or not risk_factors:
        return _template_explanation(risk_score, risk_factors)

    prompt = _build_explanation_prompt(risk_score, risk_level, risk_factors)

    try:
        if settings.LLM_PROVIDER == "claude":
            return _call_claude(prompt)
        if settings.LLM_PROVIDER == "openai":
            return _call_openai(prompt)
        if settings.LLM_PROVIDER == "groq":
            return _call_groq(prompt)
        # "local" or unrecognized provider -> fall back to template
        return _template_explanation(risk_score, risk_factors)
    except Exception as e:
        # Never let an LLM outage break transaction processing - but log the
        # real reason so a silent failure doesn't look identical to "no LLM
        # configured" in the UI.
        print(f"[llm_service] generate_explanation LLM call failed: {e!r}")
        return _template_explanation(risk_score, risk_factors)


def _template_investigation_answer(evidence: dict) -> str:
    """
    Deterministic, readable fallback used when no LLM provider is configured
    (or the provider call fails) - still built ONLY from the evidence dict,
    just formatted directly instead of through an LLM. This keeps the
    assistant useful out of the box, and keeps an outage from turning the
    answer into an unreadable dump of a raw Python dict.
    """
    lines: list[str] = []

    if "investigation_case_summary" in evidence:
        case = evidence["investigation_case_summary"]
        cust, txn = case["customer"], case["transaction"]
        lines.append(f"Customer {cust['customer_id']}: risk {cust['risk_score']:.0f}/100 ({cust['risk_level']}).")
        lines.append(f"Flagged transaction {txn['transaction_id']}: {txn['amount']} {txn['currency']}, risk {txn['risk_score']:.0f} ({txn['risk_level']}).")
        if case.get("risk_factors"):
            lines.append("Risk factors: " + "; ".join(case["risk_factors"]) + ".")
        lines.append(
            f"{len(case['related_transactions'])} related transaction(s) from other customers, "
            f"{len(case['related_alerts'])} related alert(s), {len(case['investigation_notes'])} investigation note(s) on file."
        )
    else:
        if "alert" in evidence:
            a = evidence["alert"]
            lines.append(f"Alert: {a['title']} ({a['severity']}, status {a['status']}).")
        if "flagged_transaction" in evidence:
            t = evidence["flagged_transaction"]
            lines.append(f"Flagged transaction {t['transaction_id']}: {t['amount']} {t['currency']}, risk {t['risk_score']:.0f} ({t['risk_level']}).")
            if t.get("risk_factors"):
                lines.append("Risk factors: " + "; ".join(t["risk_factors"]) + ".")

    if "customer" in evidence:
        c = evidence["customer"]
        lines.append(
            f"Customer {c['customer_id']}: risk {c['risk_score']}/100 ({c['risk_level']}), "
            f"{c['suspicious_transactions']}/{c['total_transactions']} suspicious, "
            f"{c['devices_used']} device(s), {c['locations_used']} location(s), "
            f"{c['previous_fraud_reports']} previous fraud report(s)."
        )

    if "unusual_activity" in evidence:
        ua = evidence["unusual_activity"]
        lines.append(f"Unusual activity ({ua['note']}):")
        for t in ua["unusual_transactions"][:5]:
            factors = ", ".join(t["risk_factors"]) or "no listed risk factors"
            lines.append(f"  - {t['transaction_id']}: {t['amount']} on {t['transaction_datetime']}, anomaly score {t['anomaly_score']:.0f} - {factors}")

    if "device" in evidence:
        d = evidence["device"]
        ring_note = " - shared across multiple customers, a possible fraud-ring signal." if d["shared_by_multiple_customers"] else "."
        lines.append(f"Device {d['device_id']}: {d['transaction_count']} transaction(s) across {d['distinct_customer_count']} customer(s){ring_note}")

    if not lines:
        return "No matching evidence was found for this question. Try including a customer ID, alert, or device ID."

    return "\n".join(lines)


def answer_investigation_question(question: str, evidence: dict, conversation_history: list[dict] | None = None) -> str:
    """
    Answer an analyst's free-text question using ONLY the evidence dict
    that was retrieved from the database by the investigation/assistant
    service. `conversation_history` (a list of {"role", "content"} dicts, in
    chronological order) lets the analyst ask natural follow-ups like "what
    about last week?" without repeating context - only the most recent
    turns are included to keep the prompt small.
    """
    if settings.LLM_PROVIDER == "none":
        return _template_investigation_answer(evidence)

    history_block = ""
    if conversation_history:
        recent_turns = conversation_history[-6:]
        rendered = "\n".join(f"{turn['role'].capitalize()}: {turn['content']}" for turn in recent_turns)
        history_block = f"Recent conversation so far:\n{rendered}\n\n"

    prompt = (
        "You are a fraud investigation assistant for an analyst. Answer the analyst's "
        "question using ONLY the evidence JSON below. Never invent transactions, "
        "customers, devices or amounts that are not present in the evidence. If the "
        "evidence doesn't contain enough to answer, say so plainly instead of guessing. "
        "Be concise and use short bullet points where that helps.\n\n"
        f"{history_block}"
        f"Evidence:\n{evidence}\n\n"
        f"Analyst question: {question}\n"
    )
    try:
        if settings.LLM_PROVIDER == "claude":
            return _call_claude(prompt)
        if settings.LLM_PROVIDER == "openai":
            return _call_openai(prompt)
        if settings.LLM_PROVIDER == "gemini":
            return _call_gemini(prompt)
        if settings.LLM_PROVIDER == "groq":
            return _call_groq(prompt)
        return _template_investigation_answer(evidence)
    except Exception as e:  # never let an LLM outage block an analyst
        print(f"[llm_service] answer_investigation_question LLM call failed: {e!r}")
        return _template_investigation_answer(evidence) + "\n\n(The AI provider was unavailable, so this summary was generated directly from the data.)"


def _call_openai(prompt: str) -> str:
    import httpx

    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY or ''}",
        "Content-Type": "application/json",
    }
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_gemini(prompt: str) -> str:
    import httpx

    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured")

    resp = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 500},
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _call_claude(prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if getattr(block, "type", None) == "text")


def _call_groq(prompt: str) -> str:
    import httpx

    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]