import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from before_bundle import run as before_bundle
from brand_electron import brand, bootstrap, MARKER


class BrandingTests(unittest.TestCase):
    def test_linux_window_uses_installed_desktop_identity_and_icon(self):
        harness = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm');
const path = require('node:path');
const source = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
for (const platform of ['linux', 'darwin']) {
  const calls = [];
  const env = {};
  let created;
  const app = {
    setName: value => calls.push(['name', value]),
    setDesktopName: value => calls.push(['desktop', value]),
    commandLine: { appendSwitch: (...args) => calls.push(['switch', ...args]) },
    on: (event, callback) => { assert.equal(event, 'browser-window-created'); created = callback; },
  };
  const context = {
    process: { platform, env }, __dirname: '/opt/dsh/runtime/linux-x64',
    require: module => {
      if (module === 'electron') return { app };
      if (module === 'node:path') return path;
      if (module === 'node:fs') return { existsSync: file => file === '/opt/dsh/icons/app.png' };
      throw Error(module);
    },
  };
  vm.runInNewContext(source, context);
  if (platform === 'linux') {
    assert.deepEqual(calls, [
      ['name', 'DSH Tauri'], ['desktop', 'DSH Tauri.desktop'],
      ['switch', 'class', 'deepseek-harness-desktop'],
    ]);
    assert.equal(env.ELECTRON_RS_APP_NAME, 'DSH Tauri');
    let icon;
    created({}, { setIcon: value => { icon = value; } });
    assert.equal(icon, '/opt/dsh/icons/app.png');
  } else {
    assert.deepEqual(calls, []);
    assert.equal(created, undefined);
    assert.deepEqual(env, {});
  }
}
"""
        subprocess.run(['node', '-e', harness], input=json.dumps(bootstrap()), text=True, check=True)

    def test_repeated_hook_preserves_runtime_and_rejects_unknown_entrypoint(self):
        with tempfile.TemporaryDirectory() as temp:
            entry = Path(temp) / 'linux-x64/main.cjs'
            entry.parent.mkdir()
            original = "const electron = require('electron');\n/* original application */\n"
            entry.write_text(original)
            brand(temp)
            once = entry.read_text()
            brand(temp)
            self.assertEqual(entry.read_text(), once)
            self.assertEqual(once.count(MARKER), 1)
            self.assertTrue(once.endswith(original))
            entry.write_text('unrecognized runtime')
            with self.assertRaises(ValueError):
                brand(temp)
            self.assertEqual(entry.read_text(), 'unrecognized runtime')

    def test_upstream_bundle_hook_runs_before_generated_runtime_is_branded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tauri = root / 'apps/desktop/src-tauri'
            entry = tauri / 'target/electron/linux-arm64/main.cjs'
            entry.parent.mkdir(parents=True)
            original = "require('electron');"
            # Simulate an upstream hook regenerating the runtime: branding must run afterwards.
            (tauri.parent / 'upstream_hook.py').write_text(
                'from pathlib import Path\nPath("src-tauri/target/electron/linux-arm64/main.cjs").write_text(' + repr(original) + ')\n')
            (tauri / 'tauri.conf.json').write_text(json.dumps({
                'productName': 'DSH Tauri',
                'build': {'beforeBundleCommand': 'python3 upstream_hook.py'},
            }))
            before_bundle(root)
            self.assertTrue(entry.read_text().startswith(MARKER))
            self.assertTrue(entry.read_text().endswith(original))


if __name__ == '__main__':
    unittest.main()
