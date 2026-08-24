#!/usr/bin/env python3
"""表单walker：在比特浏览器里逐步走 signup，dump 每步可见字段/按钮，供写建号流程参考。"""
from __future__ import annotations
import os, time, random, string
from bit_px_solver import ensure_profile_for, _open, _close

PROXY = os.environ.get("PX_PROXY") or os.environ.get("HTTP_PROXY") or ""

def dump(page, tag):
    print(f"\n===== [{tag}] url={page.url[:80]} title={page.title()[:40]} =====")
    for fr in page.frames:
        try:
            inputs = fr.eval_on_selector_all("input,select,button", """els=>els.slice(0,20).map(e=>({t:e.tagName,type:e.type||'',id:e.id||'',name:e.name||'',ph:e.placeholder||'',txt:(e.innerText||e.value||'').slice(0,20),vis:!!(e.offsetParent)}))""")
            vis = [i for i in inputs if i.get("vis")]
            if vis:
                print(f"  frame {fr.url[:50]}:")
                for i in vis: print("   ", i)
        except Exception:
            continue

def main():
    pid = ensure_profile_for(PROXY)
    ws = _open(pid)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.connect_over_cdp(ws)
        ctx = b.contexts[0] if b.contexts else b.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try: ctx.clear_cookies()
        except Exception: pass
        page.goto("https://signup.live.com/signup", wait_until="domcontentloaded", timeout=45000)
        time.sleep(5)
        dump(page, "step0-加载")

        def click_next():
            for how in (lambda: page.get_by_role("button", name="Next").first.click(timeout=4000),
                        lambda: page.click('button[type="submit"]', timeout=4000),
                        lambda: page.keyboard.press("Enter")):
                try: how(); return True
                except Exception: continue
            return False

        def errtext():
            try:
                return " | ".join(t for t in page.locator('[role="alert"], .text-danger, #error, [aria-live]').all_inner_texts() if t.strip())[:200]
            except Exception: return ""

        # 填完整邮箱
        user = "".join(random.choice(string.ascii_lowercase) for _ in range(6)) + "".join(random.choice(string.digits) for _ in range(4))
        email = user + "@outlook.com"
        el = page.query_selector('input[type="email"], input[name="email"], #floatingLabelInput4')
        if el:
            el.click(); el.fill(""); page.keyboard.type(email, delay=40); print(f"\n填完整邮箱 {email}")
        click_next()
        time.sleep(6); print("  错误提示:", errtext()); dump(page, "step1-邮箱后")
        # 填密码
        pwd = "Ab" + "".join(random.choice(string.ascii_letters+string.digits) for _ in range(10)) + "!7"
        el = page.query_selector('input[type="password"], input[name="Password"], #PasswordInput, #floatingLabelInput5')
        if el:
            el.click(); page.keyboard.type(pwd, delay=30); print(f"\n填密码 {pwd}")
        click_next()
        time.sleep(6); print("  错误提示:", errtext()); dump(page, "step2-密码后")
        # 再走两步（姓名/生日/国家）
        for stepn in (3, 4):
            for fr in page.frames:
                for i in fr.query_selector_all("input,select"):
                    try:
                        if not i.is_visible(): continue
                        typ=(i.get_attribute("type") or "").lower(); nm=(i.get_attribute("name") or "").lower()
                        if typ in ("text",) and ("first" in nm or "given" in nm): i.fill("John")
                        elif typ in ("text",) and ("last" in nm or "sur" in nm): i.fill("Smith")
                    except Exception: pass
            click_next(); time.sleep(5); print(f"  错误提示:", errtext()); dump(page, f"step{stepn}")
        b.close()
    _close(pid)

if __name__ == "__main__":
    main()
