#!/usr/bin/env python3
"""Add packaging metadata without changing upstream application code."""
import json
from pathlib import Path
import re
import shlex
import shutil
import sys

from plan import RPM_RELEASE

DEPENDENCIES = [
    "gtk3", "libappindicator-gtk3", "alsa-lib", "nss", "mesa-libgbm", "libdrm",
    "libX11", "libXcomposite", "libXdamage", "libXrandr", "libXtst", "libXScrnSaver",
    "cups-libs", "dbus-libs", "at-spi2-atk", "pango", "glib2", "openssl-libs", "zenity",
]


def prepare(root, version, packager):
    root, packager = Path(root).resolve(), Path(packager).resolve()
    tauri = root / "apps/desktop/src-tauri"
    config = json.loads((tauri / "tauri.conf.json").read_text())
    package = json.loads((root / "package.json").read_text())
    if config["version"] != version or package["version"] != version:
        raise ValueError("Upstream source version does not match the selected release")
    product = config["productName"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]*", product):
        raise ValueError("Unsupported product name")
    staging = tauri / ".rpm-packaging"
    staging.mkdir(exist_ok=True)
    script = (packager / "packaging/postinstall.sh.in").read_text()
    script = script.replace("@RESOURCE_ROOT@", shlex.quote("/usr/lib/" + product))
    hook = staging / "postinstall.sh"
    hook.write_text(script)
    notices = staging / "licenses"
    notices.mkdir(exist_ok=True)
    for name in ("LICENSE", "LICENSE.details", "THIRD_PARTY_NOTICES.md"):
        source = root / name
        if name != "THIRD_PARTY_NOTICES.md" or source.exists():
            shutil.copyfile(source, notices / name)
    overlay = {"build": {"beforeBundleCommand": "python3 " + shlex.quote(str(packager / "scripts/before_bundle.py")) + " " + shlex.quote(str(root))}, "bundle": {
        "license": "LicenseRef-DSH-Tauri",
        "resources": {str(notices): "licenses/upstream", str(tauri / "icons/icon.png"): "icons/app.png"},
        "linux": {"rpm": {
            "release": RPM_RELEASE,
            "depends": DEPENDENCIES,
            "conflicts": ["dsh-tauri-beta", "deepseek-harness-desktop"],
            "postInstallScript": str(hook),
        }},
    }}
    output = staging / "tauri.rpm.conf.json"
    output.write_text(json.dumps(overlay, indent=2) + "\n")
    print(output)
    return output


if __name__ == "__main__":
    prepare(*sys.argv[1:])
