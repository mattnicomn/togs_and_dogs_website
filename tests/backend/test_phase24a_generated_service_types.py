"""Phase 24A-2C.2D.2 generated backend service metadata validation."""

import ast
import json
from pathlib import Path

import common.generated_service_types as generated_service_types_module
from common.generated_service_types import SERVICE_TYPES


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "src" / "backend"
GENERATED_MODULE_PATH = BACKEND_DIR / "common" / "generated_service_types.py"
SERVICE_CONTRACT_PATH = ROOT_DIR / "shared" / "constants" / "service-types.json"
EXPECTED_FIELDS = (
    "label",
    "labelLong",
    "durationMinutes",
    "durationStatus",
    "availableInIntake",
    "supportedOnMobile",
    "lifecycle",
    "newBookingEligibility",
    "visitsPerDayOptions",
    "allowedWindowIds",
    "windowSelectionMode",
)
EXPECTED_WINDOW_FIELDS = (
    "label",
    "start",
    "end",
    "lifecycle",
    "newBookingEligibility",
)
TARGET_MODULES = {
    "common.generated_service_types",
    "src.backend.common.generated_service_types",
    "generated_service_types",
}


def load_clean_canonical_service_types():
    canonical = json.loads(SERVICE_CONTRACT_PATH.read_text(encoding="utf-8"))
    return {key: value for key, value in canonical.items() if not key.startswith("_")}


def test_generated_service_types_exactly_equal_canonical_contract():
    canonical = load_clean_canonical_service_types()

    assert SERVICE_TYPES == canonical
    assert tuple(SERVICE_TYPES) == tuple(canonical)
    assert tuple(SERVICE_TYPES["services"]) == tuple(canonical["services"])

    for metadata in SERVICE_TYPES["services"].values():
        assert tuple(metadata) == EXPECTED_FIELDS
        assert type(metadata["label"]) is str
        assert type(metadata["labelLong"]) is str
        assert type(metadata["durationMinutes"]) is int
        assert metadata["durationMinutes"] > 0
        assert type(metadata["durationStatus"]) is str
        assert type(metadata["availableInIntake"]) is bool
        assert type(metadata["supportedOnMobile"]) is bool
        assert type(metadata["lifecycle"]) is str
        assert type(metadata["newBookingEligibility"]) is str
        assert type(metadata["visitsPerDayOptions"]) is list
        assert type(metadata["allowedWindowIds"]) is list
        assert type(metadata["windowSelectionMode"]) is str

    assert tuple(SERVICE_TYPES["windows"]) == tuple(canonical["windows"])
    for metadata in SERVICE_TYPES["windows"].values():
        assert tuple(metadata) == EXPECTED_WINDOW_FIELDS
        assert type(metadata["label"]) is str
        assert metadata["start"] is None or type(metadata["start"]) is str
        assert metadata["end"] is None or type(metadata["end"]) is str
        assert type(metadata["lifecycle"]) is str
        assert type(metadata["newBookingEligibility"]) is str


def test_generated_service_types_module_resolves_under_backend_common():
    module_path = Path(generated_service_types_module.__file__).resolve()
    expected_path = GENERATED_MODULE_PATH.resolve()

    assert module_path == expected_path
    assert module_path.parent == (BACKEND_DIR / "common").resolve()


def _targeted_imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in TARGET_MODULES:
                    findings.append((node.lineno, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if module_name in TARGET_MODULES:
                findings.append((node.lineno, f"from {module_name} import ..."))
            elif any(alias.name == "generated_service_types" for alias in node.names):
                if module_name in {"", "common", "src.backend.common"}:
                    findings.append(
                        (node.lineno, f"from {'.' * node.level}{module_name} import generated_service_types")
                    )
        elif isinstance(node, ast.Call) and node.args:
            module_name = None
            if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                module_name = node.args[0]
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "importlib"
            ):
                module_name = node.args[0]
            if isinstance(module_name, ast.Constant) and module_name.value in TARGET_MODULES:
                findings.append((node.lineno, f"dynamic import {module_name.value}"))

    return findings


def test_exactly_one_approved_backend_runtime_consumer_of_generated_service_types():
    approved_path = (BACKEND_DIR / "common" / "service_contract.py").resolve()
    consumers = []

    for path in sorted(BACKEND_DIR.rglob("*.py")):
        if path.resolve() == GENERATED_MODULE_PATH.resolve():
            continue
        findings = _targeted_imports(path)
        if findings:
            for line_number, statement in findings:
                consumers.append((path.resolve(), line_number, statement))

    assert len(consumers) == 1, (
        f"Expected exactly one approved runtime consumer of generated service types, found {len(consumers)}:\n"
        + "\n".join(f"{p}:{l}: {s}" for p, l, s in consumers)
    )

    consumer_path, line_number, statement = consumers[0]
    assert consumer_path == approved_path, (
        f"Approved consumer must be {approved_path}, but found consumer in {consumer_path}:{line_number}"
    )
    assert statement == "from common.generated_service_types import ..."


def test_google_calendar_wiring_matches_generated_service_types():
    import common.google_calendar as google_calendar

    assert google_calendar.SERVICE_METADATA is SERVICE_TYPES["services"]
    assert google_calendar.SERVICE_DURATIONS == {
        service_type: metadata["durationMinutes"]
        for service_type, metadata in SERVICE_TYPES["services"].items()
    }
    assert google_calendar.FRIENDLY_SERVICE_NAMES == {
        service_type: metadata["label"]
        for service_type, metadata in SERVICE_TYPES["services"].items()
    }
    assert google_calendar.SERVICE_COLORS == {
        "WALK_30MIN": "9",
        "WALK_60MIN": "9",
        "DROPIN_1HR": "7",
        "DROPIN_3HR": "7",
        "OVERNIGHT": "6",
        "PET_SITTING": "10",
        "MEET_GREET": "3",
    }


def test_unknown_service_uses_fallback_color_eight_in_google_calendar():
    from common.google_calendar import _build_event_body

    item = {
        "request_id": "test-unknown-color",
        "client_name": "Test Client",
        "pet_names": "Buddy",
        "start_date": "2030-01-15",
        "scheduled_time": "09:00",
        "service_type": "UNKNOWN_SERVICE",
    }
    body, skip_reason = _build_event_body(item)
    assert skip_reason is None
    assert body["colorId"] == "8"


def test_build_event_body_does_not_mutate_imported_service_types():
    import copy
    import common.google_calendar as google_calendar
    from common.google_calendar import _build_event_body

    before = copy.deepcopy(SERVICE_TYPES)

    item = {
        "request_id": "test-mutation-safety",
        "client_name": "Test Client",
        "pet_names": "Max",
        "start_date": "2030-01-15",
        "scheduled_time": "10:00",
        "service_type": "WALK_30MIN",
    }
    body, skip_reason = _build_event_body(item)
    assert skip_reason is None

    assert SERVICE_TYPES == before
    assert google_calendar.SERVICE_METADATA == before["services"]
