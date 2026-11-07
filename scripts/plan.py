#!/usr/bin/env python3
"""Select a published upstream stable release and pin its source commit."""
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

UPSTREAM = "dsh-tauri/deepseek-harness-desktop"
ARCHES = ("x86_64", "aarch64")


def package_name(version, arch):
    return f"dsh-tauri-{version}-1.github.{arch}.rpm"


def make_plan(release, sha, existing=None, force=False):
    tag = release.get("tag_name", "")
    if release.get("draft") is not False or release.get("prerelease") is not False:
        raise ValueError("Upstream release is not a published stable release")
    if not re.fullmatch(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", tag):
        raise ValueError(f"Unsupported stable version: {tag!r}")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("The upstream tag must resolve to a full commit SHA")
    version = tag[1:]
    expected = {package_name(version, arch) for arch in ARCHES} | {"SHA256SUMS", "UPSTREAM.json"}
    complete = False
    if existing:
        if existing.get("tag_name") != tag:
            raise ValueError("Destination release tag does not match upstream")
        marker = re.search(r"<!-- upstream-sha:([0-9a-f]{40}) -->", existing.get("body") or "")
        if not marker or marker.group(1) != sha:
            raise ValueError("Existing release source differs or is unknown; refusing to replace it")
        names = {asset["name"] for asset in existing.get("assets", []) if asset.get("state") == "uploaded" and asset.get("size", 0) > 0}
        complete = not existing.get("draft", True) and not existing.get("prerelease", True) and expected <= names
    return {
        "should_build": force or not complete,
        "tag": tag,
        "version": version,
        "source_sha": sha,
        "upstream_repository": UPSTREAM,
        "upstream_release_id": release["id"],
        "upstream_release_url": f"https://github.com/{UPSTREAM}/releases/tag/{tag}",
        "upstream_published_at": release["published_at"],
    }


def api(path, missing_ok=False):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "deepseek-harness-desktop-rpm"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    for attempt in range(3):
        try:
            with urlopen(Request("https://api.github.com" + path, headers=headers), timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code == 404 and missing_ok:
                return None
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except URLError:
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError("GitHub API did not answer")


def main():
    destination = os.environ["GITHUB_REPOSITORY"]
    release = api(f"/repos/{UPSTREAM}/releases/latest")
    # Validate the tag before using it in another API path.
    make_plan(release, "0" * 40)
    tag = release["tag_name"]
    commit = api(f"/repos/{UPSTREAM}/commits/{quote(tag, safe='')}")
    existing = api(f"/repos/{destination}/releases/tags/{quote(tag, safe='')}", missing_ok=True)
    plan = make_plan(release, commit["sha"], existing, os.environ.get("FORCE_REBUILD") == "true")
    Path(".plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            for key in ("should_build", "tag", "version", "source_sha"):
                value = str(plan[key]).lower() if isinstance(plan[key], bool) else plan[key]
                output.write(f"{key}={value}\n")
    print(json.dumps(plan, indent=2))
    with open(os.environ.get("GITHUB_STEP_SUMMARY", os.devnull), "a") as summary:
        summary.write(f"Upstream: [{tag}]({plan['upstream_release_url']})\n\nSource: `{plan['source_sha']}`\n\n")
        summary.write("Building both RPM architectures.\n" if plan["should_build"] else "Complete RPM release already exists; skipped.\n")


if __name__ == "__main__":
    main()
