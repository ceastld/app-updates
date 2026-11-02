"""沿用同一部署作业维护多产品清单，通知身份按产品分别校验。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import sync_eaclip
import sync_omnitrigger


def validate_notification(event):
    product = event.get("client_payload", {}).get("product")
    validators = {"eaclip": sync_eaclip.validate_notification, "omnitrigger": sync_omnitrigger.validate_notification}
    if product not in validators:
        raise ValueError("未注册的发布通知产品")
    return validators[product](event)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-notification", type=Path)
    parser.add_argument("--verify-api", action="store_true")
    parser.add_argument("--attempts", type=int, default=1)
    args = parser.parse_args()
    if args.validate_notification:
        event = json.loads(args.validate_notification.read_text(encoding="utf-8"))
        print("已验证发布通知：", validate_notification(event))
        return
    for product in ("eaclip", "omnitrigger"):
        command = [sys.executable, str(Path(__file__).with_name(f"sync_{product}.py"))]
        if args.verify_api:
            command += ["--verify-api", "--attempts", str(args.attempts)]
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
