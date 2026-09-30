"""
Notification layer: confirms receipt to the tenant and alerts the right
vendor/on-call contact based on category and urgency, via Twilio SMS.

Falls back to a local "dry run" mode (logs what would be sent) when
Twilio credentials aren't configured, so the agent is fully runnable and
testable without a Twilio account.
"""
import os

# In production this would be looked up per-property from Supabase/Postgres.
# Kept simple here for demo purposes.
VENDOR_DIRECTORY = {
    "plumbing": "+15550100001",
    "electrical": "+15550100002",
    "hvac": "+15550100003",
    "appliance": "+15550100004",
    "pest": "+15550100005",
    "structural": "+15550100006",
    "other": "+15550100000",  # general property manager
}

URGENCY_ETA = {
    "emergency": "within the hour",
    "high": "within 24 hours",
    "medium": "within 2-3 business days",
    "low": "within a week",
}


def _send_sms(to: str, body: str) -> dict:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")

    if account_sid and auth_token and from_number:
        from twilio.rest import Client

        client = Client(account_sid, auth_token)
        message = client.messages.create(to=to, from_=from_number, body=body)
        return {"mode": "twilio", "sid": message.sid, "to": to, "body": body}

    # Dry-run fallback: no Twilio account configured.
    return {"mode": "dry_run", "to": to, "body": body}


def notify_tenant(to_phone: str, request: dict) -> dict:
    eta = URGENCY_ETA.get(request["urgency"], "as soon as possible")
    body = (
        f"Thanks -- we've logged your {request['category']} request "
        f"(\"{request['summary']}\"). A vendor will reach out {eta}."
    )
    return _send_sms(to_phone, body)


def notify_vendor(request: dict) -> dict:
    vendor_phone = VENDOR_DIRECTORY.get(request["category"], VENDOR_DIRECTORY["other"])
    unit = f" (Unit {request['unit_number']})" if request.get("unit_number") else ""
    body = (
        f"[{request['urgency'].upper()}] {request['category']} request{unit}: "
        f"{request['summary']}"
    )
    return _send_sms(vendor_phone, body)
