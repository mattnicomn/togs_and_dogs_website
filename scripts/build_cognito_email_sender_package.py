"""Build the isolated Cognito custom email sender Lambda zip.

The package targets Lambda's Python 3.11 x86_64 Linux runtime even when this
script is run from Windows. Output is intentionally ignored by Git.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "src" / "cognito_email_sender"
HANDLER_FILE = SOURCE_DIR / "cognito_email_sender_handler.py"
REQUIREMENTS_FILE = SOURCE_DIR / "requirements.lock"
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "artifacts"
    / "cognito-email-sender"
    / "cognito-email-sender.zip"
)
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _zip_directory(source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            relative = path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(relative, ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes())


def build(output: Path) -> None:
    if not HANDLER_FILE.is_file() or not REQUIREMENTS_FILE.is_file():
        raise FileNotFoundError("Cognito email sender package inputs are incomplete")

    with tempfile.TemporaryDirectory(prefix="cognito-email-sender-") as temp_name:
        staging = Path(temp_name) / "package"
        staging.mkdir()
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--requirement",
                str(REQUIREMENTS_FILE),
                "--target",
                str(staging),
                "--platform",
                "manylinux2014_x86_64",
                "--implementation",
                "cp",
                "--python-version",
                "3.11",
                "--abi",
                "cp311",
                "--only-binary=:all:",
                "--no-compile",
                "--disable-pip-version-check",
            ],
            check=True,
        )
        # pip creates a host-specific cffi console launcher even for a targeted
        # Linux install. Lambda does not use console scripts, and the launcher
        # makes otherwise identical builds differ. RECORD files include that
        # launcher's varying hash, so remove both deployment-irrelevant outputs.
        shutil.rmtree(staging / "bin", ignore_errors=True)
        for record_file in staging.glob("*.dist-info/RECORD"):
            record_file.unlink()
        shutil.copy2(HANDLER_FILE, staging / HANDLER_FILE.name)
        _zip_directory(staging, output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Lambda zip output path",
    )
    args = parser.parse_args()
    build(args.output.resolve())
    print(f"Built isolated Cognito email sender package: {args.output.resolve()}")


if __name__ == "__main__":
    main()
