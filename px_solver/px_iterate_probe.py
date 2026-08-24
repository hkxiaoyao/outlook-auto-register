#!/usr/bin/env python3
"""PerimeterX press 协议迭代探针（不依赖 BitBrowser / 不等 captcha.run 恢复）。

跑：
  python px_solver/px_iterate_probe.py

输出：collector 握手、活体 JS 版本、HAR press 样本、三家求解器 createTask 实测。
不打印完整 API key。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import requests  # noqa: E402

from outlook_api_reg.constants import PX_APP_ID, PX_COLLECTOR_BASE  # noqa: E402
from outlook_api_reg.proxy_utils import expand_proxy_template, parse_proxy  # noqa: E402

APP = PX_APP_ID
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
OUT = ROOT / "px_solver" / "px_iterate_probe.log"


def log(msg: str) -> None:
    line = msg.rstrip()
    print(line, flush=True)
    with OUT.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def mask(s: str, keep: int = 6) -> str:
    s = s or ""
    if len(s) <= keep * 2:
        return "***"
    return s[:keep] + "…" + s[-4:]


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "*/*"})
    return s


def probe_collector(s: requests.Session) -> dict:
    log("\n=== A. collector 握手 ===")
    url = f"{PX_COLLECTOR_BASE}/api/v2/collector"
    r = s.post(
        url,
        headers={
            "Origin": "https://iframe.hsprotect.net",
            "Referer": "https://iframe.hsprotect.net/",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"payload": "", "appId": APP},
        timeout=20,
    )
    log(f"POST collector status={r.status_code} len={len(r.content)}")
    body = r.text[:800]
    log(f"body={body}")
    do = []
    try:
        do = (r.json() or {}).get("do") or []
    except Exception:
        pass
    log(f"do={do}")
    return {"status": r.status_code, "do": do, "body": r.text[:2000]}


def probe_js(s: requests.Session) -> dict:
    log("\n=== B. 活体 JS 版本 ===")
    out = {}
    for name, url in (
        ("main.min.js", f"https://client.hsprotect.net/{APP}/main.min.js"),
        ("captcha.js", f"https://captcha.hsprotect.net/{APP}/captcha.js?a=c&m=0"),
    ):
        r = s.get(url, timeout=30)
        text = r.text
        ver = ""
        m = re.search(r"captcha_version['\"]?\s*[:=]\s*['\"]([^'\"]+)", text)
        if m:
            ver = m.group(1)
        copy = ""
        cm = re.search(r"\(C\)\s*20\d{2}-\s*20\d{2}[^\n]{0,80}", text)
        if cm:
            copy = cm.group(0)[:80]
        wasm = "WebAssembly" in text
        press = bool(re.search(r"Press|press.?hold|px-captcha", text, re.I))
        log(
            f"{name} status={r.status_code} bytes={len(text)} ver={ver or '?'} "
            f"wasm={wasm} press_strings={press} copy={copy}"
        )
        snap = ROOT / "px_solver" / f"live_{name}"
        try:
            old = snap.read_bytes() if snap.exists() else b""
            changed = old != r.content
            log(f"  vs {snap.name}: changed={changed} old_bytes={len(old)}")
            if changed:
                snap.write_bytes(r.content)
                log(f"  已覆盖快照 {snap}")
        except Exception as exc:
            log(f"  快照失败: {exc}")
        out[name] = {"status": r.status_code, "bytes": len(text), "ver": ver, "wasm": wasm}
    return out


def xor50_preview(b64: str) -> str:
    """unobpx 第一步：base64 → XOR 50。仅预览，shuffle 未还原。"""
    import base64

    try:
        raw = base64.b64decode(b64 + "==")
    except Exception:
        return "<b64 fail>"
    dec = bytes(x ^ 50 for x in raw)
    try:
        return dec[:180].decode("utf-8", "replace")
    except Exception:
        return repr(dec[:80])


def probe_har() -> dict:
    log("\n=== C. HAR collector / _px3 ===")
    stats = {"files": []}
    for har_path in (
        Path("outlook注册.har"),
        Path("Outlook抓包.har"),
    ):
        if not har_path.exists():
            log(f"missing {har_path}")
            continue
        log(f"parse {har_path.name} size={har_path.stat().st_size}")
        try:
            data = json.loads(har_path.read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:
            log(f"  json fail: {exc}")
            continue
        entries = (data.get("log") or {}).get("entries") or []
        px_posts = []
        px3_samples = []
        for e in entries:
            req = e.get("request") or {}
            url = req.get("url") or ""
            if "hsprotect" not in url and "perimeterx" not in url and "px-cdn" not in url:
                continue
            method = req.get("method")
            if method == "POST" and ("collector" in url or "bundle" in url or "/msft" in url):
                post = req.get("postData") or {}
                text = post.get("text") or ""
                params = {}
                if post.get("params"):
                    for p in post["params"]:
                        params[p.get("name", "")] = (p.get("value") or "")[:80]
                elif text:
                    qs = parse_qs(text, keep_blank_values=True)
                    params = {k: (v[0][:80] if v else "") for k, v in qs.items()}
                resp = ((e.get("response") or {}).get("content") or {}).get("text") or ""
                has_1000 = ":1000:" in resp or ":1000:" in text
                bake = "bake|_px3" in resp or "_px3=" in resp
                px_posts.append(
                    {
                        "url": url[:120],
                        "keys": list(params.keys())[:12],
                        "payload_len": len(params.get("payload") or text),
                        "status": (e.get("response") or {}).get("status"),
                        "bake": bake,
                        "has_1000": has_1000,
                    }
                )
                if params.get("payload") and len(px_posts) <= 3:
                    prev = xor50_preview(unquote(params["payload"][:4000]))
                    log(f"  xor50 preview: {prev[:160]}")
            # cookies
            for c in req.get("cookies") or []:
                if c.get("name") == "_px3":
                    val = c.get("value") or ""
                    px3_samples.append(
                        {
                            "has_1000": ":1000:" in val,
                            "parts": val.count(":"),
                            "prefix": val[:24],
                        }
                    )
        log(f"  PX POSTs={len(px_posts)} _px3 cookie sightings={len(px3_samples)}")
        for i, p in enumerate(px_posts[:8]):
            log(f"  post[{i}] {p}")
        n1000 = sum(1 for x in px3_samples if x.get("has_1000"))
        log(f"  _px3 with :1000: = {n1000}/{len(px3_samples)}")
        stats["files"].append(
            {"name": har_path.name, "posts": len(px_posts), "px3": len(px3_samples), "px3_1000": n1000}
        )
    return stats


def _proxy_url() -> str:
    raw = os.environ.get("HTTP_PROXY") or ""
    expanded = expand_proxy_template(raw, count=1)
    if not expanded:
        return ""
    cfg = parse_proxy(expanded[0])
    return cfg.url if cfg else ""


def probe_captcha_run() -> dict:
    log("\n=== D. captcha.run PxCaptcha2 ===")
    key = os.environ.get("CAPTCHA_RUN_API_KEY") or ""
    base = os.environ.get("CAPTCHA_RUN_API_BASE") or "https://apicn.captcha.run"
    if not key:
        log("无 CAPTCHA_RUN_API_KEY")
        return {"skip": True}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    out = {}
    try:
        w = requests.get(f"{base}/v2/users/self/wallet", headers=headers, timeout=20)
        log(f"wallet status={w.status_code} body={w.text[:240]}")
        out["wallet"] = w.status_code
    except Exception as exc:
        log(f"wallet err: {exc}")
        out["wallet"] = str(exc)
    payload = {
        "captchaType": "PxCaptcha2",
        "uaid": "00000000-0000-0000-0000-000000000001",
        "uuid": "00000000-0000-0000-0000-000000000002",
        "vid": "00000000-0000-0000-0000-000000000003",
        "userAgent": "Win",
        "country": "US",
        "timezone": "America/New_York",
    }
    try:
        c = requests.post(f"{base}/v2/tasks/", json=payload, headers=headers, timeout=20)
        log(f"createTask noproxy status={c.status_code} body={c.text[:300]}")
        out["create_noproxy"] = {"status": c.status_code, "body": c.text[:300]}
    except Exception as exc:
        log(f"create noproxy err: {exc}")
        out["create_noproxy"] = str(exc)
    proxy = _proxy_url()
    if proxy:
        cfg = parse_proxy(os.environ.get("HTTP_PROXY", "").replace("{sid}", "12345678"))
        # 用展开后的真实 sticky，避免 {sid} 字面
        cfg2 = parse_proxy(expand_proxy_template(os.environ.get("HTTP_PROXY", ""), count=1)[0])
        if cfg2:
            payload2 = {
                **payload,
                "host": cfg2.host,
                "port": cfg2.port,
                "login": cfg2.username or "",
                "password": cfg2.password or "",
            }
            try:
                c2 = requests.post(f"{base}/v2/tasks/", json=payload2, headers=headers, timeout=20)
                log(f"createTask proxy status={c2.status_code} body={c2.text[:300]}")
                out["create_proxy"] = {"status": c2.status_code, "body": c2.text[:300]}
            except Exception as exc:
                log(f"create proxy err: {exc}")
                out["create_proxy"] = str(exc)
    return out


def probe_ezcaptcha() -> dict:
    log("\n=== E. EzCaptcha PerimeterX ===")
    key = os.environ.get("EZCAPTCHA_API_KEY") or ""
    base = os.environ.get("EZCAPTCHA_API_BASE") or "https://api.ez-captcha.com"
    if not key:
        log("无 EZCAPTCHA_API_KEY")
        return {"skip": True}
    out = {}
    try:
        b = requests.post(f"{base}/getBalance", json={"clientKey": key}, timeout=20)
        log(f"getBalance status={b.status_code} body={b.text[:240]}")
        out["balance"] = b.json() if b.headers.get("content-type", "").startswith("application/json") else b.text[:200]
    except Exception as exc:
        log(f"balance err: {exc}")
        out["balance"] = str(exc)

    # 只 createTask，短轮询 2 次。失败则停，避免空烧余额。
    cfg2 = None
    expanded = expand_proxy_template(os.environ.get("HTTP_PROXY", ""), count=1)
    if expanded:
        cfg2 = parse_proxy(expanded[0])
    task = {
        "type": "PerimeterX",
        "websiteURL": "https://signup.live.com/",
        "websiteKey": APP,
    }
    if cfg2:
        task.update(
            {
                "proxyType": "http",
                "proxyAddress": cfg2.host,
                "proxyPort": cfg2.port,
                "proxyLogin": cfg2.username or "",
                "proxyPassword": cfg2.password or "",
            }
        )
    try:
        c = requests.post(f"{base}/createTask", json={"clientKey": key, "task": task}, timeout=30)
        log(f"createTask PerimeterX status={c.status_code} body={c.text[:400]}")
        data = c.json()
        out["create"] = {k: data.get(k) for k in ("errorId", "errorCode", "errorDescription", "taskId", "status")}
        tid = data.get("taskId")
        if tid and data.get("errorId", 1) == 0:
            for i in range(3):
                time.sleep(4)
                p = requests.post(
                    f"{base}/getTaskResult",
                    json={"clientKey": key, "taskId": tid},
                    timeout=20,
                )
                pj = p.json()
                log(
                    f"  poll{i+1} errorId={pj.get('errorId')} status={pj.get('status')} "
                    f"desc={pj.get('errorDescription')} sol_keys={list((pj.get('solution') or {}).keys())[:8]}"
                )
                out[f"poll{i+1}"] = {
                    "status": pj.get("status"),
                    "error": pj.get("errorDescription"),
                    "sol": bool(pj.get("solution")),
                }
                if pj.get("status") in ("ready", "failed") or pj.get("errorId", 0) == 1:
                    break
        # 再试 PxInvisibleCaptcha（更便宜，确认类型是否还开）
        inv = {"type": "PxInvisibleCaptcha", "websiteURL": "https://signup.live.com/", "websiteKey": APP}
        c2 = requests.post(f"{base}/createTask", json={"clientKey": key, "task": inv}, timeout=30)
        log(f"createTask PxInvisibleCaptcha status={c2.status_code} body={c2.text[:300]}")
        out["invisible"] = c2.json() if c2.status_code < 500 else c2.text[:200]
    except Exception as exc:
        log(f"ez err: {exc}")
        out["err"] = str(exc)
    return out


def probe_capsolver() -> dict:
    log("\n=== F. CapSolver AntiPerimeterX ===")
    key = os.environ.get("CAPSOLVER_API_KEY") or ""
    if not key:
        log("无 CAPSOLVER_API_KEY")
        return {"skip": True}
    out = {}
    try:
        b = requests.post("https://api.capsolver.com/getBalance", json={"clientKey": key}, timeout=20)
        log(f"getBalance status={b.status_code} body={b.text[:240]}")
        out["balance"] = b.text[:240]
    except Exception as exc:
        log(f"balance err: {exc}")
        out["balance"] = str(exc)
    for ttype in ("AntiPerimeterXTaskProxyless", "AntiPerimeterXTask"):
        task = {
            "type": ttype,
            "websiteURL": "https://signup.live.com/",
            "userAgent": UA,
        }
        if ttype == "AntiPerimeterXTask":
            expanded = expand_proxy_template(os.environ.get("HTTP_PROXY", ""), count=1)
            cfg = parse_proxy(expanded[0]) if expanded else None
            if not cfg:
                log(f"skip {ttype}（无代理）")
                continue
            task.update(
                {
                    "proxyType": "http",
                    "proxyAddress": cfg.host,
                    "proxyPort": str(cfg.port),
                    "proxyLogin": cfg.username or "",
                    "proxyPassword": cfg.password or "",
                }
            )
        try:
            c = requests.post(
                "https://api.capsolver.com/createTask",
                json={"clientKey": key, "task": task},
                timeout=20,
            )
            log(f"createTask {ttype} status={c.status_code} body={c.text[:350]}")
            out[ttype] = c.text[:350]
        except Exception as exc:
            log(f"{ttype} err: {exc}")
            out[ttype] = str(exc)
    return out


def main() -> int:
    OUT.write_text(f"px_iterate_probe {time.strftime('%Y-%m-%d %H:%M:%S')}\n", encoding="utf-8")
    log(f"app={APP} collector={PX_COLLECTOR_BASE}")
    log(
        f"keys captcha.run={bool(os.environ.get('CAPTCHA_RUN_API_KEY'))} "
        f"ez={bool(os.environ.get('EZCAPTCHA_API_KEY'))} "
        f"cap={bool(os.environ.get('CAPSOLVER_API_KEY'))} "
        f"captcha_run_key={mask(os.environ.get('CAPTCHA_RUN_API_KEY') or '')}"
    )
    s = session()
    try:
        probe_collector(s)
    except Exception as exc:
        log(f"collector FAIL: {exc}")
    try:
        probe_js(s)
    except Exception as exc:
        log(f"js FAIL: {exc}")
    try:
        probe_har()
    except Exception as exc:
        log(f"har FAIL: {exc}")
    try:
        probe_captcha_run()
    except Exception as exc:
        log(f"captcha.run FAIL: {exc}")
    try:
        probe_ezcaptcha()
    except Exception as exc:
        log(f"ez FAIL: {exc}")
    try:
        probe_capsolver()
    except Exception as exc:
        log(f"cap FAIL: {exc}")
    log("\n=== done ===")
    log(f"log={OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
