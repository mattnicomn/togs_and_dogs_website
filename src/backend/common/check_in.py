"""Contract-driven Check-In booking validation and occurrence helpers."""

from common.service_contract import SERVICE_METADATA, WINDOW_METADATA


CHECK_IN_SERVICE_TYPE = "CHECK_IN"


class CheckInValidationError(ValueError):
    """Raised when a new Check-In transactional write violates the contract."""


def _check_in_metadata():
    return SERVICE_METADATA[CHECK_IN_SERVICE_TYPE]


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


def check_in_window_start(window_id):
    """Return the canonical ``HH:mm`` start for an allowed Check-In window."""
    metadata = _check_in_metadata()
    if window_id not in metadata["allowedWindowIds"]:
        return None
    window = WINDOW_METADATA.get(window_id) or {}
    if (
        window.get("lifecycle") != "active"
        or window.get("newBookingEligibility") != "eligible"
    ):
        return None
    return window.get("start")
