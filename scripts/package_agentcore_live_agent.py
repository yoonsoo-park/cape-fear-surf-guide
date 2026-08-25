#!/usr/bin/env python3
"""Build a deterministic Linux ARM64 direct-code ZIP for AgentCore Runtime."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXED_TIMESTAMP = (2026, 8, 24, 0, 0, 0)


def _source_files() -> dict[Path, str]:
    files = {
        REPO_ROOT / "agentcore_live_entrypoint.py": "agentcore_live_entrypoint.py",
    }
    for directory in ("agentcore_runtime", "surf"):
        for path in sorted((REPO_ROOT / directory).rglob("*.py")):
            if "__pycache__" not in path.parts:
                files[path] = path.relative_to(REPO_ROOT).as_posix()
    for path in sorted((REPO_ROOT / "surf" / "data").rglob("*")):
        if path.is_file():
            files[path] = path.relative_to(REPO_ROOT).as_posix()
    return files


def _write_member(archive: ZipFile, digest: "hashlib._Hash", name: str, contents: bytes) -> None:
    info = ZipInfo(name, date_time=FIXED_TIMESTAMP)
    info.compress_type = ZIP_DEFLATED
    # AgentCore mounts artifacts under a separate runtime user.  Preserve the
    # documented world-readable mode instead of ZipInfo's host-dependent 0600.
    info.external_attr = 0o100644 << 16
    archive.writestr(info, contents)
    digest.update(name.encode())
    digest.update(b"\0")
    digest.update(contents)


def _vendor_dependencies(destination: Path) -> None:
    requirements = destination.parent / "locked-requirements.txt"
    subprocess.run(
        ["uv", "export", "--locked", "--no-dev", "--no-emit-project", "--format", "requirements-txt", "--output-file", str(requirements)],
        cwd=REPO_ROOT, check=True, stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        ["uv", "pip", "install", "--target", str(destination), "--python-version", "3.11",
         "--python-platform", "aarch64-manylinux2014", "--only-binary", ":all:", "-r", str(requirements)],
        cwd=REPO_ROOT, check=True,
    )


def package(output: Path, *, include_dependencies: bool = True) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with TemporaryDirectory(prefix="cape-fear-live-agentcore-vendor-") as temporary:
        vendor = Path(temporary) / "vendor"
        if include_dependencies:
            _vendor_dependencies(vendor)
        with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
            for source, name in sorted(_source_files().items(), key=lambda item: item[1]):
                _write_member(archive, digest, name, source.read_bytes())
            if include_dependencies:
                for source in sorted(path for path in vendor.rglob("*") if path.is_file() and "__pycache__" not in path.parts):
                    _write_member(archive, digest, source.relative_to(vendor).as_posix(), source.read_bytes())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "dist" / "cape-fear-live-agentcore.zip")
    args = parser.parse_args()
    checksum = package(args.output)
    print(f"artifact={args.output.resolve()}")
    print(f"content_sha256={checksum}")


if __name__ == "__main__":
    main()
