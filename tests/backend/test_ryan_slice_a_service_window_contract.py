"""Pure contract characterization for Ryan cross-platform alignment Slice A."""

import json
from pathlib import Path

from common.generated_service_types import SERVICE_TYPES


ROOT_DIR = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT_DIR / "shared" / "constants" / "service-types.json"
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
SERVICES = CONTRACT["services"]
WINDOWS = CONTRACT["windows"]
ACTIVE_WINDOWS = ("MORNING", "MIDDAY", "EVENING")
LEGACY_SERVICES = (
    "WALK_30MIN",
    "WALK_60MIN",
    "DROPIN_1HR",
    "DROPIN_3HR",
    "PET_SITTING",
)


def _valid_check_in_selection(visits_per_day, selected_windows):
    metadata = SERVICES["CHECK_IN"]
    return (
        visits_per_day in metadata["visitsPerDayOptions"]
        and len(selected_windows) == visits_per_day
        and len(set(selected_windows)) == len(selected_windows)
        and all(window in metadata["allowedWindowIds"] for window in selected_windows)
    )


def test_generated_backend_contract_is_exact_clean_canonical_contract():
    clean_contract = {
        key: value for key, value in CONTRACT.items() if not key.startswith("_")
    }
    assert SERVICE_TYPES == clean_contract


def test_target_service_identities_and_durations_are_exact():
    assert SERVICES["WALK_20MIN"]["label"] == "20-Min Walk"
    assert SERVICES["WALK_20MIN"]["labelLong"] == "20-Minute Walk"
    assert SERVICES["WALK_20MIN"]["durationMinutes"] == 20
    assert SERVICES["CHECK_IN"]["label"] == "Check-In"
    assert SERVICES["CHECK_IN"]["labelLong"] == "30-Minute Check-In"
    assert SERVICES["CHECK_IN"]["durationMinutes"] == 30


def test_target_services_express_new_booking_direction_without_enabling_current_intake():
    for service_id in ("WALK_20MIN", "CHECK_IN"):
        metadata = SERVICES[service_id]
        assert metadata["lifecycle"] == "active"
        assert metadata["newBookingEligibility"] == "eligible"
        assert metadata["availableInIntake"] is False


def test_legacy_service_ids_and_historical_labels_remain_readable():
    for service_id in LEGACY_SERVICES:
        assert service_id in SERVICES
        assert SERVICES[service_id]["lifecycle"] == "legacy"
    assert SERVICES["PET_SITTING"]["labelLong"] == "Pet Sitting"
    assert SERVICES["PET_SITTING"]["labelLong"] != SERVICES["CHECK_IN"]["labelLong"]


def test_unresolved_legacy_availability_decisions_are_pending_not_invented():
    for service_id in ("WALK_60MIN", "DROPIN_1HR", "DROPIN_3HR"):
        assert SERVICES[service_id]["newBookingEligibility"] == "pending"


def test_meet_greet_current_behavior_metadata_remains_compatible():
    assert SERVICES["MEET_GREET"]["availableInIntake"] is False
    assert SERVICES["MEET_GREET"]["supportedOnMobile"] is True
    assert SERVICES["MEET_GREET"]["durationMinutes"] == 45


def test_active_window_contract_is_exact_and_machine_readable():
    assert WINDOWS["MORNING"] == {
        "label": "Morning",
        "start": "06:30",
        "end": "09:30",
        "lifecycle": "active",
        "newBookingEligibility": "eligible",
    }
    assert WINDOWS["MIDDAY"] == {
        "label": "Mid-day",
        "start": "10:30",
        "end": "15:30",
        "lifecycle": "active",
        "newBookingEligibility": "eligible",
    }
    assert WINDOWS["EVENING"] == {
        "label": "Evening",
        "start": "18:00",
        "end": "21:30",
        "lifecycle": "active",
        "newBookingEligibility": "eligible",
    }


def test_legacy_window_ids_remain_readable_without_invented_time_ranges():
    for window_id in ("AFTERNOON", "ANYTIME"):
        assert WINDOWS[window_id]["lifecycle"] == "legacy"
        assert WINDOWS[window_id]["newBookingEligibility"] == "ineligible"
        assert WINDOWS[window_id]["start"] is None
        assert WINDOWS[window_id]["end"] is None


def test_check_in_metadata_encodes_visit_options_and_active_windows():
    metadata = SERVICES["CHECK_IN"]
    assert metadata["visitsPerDayOptions"] == [1, 2, 3]
    assert metadata["allowedWindowIds"] == list(ACTIVE_WINDOWS)
    assert metadata["windowSelectionMode"] == "match_visits_per_day"


def test_check_in_one_visit_requires_exactly_one_active_window():
    assert _valid_check_in_selection(1, ["MORNING"])
    assert not _valid_check_in_selection(1, [])
    assert not _valid_check_in_selection(1, ["MORNING", "MIDDAY"])


def test_check_in_two_visits_require_two_distinct_active_windows():
    assert _valid_check_in_selection(2, ["MORNING", "EVENING"])
    assert not _valid_check_in_selection(2, ["MORNING", "MORNING"])
    assert not _valid_check_in_selection(2, ["MORNING", "AFTERNOON"])


def test_check_in_three_visits_resolve_to_all_three_active_windows():
    assert _valid_check_in_selection(3, list(ACTIVE_WINDOWS))
    assert not _valid_check_in_selection(3, ["MORNING", "MIDDAY", "AFTERNOON"])


def test_walk_window_policy_uses_exactly_one_active_canonical_window():
    metadata = SERVICES["WALK_20MIN"]
    assert metadata["allowedWindowIds"] == list(ACTIVE_WINDOWS)
    assert metadata["windowSelectionMode"] == "exactly_one"


def test_overnight_uses_fixed_cross_midnight_schedule_without_selectable_windows():
    metadata = SERVICES["OVERNIGHT"]
    assert metadata["durationMinutes"] == 600
    assert metadata["durationStatus"] == "confirmed"
    assert metadata["legacyDurationMinutes"] == 720
    assert metadata["scheduleMode"] == "fixed"
    assert metadata["fixedStartTime"] == "21:00"
    assert metadata["fixedEndTime"] == "07:00"
    assert metadata["crossesMidnight"] is True
    assert metadata["allowedWindowIds"] == []
    assert metadata["windowSelectionMode"] == "none"
