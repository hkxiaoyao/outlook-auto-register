#!/usr/bin/env python3
"""探针：在比特浏览器里驱动 signup 一步，定位 PX 令牌(_px3)出现点 + 是否触发按住。"""
from __future__ import annotations
import os, time, json, random, string
from bit_solve import ensure_profile, open_profile, close_profile, human_press_hold, find_px_captcha, DEFAULT_PROXY

def rand_email():
    return "".join(random.choice(string.ascii_lowercase) for _ in range(10))

def main():
    pid = os.environ.get("BIT_PROFILE_ID") or ensure_profile(DEFAULT_PROXY)
    ws = open_profile(pid)
    from playwright.sync_api import sync_playwright
    net = []
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(ws)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        def on_resp(resp):
            u = resp.url
            if any(k in u for k in ("hsprotect", "px-cloud", "perimeterx", "risk/verify", "GetCredentialType", "/API/", "amtcb", "/signup")):
                net.append(f"{resp.status} {resp.request.method} {u[:120]}")
        page.on("response", on_resp)

        print("[nav] signup …")
        page.goto("https://signup.live.com/signup", wait_until="domcontentloaded", timeout=45000)
        time.sleep(6)

        def dump_cookies(tag):
            cs = ctx.cookies()
            px = {c["name"]: c["value"][:50] for c in cs if c["name"].startswith(("_px", "px"))}
            print(f"  [{tag}] PX cookies: {px if px else '(无)'} | 总cookie数={len(cs)}")
            return px

        dump_cookies("加载后")

        # 尝试填邮箱 + 下一步（signup 首屏是邮箱/或“获取新邮箱”）
        try:
            # 优先“创建 Outlook 邮箱”链接
            filled = False
            for sel in ['#usernameInput', 'input[name="MemberName"]', 'input[type="email"]', '#MemberName']:
                el = page.query_selector(sel)
                if el:
                    email = rand_email()
                    el.fill(email); print(f"  填入邮箱前缀/邮箱: {email}")
                    filled = True
                    break
            if not filled:
                print("  未找到邮箱输入框，页面标题:", page.title())
            # 点击 Next / 下一步
            for sel in ['#nextButton', 'input[type="submit"]', 'button[type="submit"]', '#iSignupAction']:
                b = page.query_selector(sel)
                if b:
                    b.click(); print(f"  点击 {sel}"); break
            time.sleep(7)
        except Exception as e:
            print("  驱动异常:", e)

        dump_cookies("提交后")

        # 按住挑战？
        fr, box = find_px_captcha(page)
        if box:
            print(f"  [px] 出现按住挑战 box={box} → 真实按住")
            human_press_hold(page, box, hold_ms=random.randint(8500, 10500))
            time.sleep(4)
            dump_cookies("按住后")
        else:
            print("  [px] 未见按住挑战")

        print("\n=== 关键网络(PX/risk/signup) ===")
        for n in net[-30:]:
            print("  ", n)
        print("\n最终URL:", page.url, "标题:", page.title())
        browser.close()
    close_profile(pid)

if __name__ == "__main__":
    main()
