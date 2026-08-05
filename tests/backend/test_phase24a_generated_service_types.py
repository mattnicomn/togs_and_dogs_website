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
    "availableInIntake",
    "supportedOnMobile",
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
        assert type(metadata["availableInIntake"]) is bool
        assert type(metadata["supportedOnMobile"]) is bool


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


def test_no_backend_runtime_source_consumes_generated_service_types():
    violations = []

    for path in sorted(BACKEND_DIR.rglob("*.py")):
        if path.resolve() == GENERATED_MODULE_PATH.resolve():
            continue
        for line_number, statement in _targeted_imports(path):
            violations.append(f"{path.relative_to(ROOT_DIR)}:{line_number}: {statement}")

    assert violations == [], "Generated service metadata has runtime consumers:\n" + "\n".join(violations)
