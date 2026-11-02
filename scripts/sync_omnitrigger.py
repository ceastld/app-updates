"""同步 OmniTrigger 的公开 Windows 预览版到现有更新服务。"""
import argparse
import json
from pathlib import Path
import re
import sys
import time

from sync_eaclip import encode, get_json, verify

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "public/omnitrigger/version.json"
API = "https://update.alinko.cc/omnitrigger/version.json"
RELEASES = "https://api.github.com/repos/ceastld/omnitrigger/releases?per_page=100"
BASE = "https://github.com/ceastld/omnitrigger/releases"
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?")


def version_key(value):
    if not isinstance(value, str) or not (match := VERSION.fullmatch(value)):
        raise ValueError("版本必须为发行包支持的 SemVer")
    numbers = tuple(map(int, match.group(1, 2, 3)))
    if any(number > 2**64 - 1 for number in numbers):
        raise ValueError("版本数字超限")
    prerelease = match.group(4)
    parts = []
    for part in prerelease.split(".") if prerelease else []:
        if part.isdigit():
            if len(part) > 1 and part.startswith("0"):
                raise ValueError("预发布数字不能有前导零")
            parts.append((0, int(part)))
        else:
            parts.append((1, part))
    return (*numbers, prerelease is None, tuple(parts))


def manifest_version(release):
    # Cargo 使用 SemVer；正式三段数字兼容现有服务的四段展示版本。
    version_key(release)
    return release if "-" in release else release + ".0"


def validate_notification(event):
    payload = event.get("client_payload", {})
    tag = payload.get("tag")
    if (payload.get("product") != "omnitrigger"
            or payload.get("repository") != "ceastld/omnitrigger"
            or not isinstance(tag, str) or not tag.startswith("v")):
        raise ValueError("OmniTrigger 发布通知身份无效")
    version_key(tag[1:])
    return tag


def build_manifest(release):
    tag = release.get("tag_name", "")
    if release.get("draft") is not False or not tag.startswith("v"):
        raise ValueError("仅同步已经公开的 OmniTrigger 发行")
    version = tag[1:]
    version_key(version)
    if release.get("html_url") != f"{BASE}/tag/{tag}" or not release.get("published_at"):
        raise ValueError("发行仓库、标签或发布时间无效")
    stem = f"OmniTrigger-{version}-windows-x86_64.zip"
    assets = {}
    for name, limit in [(stem, 512 * 1024 * 1024), ("SHA256SUMS.txt", 64 * 1024)]:
        matches = [asset for asset in release["assets"] if asset["name"] == name]
        if len(matches) != 1:
            raise ValueError(f"缺少唯一的发行资产：{name}")
        asset = matches[0]
        if (asset["state"] != "uploaded" or not 0 < asset["size"] <= limit
                or asset["browser_download_url"] != f"{BASE}/download/{tag}/{name}"):
            raise ValueError(f"发行资产无效：{name}")
        assets[name] = asset
    archive = assets[stem]
    digest = archive.get("digest") or ""
    if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
        raise ValueError("发行 ZIP 缺少 GitHub SHA-256 摘要")
    notes = (release.get("body") or release.get("name") or f"OmniTrigger {version}")
    notes = notes.encode("utf-8")[:48 * 1024].decode("utf-8", errors="ignore")
    result = {
        "product": "omnitrigger", "release": version, "version": manifest_version(version),
        "publishedAt": release["published_at"], "downloadUrl": archive["browser_download_url"],
        "sha256SumsUrl": assets["SHA256SUMS.txt"]["browser_download_url"],
        "sha256": digest[7:].lower(), "size": archive["size"], "notes": notes,
    }
    if len(encode(result).encode("utf-8")) > 64 * 1024:
        raise ValueError("版本清单超过 64 KiB")
    return result


def select_release(releases):
    candidates = []
    for release in releases:
        if release.get("draft") is not False:
            continue
        tag = release.get("tag_name", "")
        try:
            key = version_key(tag[1:]) if tag.startswith("v") else None
        except ValueError:
            continue
        if key is not None:
            candidates.append((key, release))
    if not candidates:
        raise ValueError("没有已公开的 OmniTrigger 发行")
    # 最高版本不完整时直接失败，避免发布过时清单掩盖错误。
    return max(candidates, key=lambda item: item[0])[1]


def sync(manifest, path=MANIFEST):
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if version_key(manifest["release"]) < version_key(previous["release"]):
            raise ValueError("拒绝降低更新服务的版本")
        if manifest["release"] == previous["release"] and manifest["sha256"] != previous["sha256"]:
            raise ValueError("拒绝同版本 ZIP 摘要变化")
        if previous == manifest:
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(encode(manifest), encoding="utf-8", newline="\n")
    temporary.replace(path)
    return True


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-api", action="store_true")
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--validate-notification", type=Path)
    args = parser.parse_args()
    if args.validate_notification:
        print("已验证通知：", validate_notification(json.loads(args.validate_notification.read_text(encoding="utf-8"))))
    elif args.verify_api:
        expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for attempt in range(max(1, args.attempts)):
            try:
                actual, headers = get_json(API)
                verify(expected, actual, headers)
                print(f"线上 OmniTrigger 清单已验证：{expected['version']}")
                return
            except Exception:
                if attempt + 1 >= args.attempts:
                    raise
                time.sleep(10)
    else:
        releases, _ = get_json(RELEASES)
        manifest = build_manifest(select_release(releases))
        changed = sync(manifest)
        print(f"{'已更新' if changed else '无变化'} OmniTrigger：{manifest['version']}")


if __name__ == "__main__":
    main()
