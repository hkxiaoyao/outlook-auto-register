#!/usr/bin/env python3
"""验证:Xvfb + Patchright 隐身 Chromium + xdotool 真实鼠标按住 能否过 PX。

流程:填 signup 表单到"按住"页 → xdotool 真实鼠标按住 → 看是否推进到 proofs/Add。
坐标:Xvfb 1x(无 Retina),screen = window.screenX/Y + chrome高度 + 元素viewport坐标。
"""
from __future__ import annotations
import os, time, random, string, subprocess, math

PROXY = os.environ.get("PX_PROXY") or os.environ.get("HTTP_PROXY") or ""
FIRST = ["James", "John", "Emma", "Olivia", "David", "Mary"]
LAST = ["Smith", "Johnson", "Brown", "Garcia", "Miller"]


def _proxy_dict(p):
    a = p.split(":"); return {"server": f"http://{a[0]}:{a[1]}", "username": a[2], "password": ":".join(a[3:])}


def xdo(*args):
    subprocess.run(["xdotool", *[str(a) for a in args]], check=False)


def press_hold_xdotool(sx, sy, hold_s):
    """真实 OS 鼠标:贝塞尔靠近 → 按下 → 保持(微抖) → 抬起。"""
    startx, starty = sx - random.randint(90, 170), sy - random.randint(60, 130)
    ctrlx, ctrly = (startx + sx) / 2 + random.randint(-40, 40), (starty + sy) / 2 + random.randint(-30, 30)
    steps = random.randint(22, 34)
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * startx + 2 * (1 - t) * t * ctrlx + t ** 2 * sx + random.uniform(-1.2, 1.2)
        y = (1 - t) ** 2 * starty + 2 * (1 - t) * t * ctrly + t ** 2 * sy + random.uniform(-1.0, 1.0)
        xdo("mousemove", int(x), int(y)); time.sleep(random.uniform(0.006, 0.022))
    xdo("mousemove", "--sync", int(sx), int(sy)); time.sleep(random.uniform(0.15, 0.3))
    xdo("mousedown", 1)
    t0 = time.time()
    while time.time() - t0 < hold_s:
        xdo("mousemove_relative", "--", random.randint(-2, 2), random.randint(-2, 2))
        time.sleep(random.uniform(0.05, 0.16))
    xdo("mouseup", 1)


def find_captcha(page):
    for fr in page.frames:
        try:
            el = fr.query_selector("#px-captcha")
            if el:
                bb = el.bounding_box()
                if bb and bb["width"] > 5:
                    return bb
        except Exception:
            continue
    return None


def screen_coords(page, box):
    m = page.evaluate("() => ({sx: window.screenX, sy: window.screenY, ch: window.outerHeight - window.innerHeight, dpr: window.devicePixelRatio})")
    x = m["sx"] + (box["x"] + box["width"] / 2)
    y = m["sy"] + m["ch"] + (box["y"] + box["height"] / 2)
    return x, y


def click_next(page):
    for how in (lambda: page.get_by_role("button", name="Next").first.click(timeout=3500),
                lambda: page.get_by_role("button", name="Create account").first.click(timeout=3500),
                lambda: page.click('button[type="submit"]', timeout=3500)):
        try: how(); return
        except Exception: continue


def pick(page, sel, idx):
    try:
        page.click(sel, force=True, timeout=3000); time.sleep(0.5)
        o = page.get_by_role("option"); n = o.count()
        if n: o.nth(min(idx, n - 1)).click()
    except Exception:
        pass


def main():
    from patchright.sync_api import sync_playwright
    user = "".join(random.choice(string.ascii_lowercase) for _ in range(4)) + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))
    email = user + "@outlook.com"; pwd = "Ab" + "".join(random.choice(string.ascii_letters + string.digits) for _ in range(11)) + "!7"
    print(f"[test] email={email}")
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir="/tmp/px-profile",
            headless=False,
            proxy=_proxy_dict(PROXY),
            no_viewport=True,
            args=["--start-maximized", "--window-position=0,0", "--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        # 出口 IP
        try:
            page.goto("https://api.myip.com/", timeout=30000); print("[ip]", page.inner_text("body")[:120])
        except Exception as e:
            print("[ip] err", e)
        page.goto("https://signup.live.com/signup?lic=1", wait_until="domcontentloaded", timeout=45000)
        time.sleep(5)
        created = False; pressed = False
        for step in range(24):
            time.sleep(2.5)
            try: title = page.title()
            except Exception: title = ""
            url = page.url
            print(f"[step {step}] {title[:40]} {url[:60]}")
            box = find_captcha(page)
            if box:
                sx, sy = screen_coords(page, box)
                print(f"  → PX 按住 box={box} screen=({sx:.0f},{sy:.0f}) xdotool 真实按住")
                press_hold_xdotool(sx, sy, random.uniform(9, 11)); pressed = True; time.sleep(4); continue
            low = ""
            try: low = (page.content() or "").lower()
            except Exception: pass
            if "proof" in url.lower() or "add security info" in low or "account.live.com" in url:
                created = True; print("  ✅ 推进到 proofs/账号页 → PX 已过、账号建成"); break
            el = page.query_selector('input[type="email"]')
            if el:
                if not (el.input_value() or "").strip():
                    el.click(); el.fill(""); page.keyboard.type(email, delay=random.randint(40, 100))
                click_next(page); continue
            el = page.query_selector('input[type="password"]')
            if el:
                if not (el.input_value() or "").strip():
                    el.click(); page.keyboard.type(pwd, delay=random.randint(40, 100))
                click_next(page); continue
            if page.query_selector('#BirthMonthDropdown') or page.query_selector('#BirthYear'):
                pick(page, '#BirthMonthDropdown', random.randint(1, 12)); time.sleep(0.3)
                pick(page, '#BirthDayDropdown', random.randint(1, 27)); time.sleep(0.3)
                y = page.query_selector('#BirthYear') or page.query_selector('[name="BirthYear"]')
                if y and not (y.input_value() or "").strip(): y.click(); y.fill(str(random.randint(1990, 2000)))
                click_next(page); continue
            fn = page.query_selector('#firstNameInput') or page.query_selector('[name="FirstName"]')
            if fn:
                ln = page.query_selector('#lastNameInput') or page.query_selector('[name="LastName"]')
                if not (fn.input_value() or "").strip(): fn.click(); page.keyboard.type(random.choice(FIRST), delay=40)
                if ln and not (ln.input_value() or "").strip(): ln.click(); page.keyboard.type(random.choice(LAST), delay=40)
                click_next(page); continue
            click_next(page)
        print(f"\n=== 结果 === created={created} pressed={pressed} final={page.url[:90]}")
        try: page.screenshot(path="/app/px_hold_last.png")
        except Exception: pass
        ctx.close()


if __name__ == "__main__":
    main()
