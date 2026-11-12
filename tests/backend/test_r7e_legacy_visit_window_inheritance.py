"""
R7E regression: legacy (non-canonical) multi-day child JOBs keep the parent's own
visit_window; canonical occurrence windows are never overwritten; missing or invalid
legacy windows are never invented.
"""
import sys
import os
import uuid
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from handlers.job_handler import handler as job_handler

COMPANY = "test_company"
CLIENT = "client-123"

_MISSING = object()


def _request(req_id, service_type="WALK_30MIN", visit_window=_MISSING, **extra):
    item = {
        "PK": f"REQ#{req_id}",
        "SK": f"CLIENT#{CLIENT}",
        "request_id": req_id,
        "client_id": CLIENT,
        "company_id": COMPANY,
        "service_type": service_type,
        "start_date": "2026-07-20",
        "end_date": "2026-07-22",
    }
    if visit_window is not _MISSING:
        item["visit_window"] = visit_window
    item.update(extra)
    return item


def _run(request_item):
    """Run the job handler for one parent REQUEST; return the persisted child JOB items."""
    def get_item(pk, sk):
        if pk == request_item["PK"] and sk == request_item["SK"]:
            return request_item
        return None  # no pre-existing child JOBs

    with patch('handlers.job_handler.get_item', side_effect=get_item), \
         patch('handlers.job_handler.put_item', return_value=True) as put, \
         patch('handlers.job_handler.table'), \
         patch('handlers.job_handler.time.sleep'), \
         patch('common.pet_profile.create_or_link_pets_from_request', return_value={"pet_ids": ["pet-123"]}), \
         patch('common.google_calendar.sync_calendar_event', return_value=None):
        res = job_handler({"expected_company_id": COMPANY, "request_id": request_item["request_id"],
                           "client_id": CLIENT}, None)
    assert "error" not in res, res
    return [c.args[0] for c in put.call_args_list]


# --- Legacy (non-canonical) multi-day children --------------------------------------

@pytest.mark.parametrize("window", ["MORNING", "MIDDAY", "EVENING", "AFTERNOON", "ANYTIME"])
def test_legacy_multi_day_children_inherit_valid_contract_window(window):
    jobs = _run(_request("req-legacy-valid", visit_window=window))
    assert len(jobs) == 3
    for job in jobs:
        assert job["visit_window"] == window
        # Only the parent's own label is carried: no canonical occurrence fields,
        # no plural window list and no clock time are invented.
        for key in ("visit_windows", "occurrence_window", "booking_visit_windows",
                    "start_time", "calendar_event_id"):
            assert key not in job
    assert [j["occurrence_date"] for j in jobs] == ["2026-07-20", "2026-07-21", "2026-07-22"]


def test_legacy_multi_day_children_missing_window_not_invented():
    jobs = _run(_request("req-legacy-missing"))
    assert len(jobs) == 3
    assert all("visit_window" not in job for job in jobs)


@pytest.mark.parametrize("bad", [None, "", "  ", "morning", " MORNING", "NOT_A_WINDOW",
                                 123, ["MORNING"], {"id": "MORNING"}])
def test_legacy_multi_day_children_invalid_window_not_inherited(bad):
    jobs = _run(_request("req-legacy-invalid", visit_window=bad))
    assert len(jobs) == 3
    assert all("visit_window" not in job for job in jobs)


def test_legacy_single_day_job_unchanged():
    """Scope guard: the correction applies only to multi-day children."""
    jobs = _run(_request("req-legacy-single", visit_window="MORNING", end_date="2026-07-20"))
    assert len(jobs) == 1
    assert "visit_window" not in jobs[0]
    assert "occurrence_date" not in jobs[0]


# --- Canonical services are never overwritten by the parent's visit_window -----------

def test_canonical_walk_multi_day_keeps_occurrence_window():
    req = _request("req-walk", service_type="WALK_20MIN", visit_window="MORNING",
                   visit_windows=["EVENING"])
    jobs = _run(req)
    assert len(jobs) == 3
    for job in jobs:
        assert job["visit_window"] == "EVENING"
        assert job["occurrence_window"] == "EVENING"
        assert job["visit_windows"] == ["EVENING"]
    # Deterministic occurrence identity is unchanged.
    expected_ids = [
        str(uuid.uuid5(uuid.NAMESPACE_URL, f"togs-and-dogs:walk-20min:req-walk:{d}:EVENING"))
        for d in ("2026-07-20", "2026-07-21", "2026-07-22")
    ]
    assert [j["PK"] for j in jobs] == [f"JOB#{i}" for i in expected_ids]


def test_canonical_check_in_multi_day_keeps_each_occurrence_window():
    req = _request("req-checkin", service_type="CHECK_IN", visit_window="EVENING",
                   visits_per_day=2, visit_windows=["MORNING", "MIDDAY"])
    jobs = _run(req)
    assert len(jobs) == 6
    windows = [(j["occurrence_date"], j["visit_window"], j["occurrence_window"]) for j in jobs]
    assert windows == [
        (d, w, w) for d in ("2026-07-20", "2026-07-21", "2026-07-22") for w in ("MORNING", "MIDDAY")
    ]
    assert all(j["visit_window"] != "EVENING" for j in jobs)


def test_canonical_fixed_overnight_multi_day_gets_no_visit_window():
    req = _request("req-overnight", service_type="OVERNIGHT", canonical_schedule_mode="fixed")
    jobs = _run(req)
    assert len(jobs) == 3
    assert all("visit_window" not in job for job in jobs)
    assert all(job["canonical_schedule_mode"] == "fixed" for job in jobs)
