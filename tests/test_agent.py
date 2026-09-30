import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from classifier import classify_rule_based  # noqa: E402
from notifier import notify_tenant, notify_vendor  # noqa: E402
from storage import DEFAULT_DB_PATH, list_requests, save_request, update_status  # noqa: E402


@pytest.fixture()
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)  # let get_connection create it fresh
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_classify_detects_emergency_flooding():
    result = classify_rule_based("There's a flood in unit 4B, water everywhere!")
    assert result.urgency == "emergency"
    assert result.category == "plumbing"
    assert result.unit_number == "4B"


def test_classify_detects_electrical_high_priority():
    result = classify_rule_based("The outlet in the kitchen is sparking, please help")
    assert result.category == "electrical"
    assert result.backend == "rule_based"


def test_classify_defaults_to_low_urgency_other_category():
    result = classify_rule_based("The hallway light bulb has been out for a while, no rush")
    assert result.urgency in ("low", "medium")


def test_classify_summary_is_truncated():
    long_message = "The dishwasher is broken and " + "leaking a lot of water " * 10
    result = classify_rule_based(long_message)
    assert len(result.summary) <= 140


def test_storage_save_and_list_roundtrip(temp_db):
    req = classify_rule_based("No hot water in unit 12, please send plumber").to_dict()
    request_id = save_request(req, from_phone="+15551234567", db_path=temp_db)
    assert request_id == 1

    rows = list_requests(db_path=temp_db)
    assert len(rows) == 1
    assert rows[0]["category"] == "plumbing"
    assert rows[0]["status"] == "open"


def test_storage_update_status(temp_db):
    req = classify_rule_based("AC not cooling in unit 9").to_dict()
    request_id = save_request(req, from_phone="+15550001111", db_path=temp_db)
    update_status(request_id, "resolved", db_path=temp_db)

    rows = list_requests(status="resolved", db_path=temp_db)
    assert len(rows) == 1
    assert rows[0]["id"] == request_id


def test_notify_tenant_dry_run_without_twilio_credentials(monkeypatch):
    for var in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"):
        monkeypatch.delenv(var, raising=False)
    req = classify_rule_based("Leaking pipe under the sink in unit 3").to_dict()
    result = notify_tenant("+15559998888", req)
    assert result["mode"] == "dry_run"
    assert "plumbing" in result["body"]


def test_notify_vendor_routes_by_category(monkeypatch):
    for var in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"):
        monkeypatch.delenv(var, raising=False)
    req = classify_rule_based("Roaches in the kitchen, unit 7").to_dict()
    result = notify_vendor(req)
    assert result["mode"] == "dry_run"
    assert result["to"] != ""
