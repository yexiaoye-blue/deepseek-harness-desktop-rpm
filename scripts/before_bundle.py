#!/usr/bin/env python3
"""Preserve upstream's bundle hook, then brand its generated Electron runtime."""
import json
from pathlib import Path
import subprocess
import sys
from brand_electron import brand


def run(root):
    root = Path(root).resolve()
    tauri = root / "apps/desktop/src-tauri"
    config = json.loads((tauri / "tauri.conf.json").read_text())
    hook = config.get("build", {}).get("beforeBundleCommand")
    if isinstance(hook, str):
        subprocess.run(hook, cwd=tauri.parent, shell=True, check=True)
    elif isinstance(hook, dict):
        cwd = Path(hook.get("cwd") or tauri.parent)
        if not cwd.is_absolute():
            cwd = tauri.parent / cwd
        subprocess.run(hook["script"], cwd=cwd, shell=True, check=True)
    elif hook is not None:
        raise ValueError("Unsupported upstream beforeBundleCommand")
    brand(tauri / "target/electron", config["productName"])


if __name__ == "__main__":
    run(sys.argv[1])
