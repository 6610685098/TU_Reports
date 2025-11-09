from django.test import TestCase
from django.urls import reverse
from django.http import HttpResponseRedirect
from unittest.mock import patch
from django.contrib.auth import get_user_model
from authentication.models import LoginLog

User = get_user_model()

class _PatchTUCallMixin:
    """
    เลือก patch จุดที่ view เรียกจริง:
      1) authentication.views.tu_verify
      2) authentication.views.mock_tu_verify
      3) fallback -> authentication.utils.mock_tu_api.mock_tu_verify
    """
    def _patch_tu_call(self, return_value):
        import authentication.views as v
        if getattr(v, "tu_verify", None) is not None:
            return patch("authentication.views.tu_verify", return_value=return_value)
        if getattr(v, "mock_tu_verify", None) is not None:
            return patch("authentication.views.mock_tu_verify", return_value=return_value)
        return patch("authentication.utils.mock_tu_api.mock_tu_verify", return_value=return_value)

SUCCESS = {
    "status": True, "message": "Success", "type": "student",
    "username": "student001", "displayname_th": "สมชาย ใจดี",
    "displayname_en": "Somchai Jaidee", "email": "student001@tu.ac.th",
    "tu_status": "ปกติ", "faculty": "วิศวกรรมศาสตร์", "department": "วิศวกรรมคอมพิวเตอร์",
}
FAIL = {"status": False, "message": "Invalid credential"}

class TestLoginPageRender(TestCase):
    def test_get_login_page(self):
        res = self.client.get(reverse("authentication:login"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "username")
        self.assertContains(res, "password")

    def test_already_authenticated_user_redirects_to_dashboard(self):
        u = User.objects.create_user(username="john", password="x", role="user")
        self.client.force_login(u)
        res = self.client.get(reverse("authentication:login"))
        self.assertEqual(res.status_code, 302)
        self.assertIn("/dashboard/", res.headers.get("Location", ""))

    def test_login_get_with_error_param(self):
        res = self.client.get(reverse("authentication:login") + "?error=1")
        self.assertEqual(res.status_code, 200)

class TestLocalLoginFlow(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="localuser", password="x12345x", role="user"
        )

    def test_local_login_success(self):
        url = reverse("authentication:login")
        res = self.client.post(url, {
            "username": "localuser", "password": "x12345x", "login_type": "local"
        })
        self.assertEqual(res.status_code, 302)
        self.assertIn("/dashboard/", res.headers.get("Location", ""))
        self.assertTrue(LoginLog.objects.filter(
            username="localuser", status="SUCCESS", login_method="LOCAL"
        ).exists())

    def test_local_login_fail(self):
        url = reverse("authentication:login")
        res = self.client.post(url, {
            "username": "localuser", "password": "WRONG", "login_type": "local"
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(LoginLog.objects.filter(
            username="localuser", status="FAILED", login_method="LOCAL"
        ).exists())

class TestTUAPILoginFlow(_PatchTUCallMixin, TestCase):
    def test_tu_api_success_creates_user_and_login(self):
        with self._patch_tu_call(SUCCESS):
            res = self.client.post(reverse("authentication:login"), {
                "username": "student001", "password": "student123",
                "login_type": "tu_api"
            })
        self.assertEqual(res.status_code, 302)
        self.assertIn("/dashboard/", res.headers.get("Location", ""))

        u = User.objects.get(username="student001")
        self.assertEqual(u.displayname_th, "สมชาย ใจดี")
        self.assertEqual(u.auth_provider, "TU_API")
        self.assertTrue(LoginLog.objects.filter(
            username="student001", status="SUCCESS", login_method="TU_API"
        ).exists())

    def test_tu_api_fail_stays_on_login_and_logs_failed(self):
        with self._patch_tu_call(FAIL):
            res = self.client.post(reverse("authentication:login"), {
                "username": "student001", "password": "wrong",
                "login_type": "tu_api"
            })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(LoginLog.objects.filter(
            username="student001", status="FAILED", login_method="TU_API"
        ).exists())

class TestLogoutView(TestCase):
    def test_logout_redirect_and_cache_headers(self):
        u = User.objects.create_user(username="john", password="x")
        self.client.force_login(u)
        res = self.client.get(reverse("authentication:logout"))
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse("authentication:login"), res.headers.get("Location", ""))
        self.assertEqual(res.headers.get("Cache-Control"),
                         "no-cache, no-store, must-revalidate, private")
        self.assertEqual(res.headers.get("Pragma"), "no-cache")
        self.assertEqual(res.headers.get("Expires"), "0")

    def test_logout_without_login_redirects_to_login(self):
        res = self.client.get(reverse("authentication:logout"))
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.url)

class TestLoginNextParam(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="localnext", password="x12345x", role="user"
        )

    def test_local_login_success_with_next(self):
        target = reverse("dashboard:map")
        url = reverse("authentication:login") + f"?next={target}"
        res = self.client.post(url, {
            "username": "localnext", "password": "x12345x", "login_type": "local"
        })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers.get("Location", "").startswith(target))


class TestTUAPILoginNextParam(_PatchTUCallMixin, TestCase):
    def test_tu_api_success_with_next(self):
        with self._patch_tu_call(SUCCESS):
            target = reverse("dashboard:map")
            url = reverse("authentication:login") + f"?next={target}"
            res = self.client.post(url, {
                "username": "student001", "password": "student123",
                "login_type": "tu_api"
            })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers.get("Location", "").startswith(target))

class TestLoginEdgeCases(TestCase):
    def test_post_missing_login_type(self):
        res = self.client.post(reverse("authentication:login"),
                               {"username": "x", "password": "y"})
        self.assertEqual(res.status_code, 200)

    def test_post_unknown_login_type(self):
        res = self.client.post(reverse("authentication:login"),
                               {"username": "x", "password": "y", "login_type": "weird"})
        self.assertEqual(res.status_code, 200)

    def test_post_empty_username(self):
        res = self.client.post(reverse("authentication:login"),
                               {"username": "", "password": "p", "login_type": "local"})
        self.assertEqual(res.status_code, 200)

    def test_post_empty_password(self):
        res = self.client.post(reverse("authentication:login"),
                               {"username": "u", "password": "", "login_type": "local"})
        self.assertEqual(res.status_code, 200)

class TestViewRoleRedirects(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="a", password="x", role="admin")
        self.tech = User.objects.create_user(username="b", password="x", role="technician")

    def test_admin_redirect(self):
        with patch("authentication.views.redirect",
                   side_effect=lambda to,*a,**k: HttpResponseRedirect("/stub")), \
             patch("django.shortcuts.redirect",
                   side_effect=lambda to,*a,**k: HttpResponseRedirect("/stub")):
            self.client.force_login(self.admin)
            res = self.client.get(reverse("authentication:login"))
        self.assertEqual(res.status_code, 302)
        self.assertIn("/stub", res.headers.get("Location", ""))

    def test_technician_redirect(self):
        with patch("authentication.views.redirect",
                   side_effect=lambda to,*a,**k: HttpResponseRedirect("/stub-tech")), \
             patch("django.shortcuts.redirect",
                   side_effect=lambda to,*a,**k: HttpResponseRedirect("/stub-tech")):
            self.client.force_login(self.tech)
            res = self.client.get(reverse("authentication:login"))
        self.assertEqual(res.status_code, 302)
        self.assertIn("/stub-tech", res.headers.get("Location", ""))

class TestGetClientIP(TestCase):
    def test_get_client_ip_uses_x_forwarded_for_first(self):
        url = reverse("authentication:login")
        res = self.client.post(url,
            {"username": "u", "password": "p", "login_type": "local"},
            HTTP_X_FORWARDED_FOR="1.2.3.4, 5.6.7.8",
        )
        self.assertEqual(res.status_code, 200)
        log = LoginLog.objects.order_by("-created_at").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.ip_address, "1.2.3.4")
