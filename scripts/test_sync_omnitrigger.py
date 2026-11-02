import copy
import json
from pathlib import Path
import tempfile
import unittest

from sync_eaclip import verify
from sync_omnitrigger import build_manifest, select_release, sync, version_key
from sync_updates import validate_notification


def release(version="0.1.0"):
    base = "https://github.com/ceastld/omnitrigger/releases"
    tag = "v" + version
    return {
        "tag_name": tag, "draft": False, "prerelease": True,
        "html_url": f"{base}/tag/{tag}", "published_at": "2026-10-27T17:17:10Z",
        "body": "预览版更新说明", "assets": [
            {"name": name, "state": "uploaded", "size": 100,
             "browser_download_url": f"{base}/download/{tag}/{name}", "digest": "sha256:" + "a" * 64}
            for name in (f"OmniTrigger-{version}-windows-x86_64.zip", "SHA256SUMS.txt")
        ],
    }


class OmniTriggerTests(unittest.TestCase):
    def test_preview_selection_and_manifest_match_client_semver(self):
        releases = [release("0.9.0"), release("0.10.0-beta.2"), release("0.10.0-beta.10")]
        selected = select_release(releases)
        self.assertEqual(selected["tag_name"], "v0.10.0-beta.10")
        self.assertEqual(build_manifest(selected)["version"], "0.10.0-beta.10")
        self.assertEqual(build_manifest(release())["version"], "0.1.0.0")
        self.assertGreater(version_key("0.10.0"), version_key("0.10.0-beta.10"))
        for value in ("01.0.0", "0.2.0-01", "0.2.0/../../a", "0.2.0+build"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                version_key(value)

    def test_notification_routing_preserves_existing_eaclip_contract(self):
        for product, repo, tag in (("eaclip", "ceastld/eaclip", "rust-v0.32.6"),
                                  ("omnitrigger", "ceastld/omnitrigger", "v0.2.0-beta.1")):
            event = {"client_payload": {"product": product, "repository": repo, "tag": tag}}
            self.assertEqual(validate_notification(event), tag)
            event["client_payload"]["repository"] = "ceastld/other"
            with self.assertRaises(ValueError):
                validate_notification(event)
        with self.assertRaises(ValueError):
            validate_notification({"client_payload": {"product": "unknown"}})

    def test_incomplete_draft_and_external_assets_are_rejected(self):
        candidates = []
        for field, value in (("draft", True), ("html_url", "https://example.test")):
            bad = release()
            bad[field] = value
            candidates.append(bad)
        for field, value in (("digest", None), ("size", 0), ("state", "new"),
                             ("browser_download_url", "https://example.test/app.zip")):
            bad = release()
            bad["assets"][0][field] = value
            candidates.append(bad)
        bad = release()
        bad["assets"].pop()
        candidates.append(bad)
        for candidate in candidates:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                build_manifest(candidate)
        with self.assertRaises(ValueError):
            build_manifest(select_release([release(), {**release("0.2.0"), "assets": []}]))

    def test_sync_refuses_downgrades_and_changed_bytes_and_verify_rejects_stale_api(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "omnitrigger/version.json"
            first = build_manifest(release())
            self.assertTrue(sync(first, path))
            self.assertFalse(sync(first, path))
            newer = build_manifest(release("0.2.0"))
            self.assertTrue(sync(newer, path))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), newer)
            with self.assertRaises(ValueError):
                sync(first, path)
            changed = copy.deepcopy(newer)
            changed["sha256"] = "b" * 64
            with self.assertRaises(ValueError):
                sync(changed, path)
            headers = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
            verify(newer, newer, headers)
            with self.assertRaises(ValueError):
                verify(newer, first, headers)
            with self.assertRaises(ValueError):
                verify(newer, newer, {})


if __name__ == "__main__":
    unittest.main()
