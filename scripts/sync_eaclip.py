"""Generate the small update API from a public, complete eaclip Release."""
import argparse
import json
import os
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "public/eaclip/version.json"
API = "https://update.alinko.cc/eaclip/version.json"
LATEST = "https://api.github.com/repos/ceastld/eaclip/releases/latest"


def get_json(address, authenticated=False):
    headers = {"User-Agent": "app-updates-eaclip", "Accept": "application/json"}
    if authenticated and os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    with urlopen(Request(address, headers=headers), timeout=30) as response:
        data = response.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise ValueError("Metadata exceeds size limit")
        return json.loads(data), dict(response.headers)


def version_tuple(value):
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", value):
        raise ValueError("Expected a stable three-part version")
    result = tuple(map(int, value.split(".")))
    if any(part > 0xFFFFFFFF for part in result):
        raise ValueError("Version component exceeds client limit")
    return result


def build_manifest(release):
    if release.get("draft") is not False or release.get("prerelease") is not False:
        raise ValueError("Only published stable releases may advance the API")
    tag = release["tag_name"]
    if not tag.startswith("rust-v"):
        raise ValueError("Expected an eaclip Rust release tag")
    version = tag.removeprefix("rust-v")
    version_tuple(version)
    base = "https://github.com/ceastld/eaclip/releases"
    if release["html_url"] != f"{base}/tag/{tag}" or not release.get("published_at"):
        raise ValueError("Release identity is invalid")
    stem = f"eaclip-{version}-windows-x64"
    assets = {}
    for suffix in (".zip", ".SHA256SUMS.txt", ".build-info.json"):
        name = stem + suffix
        matches = [asset for asset in release["assets"] if asset["name"] == name]
        if len(matches) != 1:
            raise ValueError(f"Missing unique release asset: {name}")
        asset = matches[0]
        if (asset["state"] != "uploaded" or not 0 < asset["size"] <= 512 * 1024 * 1024
                or asset["browser_download_url"] != f"{base}/download/{tag}/{name}"):
            raise ValueError(f"Invalid release asset: {name}")
        assets[suffix] = asset
    archive = assets[".zip"]
    digest = archive.get("digest", "") or ""
    if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
        raise ValueError("Portable archive has no trusted SHA-256")
    notes = (release.get("body") or release.get("name") or f"ClipHost {version}")
    notes = notes.encode("utf-8")[:48 * 1024].decode("utf-8", errors="ignore")
    manifest = {
        "product": "eaclip", "release": version, "version": version + ".0",
        "publishedAt": release["published_at"],
        "downloadUrl": archive["browser_download_url"],
        "sha256SumsUrl": assets[".SHA256SUMS.txt"]["browser_download_url"],
        "sha256": digest.removeprefix("sha256:").lower(), "size": archive["size"],
        "notes": notes,
    }
    if len(encode(manifest).encode("utf-8")) > 64 * 1024:
        raise ValueError("Manifest exceeds client size limit")
    return manifest


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def sync(manifest, path=MANIFEST):
    previous = json.loads(path.read_text(encoding="utf-8"))
    if version_tuple(manifest["release"]) < version_tuple(previous["release"]):
        raise ValueError("Refusing to move the API to an older release")
    if (manifest["release"] == previous["release"] and previous.get("sha256")
            and manifest["sha256"] != previous["sha256"]):
        raise ValueError("Refusing changed archive bytes for an existing release")
    if previous == manifest:
        return False
    path.write_text(encode(manifest), encoding="utf-8", newline="\n")
    return True


def verify(expected, actual, headers):
    headers = {key.lower(): value for key, value in headers.items()}
    if actual != expected:
        raise ValueError("Deployed API does not match the release manifest")
    if (not headers.get("content-type", "").startswith("application/json")
            or headers.get("access-control-allow-origin") != "*"):
        raise ValueError("Deployed API is missing JSON/CORS headers")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-api", action="store_true")
    parser.add_argument("--attempts", type=int, default=1)
    args = parser.parse_args()
    if args.verify_api:
        expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for attempt in range(max(1, args.attempts)):
            try:
                actual, headers = get_json(API)
                verify(expected, actual, headers)
                print(f"Verified deployed API: {expected['version']}")
                return
            except Exception:
                if attempt + 1 >= args.attempts:
                    raise
                time.sleep(10)
    else:
        try:
            release, _ = get_json(LATEST, authenticated=True)
        except HTTPError as error:
            # A repository's Actions token may not cover another public repo.
            if error.code not in (403, 404) or not os.environ.get("GH_TOKEN"):
                raise
            release, _ = get_json(LATEST)
        manifest = build_manifest(release)
        changed = sync(manifest)
        print(f"{'Updated' if changed else 'Unchanged'} eaclip: {manifest['version']}")


if __name__ == "__main__":
    main()
