#!/usr/bin/env python3
"""协议实验：重放 HAR bundle POST + 活体 collector 带 tag/uuid 握手 + 解码 ob。

证明：空 payload 的 /api/v2/collector 已变成 do=[]；真正 bake _px3 的是
POST /assets/js/bundle（HAR 已解码出 _px3|:1000:）。
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from urllib.parse import urlencode

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "px_solver"))
from px_ob_decode import decode_ob, tag_xor_key  # noqa: E402

APP = "PXzC5j78di"
COL = f"https://collector-{APP.lower()}.hsprotect.net"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
TAG = "YjIYfyxJHRR9"  # HAR 中 Outlook 注册用的 PX tag


def _headers():
    return {
        "User-Agent": UA,
        "Origin": "https://iframe.hsprotect.net",
        "Referer": "https://iframe.hsprotect.net/",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "*/*",
    }


def _print_ob(label: str, r: requests.Response, tag: str) -> None:
    print(f"\n[{label}] status={r.status_code} len={len(r.content)} body={r.text[:180]}")
    try:
        j = r.json()
    except Exception:
        return
    ob = j.get("ob") or ""
    do = j.get("do")
    print(f"  do={do} ob_len={len(ob)} xor_key={tag_xor_key(tag)}")
    if not ob:
        return
    segs = decode_ob(ob, tag)
    print(f"  segs={len(segs)}")
    for s in segs[:12]:
        line = s.replace("\n", " ")[:180]
        mark = " ★" if "_px" in s or "score" in s or "captcha" in s.lower() else ""
        print(f"  {line}{mark}")


def handshake_variants() -> None:
    s = requests.Session()
    uid = str(uuid.uuid4())
    vid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    common = {
        "payload": "",
        "appId": APP,
        "tag": TAG,
        "uuid": uid,
        "ft": "256",
        "seq": "0",
        "en": "NTA",
        "sid": sid,
        "vid": vid,
    }
    for path in (
        "/api/v2/collector",
        "/api/v2/msft/beacon",
        "/b/c/beacon",
        "/assets/js/bundle",
    ):
        r = s.post(COL + path, headers=_headers(), data=urlencode(common), timeout=20)
        _print_ob(path + " empty+tag", r, TAG)


def replay_har_bundle() -> None:
    har_path = Path("outlook.har")
    har = json.loads(har_path.read_text(encoding="utf-8", errors="replace"))
    for e in har["log"]["entries"]:
        req = e.get("request") or {}
        url = req.get("url") or ""
        if req.get("method") != "POST" or "/assets/js/bundle" not in url:
            continue
        post = req.get("postData") or {}
        params = {}
        if post.get("params"):
            for p in post["params"]:
                params[p.get("name", "")] = p.get("value") or ""
        elif post.get("text"):
            from urllib.parse import parse_qs
            qs = parse_qs(post["text"], keep_blank_values=True)
            params = {k: (v[0] if v else "") for k, v in qs.items()}
        if not params.get("payload") or len(params.get("payload", "")) < 10000:
            continue
        print(f"\n[replay HAR bundle] payload_len={len(params['payload'])} uuid={params.get('uuid','')[:20]}")
        r = requests.post(url, headers=_headers(), data=urlencode(params), timeout=20)
        _print_ob("HAR replay live collector", r, params.get("tag") or TAG)
        break


if __name__ == "__main__":
    print("tag", TAG, "xor", tag_xor_key(TAG))
    handshake_variants()
    replay_har_bundle()
