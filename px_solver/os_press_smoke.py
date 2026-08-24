#!/usr/bin/env python3
"""headed Chromium + OS-HID 按住冒烟：本地 HTML 按钮，不碰 Outlook。

成功标准：按钮收到 pointerdown+pointerup，且 hold_ms 在 1000–3000。
失败常见原因：未授权「辅助功能」给 Cursor/Python。
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from os_press import os_press_available, os_press_hold, viewport_to_screen  # noqa: E402

HTML = """<!doctype html><meta charset=utf-8>
<title>os-press smoke</title>
<style>html,body{margin:0;height:100%;background:#111;color:#eee;font:16px sans-serif}
#px-captcha{position:absolute;left:200px;top:180px;width:360px;height:48px;background:#2b6;border:0;font-size:18px;cursor:pointer}
#log{margin-top:260px;padding:12px;white-space:pre}</style>
<button id="px-captcha">Press and hold</button>
<div id="log"></div>
<script>
window.__down=0; window.__up=0; window.__held=0;
const b=document.getElementById('px-captcha');
const log=document.getElementById('log');
function L(s){log.textContent += s+'\\n'}
b.addEventListener('pointerdown', e => { window.__down=performance.now(); L('down '+e.pointerType+' '+e.clientX.toFixed(1)+','+e.clientY.toFixed(1)); });
b.addEventListener('pointerup', e => { window.__up=performance.now(); window.__held=window.__up-window.__down; L('up held='+window.__held.toFixed(0)); });
</script>
"""


def main() -> int:
    ok, why = os_press_available()
    print("os_press:", ok, why)
    if not ok:
        return 2
    html = Path(tempfile.gettempdir()) / "px_os_press_smoke.html"
    html.write_text(HTML, encoding="utf-8")
    print("html", html)

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        print("playwright missing:", exc)
        return 3

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page(viewport={"width": 800, "height": 500})
        page.goto(html.as_uri())
        time.sleep(0.6)
        box = page.query_selector("#px-captcha").bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        sx, sy = viewport_to_screen(page, cx, cy)
        print(f"viewport=({cx:.1f},{cy:.1f}) screen=({sx:.1f},{sy:.1f})")
        os_press_hold(sx, sy, 1700, print)
        time.sleep(0.4)
        stats = page.evaluate("() => ({down:window.__down, up:window.__up, held:window.__held, log:document.getElementById('log').textContent})")
        print("result", stats)
        browser.close()
    held = float(stats.get("held") or 0)
    if held >= 800:
        print("SMOKE PASS held_ms", held)
        return 0
    print("SMOKE FAIL — HID 事件未送达页面（给终端/Cursor 开辅助功能）")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
