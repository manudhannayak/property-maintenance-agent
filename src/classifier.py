"""
AI classification layer for incoming maintenance requests.

Uses Google's Gemini API to turn a free-text tenant message (e.g. an SMS)
into structured fields: category, urgency, a short summary, and any unit/
contact details mentioned. Falls back to a deterministic rule-based
classifier when GEMINI_API_KEY isn't set, so the agent is runnable and
testable without external credentials.
"""
import json
import os
import re
from dataclasses import asdict, dataclass

CATEGORIES = ["plumbing", "electrical", "hvac", "appliance", "pest", "structural", "other"]
URGENCY_LEVELS = ["emergency", "high", "medium", "low"]

_EMERGENCY_KEYWORDS = ["flood", "flooding", "gas smell", "gas leak", "fire", "no heat", "sparking", "smoke"]
_HIGH_KEYWORDS = ["leak", "leaking", "no hot water", "no water", "broken lock", "not cooling", "not heating"]
_CATEGORY_KEYWORDS = {
    "plumbing": ["leak", "pipe", "faucet", "toilet", "drain", "water heater", "sink", "flood", "hot water", "no water"],
    "electrical": ["outlet", "wiring", "sparking", "breaker", "light switch", "power"],
    "hvac": ["heat", "heater", "furnace", "ac", "air condition", "thermostat", "cooling"],
    "appliance": ["fridge", "refrigerator", "dishwasher", "washer", "dryer", "stove", "oven"],
    "pest": ["roach", "roaches", "mice", "mouse", "rat", "rats", "ant", "ants", "bed bug", "pest"],
    "structural": ["ceiling", "wall crack", "window broken", "door won't", "roof"],
}


def _contains_keyword(text: str, keyword: str) -> bool:
    """Whole-word/phrase match so short keywords (e.g. 'ac', 'rat') don't
    false-positive inside unrelated words ('roACHes', 'geneRATor')."""
    pattern = r"\b" + re.escape(keyword) + r"\b"
    return re.search(pattern, text) is not None


@dataclass
class MaintenanceRequest:
    raw_message: str
    category: str
    urgency: str
    summary: str
    unit_number: str | None = None
    backend: str = "rule_based"

    def to_dict(self) -> dict:
        return asdict(self)


def _extract_unit_number(text: str) -> str | None:
    match = re.search(r"\bunit\s*#?\s*([a-zA-Z0-9-]+)", text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"\bapt\.?\s*#?\s*([a-zA-Z0-9-]+)", text, re.IGNORECASE)
    return match.group(1) if match else None


def classify_rule_based(message: str) -> MaintenanceRequest:
    text = message.lower()

    urgency = "low"
    if any(_contains_keyword(text, kw) for kw in _EMERGENCY_KEYWORDS):
        urgency = "emergency"
    elif any(_contains_keyword(text, kw) for kw in _HIGH_KEYWORDS):
        urgency = "high"
    elif any(_contains_keyword(text, kw) for kw in ["broken", "not working", "won't"]):
        urgency = "medium"

    category = "other"
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        if any(_contains_keyword(text, kw) for kw in keywords):
            category = cat
            break

    summary = message.strip()
    if len(summary) > 140:
        summary = summary[:137] + "..."

    return MaintenanceRequest(
        raw_message=message,
        category=category,
        urgency=urgency,
        summary=summary,
        unit_number=_extract_unit_number(message),
        backend="rule_based",
    )


def classify_with_gemini(message: str) -> MaintenanceRequest:
    """Structured classification via the Gemini API. Requires GEMINI_API_KEY."""
    import google.generativeai as genai

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = (
        "You are a property-management triage assistant. A tenant sent the "
        "maintenance request below by text message. Classify it and return "
        "ONLY compact JSON with keys: category (one of "
        f"{CATEGORIES}), urgency (one of {URGENCY_LEVELS}), summary (<=20 words), "
        "unit_number (string or null if not mentioned).\n\n"
        f"Tenant message: \"{message}\""
    )
    response = model.generate_content(prompt)
    data = json.loads(response.text)
    return MaintenanceRequest(
        raw_message=message,
        category=data.get("category", "other"),
        urgency=data.get("urgency", "medium"),
        summary=data.get("summary", message[:140]),
        unit_number=data.get("unit_number"),
        backend="gemini",
    )


def classify(message: str) -> MaintenanceRequest:
    """
    Classifies a tenant maintenance request, preferring Gemini if configured,
    falling back to the rule-based classifier on missing key or API failure.
    """
    if os.getenv("GEMINI_API_KEY"):
        try:
            return classify_with_gemini(message)
        except Exception:
            result = classify_rule_based(message)
            result.backend = "rule_based (gemini call failed)"
            return result
    return classify_rule_based(message)
