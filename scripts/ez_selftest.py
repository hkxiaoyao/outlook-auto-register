#!/usr/bin/env python3
"""
EzCaptcha / CapSolver 自检脚本。

用途：划转余额或更换 key 后，一键确认
  1) key 是否有效、余额多少
  2) PerimeterX 通道当前能否真正解出 token（signup.live.com / PXzC5j78di）

用法：
  python scripts/ez_selftest.py                     # 读 .env 里的 EZCAPTCHA_API_KEY
  python scripts/ez_selftest.py --key xxxx          # 直接指定 key
  python scripts/ez_selftest.py --provider capsolver --key xxxx
  python scripts/ez_selftest.py --retries 5         # PX 通道重试次数
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

PX_APP_ID = "PXzC5j78di"
SIGNUP_URL = "https://signup.live.com/"

PROVIDERS = {
    "ezcaptcha": {
        "base": os.environ.get("EZCAPTCHA_API_BASE", "https://api.ez-captcha.com"),
        "px_type": "PerimeterX",
    },
    "capsolver": {
        "base": "https://api.capsolver.com",
        "px_type": "AntiPerimeterXTaskProxyless",
    },
}


def get_balance(base: str, key: str) -> None:
    try:
        r = requests.post(f"{base}/getBalance", json={"clientKey": key}, timeout=30)
        data = r.json()
        if data.get("errorId") == 0:
            print(f"  [余额] ${data.get('balance')}  (key 有效)")
        else:
            print(f"  [余额] 查询失败: {data.get('errorCode')} - {data.get('errorDescription')}")
    except Exception as exc:
        print(f"  [余额] 请求异常: {exc}")


def test_px(base: str, key: str, px_type: str, retries: int) -> bool:
    print(f"  [PX] 测试通道 type={px_type} app_id={PX_APP_ID}")
    for attempt in range(1, retries + 1):
        try:
            create = requests.post(
                f"{base}/createTask",
                json={
                    "clientKey": key,
                    "task": {
                        "type": px_type,
                        "websiteURL": SIGNUP_URL,
                        "websiteKey": PX_APP_ID,
                    },
                },
                timeout=30,
            ).json()
            if create.get("errorId") != 0:
                print(f"    #{attempt} 创建失败: {create.get('errorCode')} - {create.get('errorDescription')}")
                time.sleep(6)
                continue

            task_id = create["taskId"]
            for _ in range(12):
                time.sleep(5)
                result = requests.post(
                    f"{base}/getTaskResult",
                    json={"clientKey": key, "taskId": task_id},
                    timeout=30,
                ).json()
                status = result.get("status")
                if status == "ready":
                    keys = list((result.get("solution") or {}).keys())
                    print(f"    #{attempt} 成功! solution keys={keys}")
                    return True
                if result.get("errorId") == 1 or status in ("failed", "error"):
                    print(f"    #{attempt} 失败: {result.get('errorCode')} - {result.get('errorDescription')}")
                    break
            else:
                print(f"    #{attempt} 超时")
        except Exception as exc:
            print(f"    #{attempt} 异常: {exc}")
        time.sleep(4)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="打码平台自检")
    parser.add_argument("--provider", choices=list(PROVIDERS), default="ezcaptcha")
    parser.add_argument("--key", help="clientKey（默认读 .env 的 EZCAPTCHA_API_KEY）")
    parser.add_argument("--retries", type=int, default=3, help="PX 通道重试次数")
    args = parser.parse_args()

    key = args.key or os.environ.get(
        "CAPSOLVER_API_KEY" if args.provider == "capsolver" else "EZCAPTCHA_API_KEY", ""
    )
    if not key:
        env_name = "CAPSOLVER_API_KEY" if args.provider == "capsolver" else "EZCAPTCHA_API_KEY"
        print(f"未提供 key，且 .env 中无 {env_name}")
        return 1

    cfg = PROVIDERS[args.provider]
    print(f"=== {args.provider} 自检 ===")
    print(f"base: {cfg['base']}")
    get_balance(cfg["base"], key)
    ok = test_px(cfg["base"], key, cfg["px_type"], args.retries)

    print()
    if ok:
        print("结论: PerimeterX 通道可用，可运行 python main.py --px-mode solver")
        return 0
    print("结论: PerimeterX 通道当前不可用（多为平台端 NO_SLOT / 不支持该站点）")
    print("      建议开工单问客服，或更换打码平台 / 更换住宅代理")
    return 2


if __name__ == "__main__":
    sys.exit(main())
