import copy
import json
from pathlib import Path
import tempfile
import unittest

from sync_eaclip import build_manifest, encode, sync, validate_notification, verify


def release(version="0.32.5"):
    base = "https://github.com/ceastld/eaclip/releases"
    tag = "rust-v" + version
    stem = f"eaclip-{version}-windows-x64"
    return {
        "tag_name": tag, "draft": False, "prerelease": False,
        "html_url": f"{base}/tag/{tag}", "published_at": "2026-10-29T15:09:33Z",
        "body": "更新说明", "assets": [
            {"name": stem + suffix, "size": 1234, "state": "uploaded",
             "browser_download_url": f"{base}/download/{tag}/{stem}{suffix}",
             "digest": "sha256:" + "a" * 64}
            for suffix in (".zip", ".SHA256SUMS.txt", ".build-info.json")
        ],
    }


class UpdateApiTests(unittest.TestCase):
    def test_release_notifications_require_the_expected_product_repository_and_stable_tag(self):
        event = {'client_payload': {'product': 'eaclip', 'repository': 'ceastld/eaclip', 'tag': 'rust-v0.32.6'}}
        self.assertEqual(validate_notification(event), 'rust-v0.32.6')
        for field, value in [('product', 'raishot'), ('repository', 'ceastld/other'),
                             ('tag', 'rust-v0.32.6-beta'), ('tag', '../main'), ('tag', None)]:
            bad = copy.deepcopy(event)
            bad['client_payload'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_notification(bad)

    def test_new_release_advances_version_and_all_asset_addresses(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "version.json"
            path.write_text(encode(build_manifest(release())), encoding="utf-8")
            updated = build_manifest(release("0.32.6"))
            self.assertTrue(sync(updated, path))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["version"], "0.32.6.0")
            self.assertIn("rust-v0.32.6/eaclip-0.32.6", updated["downloadUrl"])
            self.assertFalse(sync(updated, path))
            with self.assertRaises(ValueError):
                sync(build_manifest(release()), path)
            changed = copy.deepcopy(updated)
            changed["sha256"] = "b" * 64
            with self.assertRaises(ValueError):
                sync(changed, path)

    def test_incomplete_draft_prerelease_and_untrusted_assets_do_not_publish(self):
        candidates = []
        for key, value in (("draft", True), ("prerelease", True),
                           ("tag_name", "rust-v0.32.6-beta"), ("html_url", "https://example.test")):
            item = release()
            item[key] = value
            candidates.append(item)
        for key, value in (("digest", None), ("size", 0), ("state", "new"),
                           ("browser_download_url", "https://example.test/app.zip")):
            item = release()
            item["assets"][0][key] = value
            candidates.append(item)
        item = release()
        item["assets"].pop()
        candidates.append(item)
        for item in candidates:
            with self.subTest(item=item), self.assertRaises(ValueError):
                build_manifest(item)

    def test_api_verification_rejects_stale_version_and_missing_cors(self):
        expected = build_manifest(release("0.32.6"))
        headers = {"Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*"}
        verify(expected, expected, headers)
        with self.assertRaises(ValueError):
            verify(expected, build_manifest(release()), headers)
        with self.assertRaises(ValueError):
            verify(expected, expected, {})


if __name__ == "__main__":
    unittest.main()
