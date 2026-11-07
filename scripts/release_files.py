#!/usr/bin/env python3
"""Prepare checksums and provenance only after both architectures are available."""
import hashlib
import json
import os
from pathlib import Path
import sys

from plan import ARCHES, package_name


def prepare(plan_path, asset_dir):
    plan = json.loads(Path(plan_path).read_text())
    assets = Path(asset_dir)
    builds = []
    checksums = []
    for arch in ARCHES:
        data = json.loads((assets / f"build-{arch}.json").read_text())
        filename = package_name(plan["version"], arch)
        if data["architecture"] != arch or data["version"] != plan["version"] or data["upstream_sha"] != plan["source_sha"] or data["filename"] != filename:
            raise ValueError(f"Build provenance mismatch for {arch}")
        file = assets / filename
        if not file.is_file() or file.stat().st_size == 0:
            raise ValueError(f"Missing RPM for {arch}")
        with file.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        data["sha256"] = digest
        builds.append(data)
        checksums.append(f"{digest}  {filename}\n")
    provenance = {**plan, "builds": builds, "packaging_repository": os.environ.get("GITHUB_REPOSITORY"),
                  "packaging_commit": os.environ.get("GITHUB_SHA"),
                  "workflow_run": f"https://github.com/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ.get('GITHUB_RUN_ID')}"}
    provenance.pop("should_build", None)
    output = assets / "UPSTREAM.json"
    output.write_text(json.dumps(provenance, indent=2) + "\n")
    checksums.append(f"{hashlib.sha256(output.read_bytes()).hexdigest()}  UPSTREAM.json\n")
    (assets / "SHA256SUMS").write_text("".join(checksums))
    body = f"""Community RPM packages for [DSH Tauri {plan['tag']}]({plan['upstream_release_url']}).

- Upstream source: `{plan['source_sha']}`
- Architectures: **x86_64** and **aarch64**
- Target distribution: **Fedora 43+**
- Both packages passed RPM structure, GLIBC baseline, and Fedora container installation checks.
- This is a normal online installer; missing Harness components are downloaded on first launch.
- Application self-updates are disabled for this package; install future RPMs from this repository.
- Original upstream license notices, including `LICENSE.details`, are included in each RPM.

Install the RPM matching your architecture with `sudo dnf install ./dsh-tauri-*.rpm`.
Use `sha256sum -c SHA256SUMS --ignore-missing` to verify downloaded files.

These are community builds, not official upstream release assets. Desktop GUI behavior still depends on the host session.

<!-- upstream-sha:{plan['source_sha']} -->
"""
    (assets / "release-notes.md").write_text(body)
    return provenance


if __name__ == "__main__":
    prepare(*sys.argv[1:])
