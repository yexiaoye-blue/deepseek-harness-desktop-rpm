#!/usr/bin/env python3
"""Associate Electron windows with the RPM desktop launcher before app readiness."""
import json
from pathlib import Path
import sys

MARKER = "/* dsh-rpm-linux-branding:v1 */"


def bootstrap(product="DSH Tauri", wm_class="deepseek-harness-desktop"):
    identity = json.dumps({"name": product, "desktopFile": product + ".desktop", "wmClass": wm_class})
    return MARKER + "\n" + r''';(() => {
  if (process.platform !== 'linux') return;
  const { app } = require('electron');
  const fs = require('node:fs');
  const path = require('node:path');
  const identity = IDENTITY;
  process.env.ELECTRON_RS_APP_NAME = identity.name;
  app.setName(identity.name);
  app.setDesktopName(identity.desktopFile);
  app.commandLine.appendSwitch('class', identity.wmClass);
  const candidates = [
    path.resolve(__dirname, '../../icons/app.png'),
    `/usr/share/icons/hicolor/512x512/apps/${identity.wmClass}.png`,
    path.resolve(__dirname, '../../icons/32x32.png'),
  ];
  const icon = candidates.find(candidate => fs.existsSync(candidate));
  if (icon) app.on('browser-window-created', (_event, window) => window.setIcon(icon));
})();
'''.replace("IDENTITY", identity)


def brand(runtime_root, product="DSH Tauri", wm_class="deepseek-harness-desktop"):
    root = Path(runtime_root).resolve()
    entries = [root / "main.cjs"] if (root / "main.cjs").is_file() else sorted(root.glob("linux-*/main.cjs"))
    if not entries:
        raise ValueError("No Linux Electron main.cjs was found")
    for entry in entries:
        original = entry.read_text()
        if original.startswith(MARKER):
            continue
        if 'require("electron")' not in original and "require('electron')" not in original:
            raise ValueError(f"Unrecognized Electron entry point: {entry}")
        entry.write_text(bootstrap(product, wm_class) + original)
        print(f"Applied Linux desktop identity: {entry}")
    return entries


if __name__ == "__main__":
    brand(*sys.argv[1:])
