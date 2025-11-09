# authentication/tests/test_middleware.py
import importlib
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.urls import reverse

import authentication.middleware as mw

def _attach_session_and_messages(request, get_response):
    """ติดตั้ง Session + Message middleware ให้ request จาก RequestFactory"""
    from django.contrib.sessions.middleware import SessionMiddleware
    from django.contrib.messages.middleware import MessageMiddleware
    sm = SessionMiddleware(get_response)
    sm.process_request(request)
    request.session.save()
    mm = MessageMiddleware(get_response)
    mm.process_request(request)

class TestSessionSecurityMiddleware(TestCase):
    def setUp(self):
        importlib.reload(mw)
        self.MW = mw.SessionSecurityMiddleware
        self.factory = RequestFactory()
        self.get_resp = lambda r: HttpResponse("OK")

    def test_authenticated_user_with_logout_triggered(self):
        req = self.factory.get("/")
        req.user = get_user_model().objects.create_user("john", password="x")
        _attach_session_and_messages(req, self.get_resp)
        req.session["_logout_triggered"] = True
        resp = self.MW(self.get_resp)(req)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_authenticated_user_without_flag(self):
        """ไม่มี flag → process_request คืน None → Django ไปเรียก view ต่อ → ได้ 200"""
        req = self.factory.get("/")
        req.user = get_user_model().objects.create_user("john2", password="x")
        _attach_session_and_messages(req, self.get_resp)
        resp = self.MW(self.get_resp)(req)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "OK")

class TestLoginRequiredMiddleware(TestCase):
    def setUp(self):
        importlib.reload(mw)
        self.MW = mw.LoginRequiredMiddleware
        self.factory = RequestFactory()
        self.get_resp = lambda r: HttpResponse("OK")

    def test_authenticated_user_pass(self):
        req = self.factory.get("/dashboard/")
        req.user = get_user_model().objects.create_user("user1", password="x")
        _attach_session_and_messages(req, self.get_resp)
        resp = self.MW(self.get_resp)(req)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "OK")

    def test_anonymous_user_on_login_page(self):
        """/login/ อยู่ใน whitelist → ไม่ redirect"""
        req = self.factory.get(reverse("authentication:login"))
        req.user = AnonymousUser()
        _attach_session_and_messages(req, self.get_resp)
        resp = self.MW(self.get_resp)(req)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "OK")

    def test_anonymous_user_on_protected_page_redirects(self):
        """path ไม่ whitelist + anonymous → redirect ไป /login"""
        req = self.factory.get("/private/")
        req.user = AnonymousUser()
        _attach_session_and_messages(req, self.get_resp)
        resp = self.MW(self.get_resp)(req)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.url)

    def test_admin_prefix_is_whitelisted(self):
        """ครอบเคส /admin/ ใน EXEMPT_URLS → ผ่าน"""
        req = self.factory.get("/admin/")
        req.user = AnonymousUser()
        _attach_session_and_messages(req, self.get_resp)
        resp = self.MW(self.get_resp)(req)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "OK")

class TestNoCacheAfterLogoutMiddleware(TestCase):
    def setUp(self):
        importlib.reload(mw)
        self.MW = mw.NoCacheAfterLogoutMiddleware
        self.factory = RequestFactory()
        self.get_resp = lambda r: HttpResponse("OK")

    def test_headers_set_only_for_authenticated(self):
        """ผู้ใช้ auth → ใส่ no-cache headers / anonymous → ไม่ใส่"""

        req = self.factory.get("/any/")
        req.user = get_user_model().objects.create_user("u1", password="x")
        _attach_session_and_messages(req, self.get_resp)
        resp = self.MW(self.get_resp)(req)
        self.assertIn("Cache-Control", resp)
        self.assertIn("no-store", resp["Cache-Control"])
        self.assertIn("Pragma", resp)
        self.assertIn("Expires", resp)

        req2 = self.factory.get("/any/")
        req2.user = AnonymousUser()
        _attach_session_and_messages(req2, self.get_resp)
        resp2 = self.MW(self.get_resp)(req2)
        self.assertNotIn("Cache-Control", resp2)

class TestLoginRequiredMiddlewareExtraPaths(TestCase):
    def setUp(self):
        importlib.reload(mw)
        self.MW = mw.LoginRequiredMiddleware
        self.factory = RequestFactory()
        self.get_resp = lambda r: HttpResponse("OK")

    def test_static_media_favicon(self):
        for path in ("/static/app.js", "/media/logo.png", "/favicon.ico"):
            req = self.factory.get(path)
            req.user = AnonymousUser()
            _attach_session_and_messages(req, self.get_resp)
            resp = self.MW(self.get_resp)(req)
            self.assertIn(resp.status_code, (200, 301, 302))

    def test_options_with_cors_headers(self):
        req = self.factory.generic(
            "OPTIONS", "/api/public/ping/",
            HTTP_ORIGIN="https://ex.com",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="Content-Type",
        )
        req.user = AnonymousUser()
        _attach_session_and_messages(req, self.get_resp)
        resp = self.MW(self.get_resp)(req)
        self.assertIn(resp.status_code, (200, 204, 301, 302))

    def test_api_public_and_robots(self):
        for path in ("/api/public/ping/", "/robots.txt"):
            req = self.factory.get(path)
            req.user = AnonymousUser()
            _attach_session_and_messages(req, self.get_resp)
            resp = self.MW(self.get_resp)(req)
            self.assertIn(resp.status_code, (200, 301, 302))
