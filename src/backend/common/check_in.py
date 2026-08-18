"""Contract-driven canonical booking-window validation and helpers."""

from common.service_contract import SERVICE_METADATA, WINDOW_METADATA


CHECK_IN_SERVICE_TYPE = "CHECK_IN"
WALK_SERVICE_TYPE = "WALK_20MIN"
OVERNIGHT_SERVICE_TYPE = "OVERNIGHT"


class BookingWindowValidationError(ValueError):
    """Raised when a new canonical booking-window write violates the contract."""


class CheckInValidationError(BookingWindowValidationError):
    """Raised when a new Check-In transactional write violates the contract."""


def _check_in_metadata():
    return SERVICE_METADATA[CHECK_IN_SERVICE_TYPE]


def _walk_metadata():
    return SERVICE_METADATA[WALK_SERVICE_TYPE]


def _overnight_metadata():
    return SERVICE_METADATA[OVERNIGHT_SERVICE_TYPE]


def validate_check_in_booking_fields(record):
    """Return canonical Check-In fields, or ``None`` for another service.

    Historical records are not rewritten or globally validated. Callers use this
    helper only at new request/job transaction boundaries.
    """
    if record.get("service_type") != CHECK_IN_SERVICE_TYPE:
        return None

    metadata = _check_in_metadata()
    visits_per_day = record.get("visits_per_day")
    visit_windows = record.get("visit_windows")
    allowed_visits = metadata["visitsPerDayOptions"]
    allowed_windows = metadata["allowedWindowIds"]

    if isinstance(visits_per_day, bool) or not isinstance(visits_per_day, int):
        raise CheckInValidationError(
            "CHECK_IN requires visits_per_day from the canonical contract."
        )
    if visits_per_day not in allowed_visits:
        raise CheckInValidationError(
            "CHECK_IN visits_per_day is not allowed by the canonical contract."
        )
    if not isinstance(visit_windows, list) or not visit_windows:
        raise CheckInValidationError(
            "CHECK_IN requires visit_windows matching visits_per_day."
        )
    if any(not isinstance(window, str) for window in visit_windows):
        raise CheckInValidationError(
            "CHECK_IN visit_windows must contain canonical window identifiers."
        )
    if len(set(visit_windows)) != len(visit_windows):
        raise CheckInValidationError("CHECK_IN visit_windows must be distinct.")

    invalid_windows = [window for window in visit_windows if window not in allowed_windows]
    if invalid_windows:
        raise CheckInValidationError(
            "CHECK_IN visit_windows contains a window not allowed by the canonical contract."
        )
    if metadata.get("windowSelectionMode") != "match_visits_per_day":
        raise CheckInValidationError("CHECK_IN window selection contract is unsupported.")
    if len(visit_windows) != visits_per_day:
        raise CheckInValidationError(
            "CHECK_IN visit_windows count must equal visits_per_day."
        )

    selected = set(visit_windows)
    canonical_windows = [window for window in allowed_windows if window in selected]
    return {
        "visits_per_day": visits_per_day,
        "visit_windows": canonical_windows,
        "visit_window": canonical_windows[0],
    }


def validate_walk_booking_fields(record):
    """Return canonical 20-Minute Walk fields, or ``None`` for another service."""
    if record.get("service_type") != WALK_SERVICE_TYPE:
        return None

    metadata = _walk_metadata()
    visit_windows = record.get("visit_windows")
    allowed_windows = metadata["allowedWindowIds"]

    if metadata.get("windowSelectionMode") != "exactly_one":
        raise BookingWindowValidationError(
            "WALK_20MIN window selection contract is unsupported."
        )
    if not isinstance(visit_windows, list) or not visit_windows:
        raise BookingWindowValidationError(
            "WALK_20MIN requires exactly one canonical visit_windows entry."
        )
    if any(not isinstance(window, str) for window in visit_windows):
        raise BookingWindowValidationError(
            "WALK_20MIN visit_windows must contain canonical window identifiers."
        )
    if len(set(visit_windows)) != len(visit_windows):
        raise BookingWindowValidationError("WALK_20MIN visit_windows must be distinct.")
    if len(visit_windows) != 1:
        raise BookingWindowValidationError(
            "WALK_20MIN requires exactly one canonical visit_windows entry."
        )
    if visit_windows[0] not in allowed_windows:
        raise BookingWindowValidationError(
            "WALK_20MIN visit_windows contains a window not allowed by the canonical contract."
        )
    if record.get("visits_per_day") is not None:
        raise BookingWindowValidationError("WALK_20MIN does not accept visits_per_day.")

    window_id = visit_windows[0]
    return {
        "visits_per_day": None,
        "visit_windows": [window_id],
        "visit_window": window_id,
    }


def validate_overnight_booking_fields(record, *, persisted=False):
    """Return backend-derived fixed Overnight fields for a new write."""
    if record.get("service_type") != OVERNIGHT_SERVICE_TYPE:
        return None
    if persisted and record.get("canonical_schedule_mode") != "fixed":
        return None

    metadata = _overnight_metadata()
    if (
        metadata.get("scheduleMode") != "fixed"
        or metadata.get("windowSelectionMode") != "none"
        or metadata.get("allowedWindowIds") != []
        or metadata.get("durationStatus") != "confirmed"
    ):
        raise BookingWindowValidationError(
            "OVERNIGHT fixed scheduling contract is unsupported."
        )

    prohibited_fields = (
        "visits_per_day",
        "visit_windows",
        "visit_window",
        "preferred_time",
        "scheduled_time",
        "start_time",
        "end_time",
        "fixed_start_time",
        "fixed_end_time",
    )
    supplied_fields = [field for field in prohibited_fields if field in record]
    if supplied_fields:
        raise BookingWindowValidationError(
            "OVERNIGHT uses a fixed canonical schedule and does not accept "
            + ", ".join(supplied_fields)
            + "."
        )

    return {
        "canonical_schedule_mode": "fixed",
        "canonical_fixed_start_time": metadata["fixedStartTime"],
        "canonical_fixed_end_time": metadata["fixedEndTime"],
        "canonical_crosses_midnight": metadata["crossesMidnight"],
        "scheduled_duration": metadata["durationMinutes"],
    }


def validate_booking_window_fields(record, *, persisted=False):
    """Validate a new write for any service with canonical window semantics."""
    check_in_fields = validate_check_in_booking_fields(record)
    if check_in_fields:
        return check_in_fields
    walk_fields = validate_walk_booking_fields(record)
    if walk_fields:
        return walk_fields
    return validate_overnight_booking_fields(record, persisted=persisted)


def canonical_window_start(service_type, window_id):
    """Return an allowed canonical ``HH:mm`` start for a service window."""
    metadata = SERVICE_METADATA.get(service_type) or {}
    if metadata.get("windowSelectionMode") not in {
        "match_visits_per_day",
        "exactly_one",
    }:
        return None
    if window_id not in metadata.get("allowedWindowIds", []):
        return None
    window = WINDOW_METADATA.get(window_id) or {}
    if (
        window.get("lifecycle") != "active"
        or window.get("newBookingEligibility") != "eligible"
    ):
        return None
    return window.get("start")


def check_in_window_start(window_id):
    """Return the canonical ``HH:mm`` start for an allowed Check-In window."""
    return canonical_window_start(CHECK_IN_SERVICE_TYPE, window_id)
