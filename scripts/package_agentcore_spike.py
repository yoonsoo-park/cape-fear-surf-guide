#!/usr/bin/env python3
"""Create the minimal, deterministic source zip for the AgentCore MCP v2 spike."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXED_TIMESTAMP = (2026, 8, 22, 0, 0, 0)


def _source_files() -> dict[Path, str]:
    """Return archive-member paths for the read-only MCP application only."""
    files: dict[Path, str] = {
        REPO_ROOT / "mcp_runtime" / "agentcore_entrypoint.py": "agentcore_entrypoint.py",
        REPO_ROOT / "mcp_runtime" / "agentcore_package_init.py": "__init__.py",
        REPO_ROOT / "mcp_runtime" / "requirements.txt": "requirements.txt",
    }
    for path in sorted((REPO_ROOT / "mcp_runtime" / "mcp_runtime").glob("*.py")):
        files[path] = f"mcp_runtime/{path.name}"
    for name in ("__init__.py", "application.py", "brief.py", "fixtures.py", "mcp_contract.py", "policy.py", "schema.py"):
        path = REPO_ROOT / "surf" / name
        files[path] = path.relative_to(REPO_ROOT).as_posix()
    for name in ("normal.json", "hazard.json", "stale.json", "conflict.json"):
        path = REPO_ROOT / "fixtures" / name
        files[path] = path.relative_to(REPO_ROOT).as_posix()
    return files


def _write_member(archive: ZipFile, digest: "hashlib._Hash", member_name: str, contents: bytes) -> None:
    info = ZipInfo(member_name, date_time=FIXED_TIMESTAMP)
    info.compress_type = ZIP_DEFLATED
    archive.writestr(info, contents)
    digest.update(member_name.encode())
    digest.update(b"\0")
    digest.update(contents)


def _vendor_dependencies(destination: Path) -> None:
    """Install the locked Linux ARM64 runtime dependencies outside the repository.

    AgentCore's code-artifact runner executes the zip directly and did not
    install its bundled requirements file. Vendoring the lockfile-resolved
    Linux ARM64 wheels makes startup independent of that undocumented behavior
    and avoids copying the host (macOS) virtual environment.
    """
    runtime_dir = REPO_ROOT / "mcp_runtime"
    requirements = destination.parent / "locked-requirements.txt"
    subprocess.run(
        ["uv", "export", "--locked", "--no-dev", "--no-emit-project", "--format", "requirements-txt", "--output-file", str(requirements)],
        cwd=runtime_dir,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            "uv", "pip", "install", "--target", str(destination), "--python-version", "3.11",
            "--python-platform", "aarch64-unknown-linux-gnu", "-r", str(requirements),
        ],
        cwd=runtime_dir,
        check=True,
    )


def package(output: Path, *, include_dependencies: bool = True) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with TemporaryDirectory(prefix="cape-fear-agentcore-vendor-") as temporary:
        vendor = Path(temporary) / "vendor"
        if include_dependencies:
            _vendor_dependencies(vendor)
        with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
            for source, member_name in sorted(_source_files().items(), key=lambda item: item[1]):
                _write_member(archive, digest, member_name, source.read_bytes())
            if include_dependencies:
                for source in sorted(path for path in vendor.rglob("*") if path.is_file() and "__pycache__" not in path.parts):
                    _write_member(archive, digest, source.relative_to(vendor).as_posix(), source.read_bytes())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "dist" / "cape-fear-mcp-v2-spike.zip")
    args = parser.parse_args()
    checksum = package(args.output)
    print(f"artifact={args.output.resolve()}")
    print(f"content_sha256={checksum}")


if __name__ == "__main__":
    main()
