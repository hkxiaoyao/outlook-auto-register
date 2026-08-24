#!/usr/bin/env python3
"""探清生日下拉结构。"""
import os, time, random, string
from bit_px_solver import ensure_profile_for, _open, _close
PROXY = os.environ.get("PX_PROXY") or os.environ.get("HTTP_PROXY") or ""
def main():
    pid = ensure_profile_for(PROXY); ws = _open(pid)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.connect_over_cdp(ws)
        ctx = b.contexts[0] if b.contexts else b.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try: ctx.clear_cookies()
        except Exception: pass
        page.goto("https://signup.live.com/signup?lic=1", wait_until="domcontentloaded", timeout=45000); time.sleep(4)
        email = "".join(random.choice(string.ascii_lowercase) for _ in range(10)) + "@outlook.com"
        page.query_selector('input[type="email"]').fill(email); page.get_by_role("button", name="Next").first.click(); time.sleep(5)
        page.query_selector('input[type="password"]').fill("Ab" + "".join(random.choice(string.ascii_letters) for _ in range(10)) + "!7"); page.get_by_role("button", name="Next").first.click(); time.sleep(5)
        print("到达:", page.title())
        # 探 month dropdown
        btn = page.query_selector('#BirthMonthDropdown')
        print("BirthMonth 外层 HTML:", (btn.evaluate("e=>e.outerHTML") if btn else "无")[:300])
        if btn:
            btn.click(); time.sleep(1)
            # 点开后 dump 可能的选项容器
            html = page.evaluate("""()=>{
                const cands=[...document.querySelectorAll('[role=option],[role=listbox] *,li,option,.ms-Dropdown-item,[role=menuitem]')].filter(e=>e.offsetParent);
                return cands.slice(0,10).map(e=>({tag:e.tagName,role:e.getAttribute('role'),txt:(e.innerText||'').slice(0,15),cls:(e.className||'').slice(0,30)}));
            }""")
            print("点开后候选选项:", html)
            # 原生 select?
            sel = page.query_selector('select[name="BirthMonth"], select#BirthMonth')
            print("原生 select?", bool(sel))
        b.close()
    _close(pid)
if __name__ == "__main__":
    main()
