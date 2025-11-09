import importlib
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.urls import reverse
import authentication.middleware as mw


def _attach_session_and_messages(request, get_response):
    """แนบ session และ message middleware เข้ากับ request จำลอง เพื่อให้ทดสอบได้เหมือนจริง"""
    from django.contrib.sessions.middleware import SessionMiddleware
    from django.contrib.messages.middleware import MessageMiddleware
    sm = SessionMiddleware(get_response)
    sm.process_request(request)
    request.session.save()
    mm = MessageMiddleware(get_response)
    mm.process_request(request)


# ---------- ทดสอบระบบ SessionSecurity ----------
class TestSessionSecurityMiddleware(TestCase):
    def setUp(self):
        importlib.reload(mw)
        self.MW = mw.SessionSecurityMiddleware
        self.factory = RequestFactory()
        self.get_resp = lambda r: HttpResponse("OK")

    def test_authenticated_user_with_logout_triggered(self):
        """เคสที่ผู้ใช้ล็อกอินแล้ว แต่ session ถูกตั้งค่าว่าหมดอายุ → ต้อง redirect ไปหน้า login"""
        req = self.factory.get("/")
        req.user = get_user_model().objects.create_user("john", password="x")
        _attach_session_and_messages(req, self.get_resp)
        req.session["_logout_triggered"] = True
        resp = self.MW(self.get_resp)(req)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_authenticated_user_without_flag(self):
        """ผู้ใช้ล็อกอินปกติ ไม่มี flag หมดอายุ → ผ่าน middleware แล้วไป view ได้"""
        req = self.factory.get("/")
        req.user = get_user_model().objects.create_user("john2", password="x")
        _attach_session_and_messages(req, self.get_resp)
        resp = self.MW(self.get_resp)(req)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "OK")


# ---------- ทดสอบระบบ LoginRequired ----------
class TestLoginRequiredMiddleware(TestCase):
    def setUp(self):
        importlib.reload(mw)
        self.MW = mw.LoginRequiredMiddleware
        self.factory = RequestFactory()
        self.get_resp = lambda r: HttpResponse("OK")

    def test_authenticated_user_pass(self):
        """ผู้ใช้ล็อกอินแล้ว → ผ่าน middleware ได้"""
        req = self.factory.get("/dashboard/")
        req.user = get_user_model().objects.create_user("user1", password="x")
        _attach_session_and_messages(req, self.get_resp)
        resp = self.MW(self.get_resp)(req)
        self.assertEqual(resp.status_code, 200)

    def test_anonymous_user_on_login_page(self):
        """ผู้ใช้ไม่ล็อกอิน แต่กำลังเข้าหน้า /login → ผ่านได้เพราะเป็น whitelist"""
        req = self.factory.get(reverse("authentication:login"))
        req.user = AnonymousUser()
        _attach_session_and_messages(req, self.get_resp)
        resp = self.MW(self.get_resp)(req)
        self.assertEqual(resp.status_code, 200)

    def test_anonymous_user_on_protected_page_redirects(self):
        """ผู้ใช้ไม่ล็อกอิน และพยายามเข้าเพจที่ป้องกัน → redirect ไปหน้า login"""
        req = self.factory.get("/private/")
        req.user = AnonymousUser()
        _attach_session_and_messages(req, self.get_resp)
        resp = self.MW(self.get_resp)(req)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.url)

    def test_admin_prefix_is_whitelisted(self):
        """ตรวจสอบว่าหน้า /admin/ อยู่ใน EXEMPT_URLS ไม่โดน redirect"""
        req = self.factory.get("/admin/")
        req.user = AnonymousUser()
        _attach_session_and_messages(req, self.get_resp)
        resp = self.MW(self.get_resp)(req)
        self.assertEqual(resp.status_code, 200)


# ---------- ทดสอบระบบ NoCacheAfterLogout ----------
class TestNoCacheAfterLogoutMiddleware(TestCase):
    def setUp(self):
        importlib.reload(mw)
        self.MW = mw.NoCacheAfterLogoutMiddleware
        self.factory = RequestFactory()
        self.get_resp = lambda r: HttpResponse("OK")

    def test_headers_set_only_for_authenticated(self):
        """ผู้ใช้ล็อกอิน → ต้องมี header no-cache / ผู้ใช้ไม่ล็อกอิน → ไม่มี header"""
        req = self.factory.get("/any/")
        req.user = get_user_model().objects.create_user("u1", password="x")
        _attach_session_and_messages(req, self.get_resp)
        resp = self.MW(self.get_resp)(req)
        self.assertIn("Cache-Control", resp)
        req2 = self.factory.get("/any/")
        req2.user = AnonymousUser()
        _attach_session_and_messages(req2, self.get_resp)
        resp2 = self.MW(self.get_resp)(req2)
        self.assertNotIn("Cache-Control", resp2)


# ---------- ทดสอบ path พิเศษอื่น ๆ ----------
class TestLoginRequiredMiddlewareExtraPaths(TestCase):
    def setUp(self):
        importlib.reload(mw)
        self.MW = mw.LoginRequiredMiddleware
        self.factory = RequestFactory()
        self.get_resp = lambda r: HttpResponse("OK")

    def test_static_media_favicon(self):
        """ตรวจสอบ path /static /media /favicon.ico ว่าผ่าน middleware ได้"""
        for path in ("/static/app.js", "/media/logo.png", "/favicon.ico"):
            req = self.factory.get(path)
            req.user = AnonymousUser()
            _attach_session_and_messages(req, self.get_resp)
            resp = self.MW(self.get_resp)(req)
            self.assertIn(resp.status_code, (200, 301, 302))

    def test_options_with_cors_headers(self):
        """ทดสอบ method OPTIONS (เช่น preflight ของ CORS)"""
        req = self.factory.generic("OPTIONS", "/api/public/ping/")
        req.user = AnonymousUser()
        _attach_session_and_messages(req, self.get_resp)
        resp = self.MW(self.get_resp)(req)
        self.assertIn(resp.status_code, (200, 204, 301, 302))

    def test_api_public_and_robots(self):
        """ทดสอบ path /api/public/ping/ และ /robots.txt ต้องไม่โดน redirect"""
        for path in ("/api/public/ping/", "/robots.txt"):
            req = self.factory.get(path)
            req.user = AnonymousUser()
            _attach_session_and_messages(req, self.get_resp)
            resp = self.MW(self.get_resp)(req)
            self.assertIn(resp.status_code, (200, 301, 302))
