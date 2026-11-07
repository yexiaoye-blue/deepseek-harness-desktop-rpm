import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from plan import make_plan, package_name, ARCHES
from prepare_rpm import prepare as prepare_rpm
from release_files import prepare as prepare_release

SHA = "a" * 40
RELEASE = {"id": 123, "tag_name": "v0.30.4", "draft": False, "prerelease": False, "published_at": "2026-11-04T13:02:09Z"}


def existing_release():
    names = [package_name("0.30.4", arch) for arch in ARCHES] + ["SHA256SUMS", "UPSTREAM.json"]
    return {"tag_name": "v0.30.4", "draft": False, "prerelease": False,
            "body": f"<!-- upstream-sha:{SHA} -->",
            "assets": [{"name": name, "state": "uploaded", "size": 10} for name in names]}


class ReleaseSelectionTests(unittest.TestCase):
    def test_first_published_stable_release_builds(self):
        plan = make_plan(RELEASE, SHA)
        self.assertTrue(plan["should_build"])
        self.assertEqual(plan["source_sha"], SHA)

    def test_prerelease_draft_and_non_stable_tags_are_rejected(self):
        for override in ({"prerelease": True}, {"draft": True}, {"tag_name": "v0.30.4-beta.1"}, {"tag_name": "nightly"}, {"tag_name": "v0.30.4\nmain"}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                make_plan({**RELEASE, **override}, SHA)

    def test_incomplete_sha_is_rejected(self):
        with self.assertRaises(ValueError):
            make_plan(RELEASE, "a" * 7)

    def test_complete_release_skips_but_force_can_rebuild_same_source(self):
        self.assertFalse(make_plan(RELEASE, SHA, existing_release())["should_build"])
        self.assertTrue(make_plan(RELEASE, SHA, existing_release(), force=True)["should_build"])

    def test_partial_draft_and_zero_byte_assets_are_retried(self):
        for kind in ("partial", "draft", "empty"):
            own = existing_release()
            if kind == "partial":
                own["assets"].pop()
            elif kind == "draft":
                own["draft"] = True
            else:
                own["assets"][0]["size"] = 0
            with self.subTest(kind=kind):
                self.assertTrue(make_plan(RELEASE, SHA, own)["should_build"])

    def test_force_never_overwrites_a_moved_tag(self):
        with self.assertRaises(ValueError):
            make_plan(RELEASE, "b" * 40, existing_release(), force=True)

    def test_unknown_release_origin_is_not_overwritten(self):
        own = existing_release()
        own["body"] = "unrelated release"
        with self.assertRaises(ValueError):
            make_plan(RELEASE, SHA, own)


class PackagingTests(unittest.TestCase):
    def test_overlay_preserves_source_and_includes_both_license_files(self):
        packager = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tauri = root / "apps/desktop/src-tauri"
            tauri.mkdir(parents=True)
            original = json.dumps({"productName": "DSH Tauri", "version": "0.30.4"})
            (tauri / "tauri.conf.json").write_text(original)
            (root / "package.json").write_text(json.dumps({"version": "0.30.4"}))
            for name in ("LICENSE", "LICENSE.details"):
                (root / name).write_text(name)
            output = prepare_rpm(root, "0.30.4", packager)
            data = json.loads(output.read_text())
            self.assertEqual((tauri / "tauri.conf.json").read_text(), original)
            self.assertEqual(data["bundle"]["linux"]["rpm"]["release"], "1.github")
            self.assertTrue((output.parent / "licenses/LICENSE.details").exists())
            hook = Path(data["bundle"]["linux"]["rpm"]["postInstallScript"]).read_text()
            self.assertIn("resource_root='/usr/lib/DSH Tauri'", hook)
            self.assertIn("chmod 4755", hook)
            with self.assertRaises(ValueError):
                prepare_rpm(root, "0.31.0", packager)

    def test_release_requires_both_matching_architectures_and_hashes_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan = root / "plan.json"
            plan.write_text(json.dumps(make_plan(RELEASE, SHA)))
            for arch in ARCHES:
                name = package_name("0.30.4", arch)
                (root / name).write_bytes(b"test RPM " + arch.encode())
                (root / f"build-{arch}.json").write_text(json.dumps({"architecture": arch, "filename": name, "version": "0.30.4", "upstream_sha": SHA}))
            result = prepare_release(plan, root)
            self.assertEqual(len(result["builds"]), 2)
            sums = (root / "SHA256SUMS").read_text()
            self.assertIn(hashlib.sha256((root / package_name("0.30.4", "x86_64")).read_bytes()).hexdigest(), sums)
            bad = root / "build-aarch64.json"
            data = json.loads(bad.read_text())
            data["upstream_sha"] = "b" * 40
            bad.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                prepare_release(plan, root)
            bad.unlink()
            with self.assertRaises(FileNotFoundError):
                prepare_release(plan, root)


if __name__ == "__main__":
    unittest.main()
