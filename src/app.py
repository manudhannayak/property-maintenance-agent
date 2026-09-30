"""
Webhook server for the Property Maintenance AI Agent.

Receives an incoming SMS from Twilio (tenant reports an issue), runs it
through the classifier, persists it, notifies the assigned vendor, and
replies to the tenant with a confirmation + ETA -- all as valid TwiML.

This endpoint is what an n8n "Webhook" node would call in the workflow
defined in workflows/property_maintenance.json, or what Twilio can call
directly if you point a phone number's messaging webhook at it.

Run with:
    uvicorn src.app:app --reload --port 8000
"""
from fastapi import FastAPI, Form
from fastapi.responses import PlainTextResponse

from classifier import classify
from notifier import notify_tenant, notify_vendor
from storage import save_request

app = FastAPI(title="Property Maintenance AI Agent")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhooks/sms", response_class=PlainTextResponse)
def incoming_sms(Body: str = Form(...), From: str = Form(...)):
    """Twilio posts incoming SMS here as `Body` and `From` form fields."""
    request = classify(Body)
    request_dict = request.to_dict()

    request_id = save_request(request_dict, from_phone=From)
    vendor_result = notify_vendor(request_dict)
    tenant_result = notify_tenant(From, request_dict)

    reply_body = tenant_result["body"]
    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{reply_body}</Message></Response>'

    # request_id / vendor_result are logged for observability; Twilio only needs the TwiML reply.
    print(f"[maintenance-agent] request #{request_id} routed to vendor: {vendor_result}")
    return twiml


@app.get("/requests")
def get_requests(status: str | None = None):
    from storage import list_requests

    return {"requests": list_requests(status=status)}
