#!/usr/bin/env python3
"""browser_proofs：页面阶段判定 + 浏览器已绑定则 OAuth 不再走 HTTP AddProof。"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class ClassifyProofsViewTests(unittest.TestCase):
    def test_add_page_from_bitbrowser_dump(self):
        from browser_proofs import classify_proofs_view

        url = "https://account.live.com/proofs/Add?mkt=EN-US&uiflavor=web&id=2926"
        html = '<input id="EmailAddress" name="EmailAddress" type="email"><input id="iNext" type="submit" value="Next">'
        self.assertEqual(classify_proofs_view(url, html), "add")

    def test_verify_page_has_ott(self):
        from browser_proofs import classify_proofs_view

        url = "https://account.live.com/proofs/Verify?mkt=EN-US"
        html = '<form id="frmVerifyProof"><input id="iOttText" name="iOttText"></form>'
        self.assertEqual(classify_proofs_view(url, html), "verify")

    def test_privacy_notice_after_bind_is_done(self):
        from browser_proofs import classify_proofs_view

        url = "https://privacynotice.account.microsoft.com/notice?ru=https://login.live.com/login.srf"
        self.assertEqual(classify_proofs_view(url, ""), "done")


class PlanRecoveryTests(unittest.TestCase):
    def test_cf_plan_makes_domain_address(self):
        env = {
            "OUTLOOK_RECOVERY_BACKEND": "cf_domain",
            "OUTLOOK_CF_WORKER_API_URL": "https://apimail.example",
            "OUTLOOK_CF_WORKER_ADMIN_TOKEN": "secret",
            "OUTLOOK_CF_DOMAIN": "your-cf-domain.com",
            "OUTLOOK_CF_USE_NEW_ADDRESS": "0",
        }
        with patch.dict(os.environ, env, clear=False):
            from browser_proofs import plan_recovery

            rec = plan_recovery()
            self.assertIsNotNone(rec)
            self.assertTrue(rec["email"].endswith("@your-cf-domain.com"))
            self.assertEqual(rec["password"], "cf_domain")
            self.assertEqual(rec["method"], "browser_proofs")


class FinishAfterProofsSkipBindTests(unittest.TestCase):
    def test_proofs_done_skips_http_addproof(self):
        fake_http = MagicMock()
        fake_http.session.headers = {}
        fake_http.session.cookies = MagicMock()

        with patch("outlook_api_reg.http_session.OutlookHttpSession", return_value=fake_http), \
             patch("outlook_api_reg.post_register.satisfy_proofs_with_external") as satisfy, \
             patch("outlook_api_reg.post_register.fetch_mail_oauth_code",
                   return_value={"code": "abc", "authorize_url": "https://login.live.com/oauth20_desktop.srf?code=abc"}), \
             patch("outlook_api_reg.post_register.exchange_code_for_token",
                   return_value={"refresh_token": "rt", "scope": "mail"}), \
             patch("ss_post._export_combo", return_value={
                 "combo_path": "/tmp/x", "snapshot": "/tmp/y", "combo_recovery": "c",
             }):
            from ss_post import finish_after_proofs

            info = finish_after_proofs(
                email="nwn9dau7hh@outlook.com",
                password="x",
                proofs_url="https://account.live.com/proofs/Add",
                proofs_html="",
                cookies=[{"name": "RPS", "value": "1", "domain": ".live.com", "path": "/"}],
                proxy=None,
                proofs_done=True,
                recovery_email="z@your-cf-domain.com",
                recovery_password="cf_domain",
                proofs_method="browser_proofs",
                log=lambda *a, **k: None,
            )
        satisfy.assert_not_called()
        self.assertEqual(info["status"], "ok")
        self.assertEqual(info["recovery_email"], "z@your-cf-domain.com")
        self.assertEqual(info["proofs_method"], "browser_proofs")


if __name__ == "__main__":
    unittest.main()
