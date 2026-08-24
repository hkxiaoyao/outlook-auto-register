#!/usr/bin/env python3
"""SwiftShader 软件渲染探针（Path D 前置校验）。

目的：在跑完整 PX 收割前，先确认 headless Chromium 用 SwiftShader
真的能"绘制"（有可用 WebGL/canvas 上下文、真实 paint），从而满足
captcha.js 的 captchaNotRendered 渲染门。

用法：
    .venv/bin/python px_solver/px_swiftshader_probe.py

对每组候选启动参数，打印：是否成功启动、WebGL renderer 字符串、
canvas 2D 是否可绘、devicePixelRatio 等，最后给出建议采用的参数组。
"""
from __future__ import annotations

import json
import sys
import traceback

# 候选启动参数组（macOS darwin，按优先级尝试）
_COMMON = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
]
FLAG_SETS = [
    (
        "swiftshader(angle)",
        ["--headless=new", "--use-gl=angle", "--use-angle=swiftshader",
         "--enable-unsafe-swiftshader"] + _COMMON,
    ),
    (
        "swiftshader(angle)+ignore-blocklist",
        ["--headless=new", "--use-gl=angle", "--use-angle=swiftshader",
         "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
         "--enable-webgl", "--enable-webgl2-compute-context"] + _COMMON,
    ),
    (
        "use-gl=swiftshader",
        ["--headless=new", "--use-gl=swiftshader",
         "--enable-unsafe-swiftshader"] + _COMMON,
    ),
    (
        "swiftshader-webgl",
        ["--headless=new", "--use-gl=swiftshader-webgl",
         "--enable-unsafe-swiftshader"] + _COMMON,
    ),
    (
        "angle+in-process-gpu",
        ["--headless=new", "--use-gl=angle", "--use-angle=swiftshader",
         "--enable-unsafe-swiftshader", "--in-process-gpu",
         "--ignore-gpu-blocklist"] + _COMMON,
    ),
    (
        "no-headless-flag(pw default)+swiftshader",
        ["--use-gl=angle", "--use-angle=swiftshader",
         "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] + _COMMON,
    ),
]

PROBE_JS = r"""
() => {
  const out = {};
  try {
    // 独立 canvas 做 2D paint（一个 canvas 只能有一种 context 类型）
    const c2 = document.createElement('canvas');
    c2.width = 300; c2.height = 150;
    document.body.appendChild(c2);
    const ctx2d = c2.getContext('2d');
    if (ctx2d) {
      ctx2d.fillStyle = '#123456';
      ctx2d.fillRect(0, 0, 120, 60);
      const px = ctx2d.getImageData(10, 10, 1, 1).data;
      out.canvas2d_pixel = Array.from(px);
      out.canvas2d_painted = (px[0] !== 0 || px[1] !== 0 || px[2] !== 0);
    } else {
      out.canvas2d_painted = false;
    }
    // 独立 canvas 做 WebGL
    const cg = document.createElement('canvas');
    cg.width = 300; cg.height = 150;
    document.body.appendChild(cg);
    out.webgl_error = null;
    cg.addEventListener('webglcontextcreationerror', (ev) => {
      out.webgl_error = ev.statusMessage || 'unknown';
    }, false);
    let gl = cg.getContext('webgl') || cg.getContext('experimental-webgl');
    out.webgl_available = !!gl;
    if (gl) {
      const dbg = gl.getExtension('WEBGL_debug_renderer_info');
      out.webgl_vendor = dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR);
      out.webgl_renderer = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
      out.webgl_version = gl.getParameter(gl.VERSION);
      // 真的画一帧，确认软件光栅可用
      gl.clearColor(0.1, 0.2, 0.3, 1.0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      const rp = new Uint8Array(4);
      gl.readPixels(1, 1, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, rp);
      out.webgl_readpixels = Array.from(rp);
    }
    // 独立 canvas 做 WebGL2
    const cg2 = document.createElement('canvas');
    let gl2 = cg2.getContext('webgl2');
    out.webgl2_available = !!gl2;
    if (gl2) {
      const dbg2 = gl2.getExtension('WEBGL_debug_renderer_info');
      out.webgl2_renderer = dbg2 ? gl2.getParameter(dbg2.UNMASKED_RENDERER_WEBGL) : gl2.getParameter(gl2.RENDERER);
    }
  } catch (e) {
    out.error = String(e);
  }
  out.devicePixelRatio = window.devicePixelRatio;
  out.userAgent = navigator.userAgent;
  out.webdriver = navigator.webdriver;
  return out;
}
"""

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")


def probe_one(engine: str, label: str, args: list[str]) -> dict:
    result = {"engine": engine, "label": label, "args": args, "launched": False}
    if engine == "patchright":
        from patchright.sync_api import sync_playwright
    else:
        from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=args)
            result["launched"] = True
            ctx = browser.new_context(
                user_agent=UA,
                viewport={"width": 1280, "height": 800},
            )
            page = ctx.new_page()
            page.goto("about:blank")
            probe = page.evaluate(PROBE_JS)
            result["probe"] = probe
            browser.close()
    except Exception as e:
        result["exception"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc()[-1500:]
    return result


def main() -> None:
    engines = ["playwright", "patchright"]
    all_results = []
    for engine in engines:
        for label, args in FLAG_SETS:
            print(f"\n=== [{engine}] {label} ===")
            r = probe_one(engine, label, args)
            all_results.append(r)
            if not r["launched"]:
                print(f"  ❌ 启动失败: {r.get('exception')}")
                continue
            p = r.get("probe", {})
            print(f"  ✅ 启动成功")
            print(f"     canvas2d_painted = {p.get('canvas2d_painted')}")
            print(f"     webgl_available  = {p.get('webgl_available')}")
            print(f"     webgl_error      = {p.get('webgl_error')}")
            print(f"     webgl_renderer   = {p.get('webgl_renderer')}")
            print(f"     webgl_vendor     = {p.get('webgl_vendor')}")
            print(f"     webgl_readpixels = {p.get('webgl_readpixels')}")
            print(f"     webgl2_available = {p.get('webgl2_available')}")
            print(f"     webgl2_renderer  = {p.get('webgl2_renderer')}")
            print(f"     webdriver        = {p.get('webdriver')}")
            print(f"     devicePixelRatio = {p.get('devicePixelRatio')}")

    # 汇总建议
    print("\n\n===== 汇总 =====")
    best = None
    for r in all_results:
        p = r.get("probe", {})
        ok = r["launched"] and p.get("webgl_available") and p.get("canvas2d_painted")
        tag = "GOOD" if ok else "----"
        print(f"[{tag}] {r['engine']:10s} {r['label']:24s} "
              f"webgl={p.get('webgl_available')} renderer={str(p.get('webgl_renderer'))[:50]}")
        if ok and best is None:
            best = r
    if best:
        print(f"\n推荐: engine={best['engine']} label={best['label']}")
        print("args=" + json.dumps(best["args"]))
    else:
        print("\n⚠️ 没有任何组合同时满足 webgl+canvas2d。见各组 exception。")


if __name__ == "__main__":
    main()
