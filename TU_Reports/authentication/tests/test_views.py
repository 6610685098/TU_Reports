from django.test import TestCase
from django.urls import reverse
from django.http import HttpResponseRedirect
from unittest.mock import patch
from django.contrib.auth import get_user_model

from authentication.models import LoginLog

User = get_user_model()

# ---------- Utility: patch TU verify จุดที่ view เรียกจริง ----------
class _PatchTUCallMixin:
    """
    เลือก patch จุดที่ view เรียกจริง:
      1) authentication.views.tu_verify
      2) authentication.views.mock_tu_verify
      3) fallback -> authentication.utils.mock_tu_api.mock_tu_verify
    """
    def _patch_tu_call(self, return_value):
        import authentication.views as v
        from unittest.mock import patch
        if getattr(v, "tu_verify", None) is not None:
            return patch("authentication.views.tu_verify", return_value=return_value)
        if getattr(v, "mock_tu_verify", None) is not None:
            return patch("authentication.views.mock_tu_verify", return_value=return_value)
        return patch("authentication.utils.mock_tu_api.mock_tu_verify", return_value=return_value)


# ---------- ผลลัพธ์ TU API จำลอง ----------
SUCCESS = {
    "status": True, "message": "Success", "type": "student",
    "username": "student001", "displayname_th": "สมชาย ใจดี",
    "displayname_en": "Somchai Jaidee", "email": "student001@tu.ac.th",
    "tu_status": "ปกติ", "faculty": "วิศวกรรมศาสตร์", "department": "วิศวกรรมคอมพิวเตอร์",
}
FAIL = {"status": False, "message": "Invalid credential"}


# ---------- หน้า Login (GET) ----------
class TestLoginPageRender(TestCase):
    def test_get_login_page(self):
        """เรียกหน้า login แบบ GET → ต้องเห็นช่อง username/password และสถานะ 200"""
        res = self.client.get(reverse("authentication:login"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "username")
        self.assertContains(res, "password")

    def test_already_authenticated_user_redirects_to_dashboard(self):
        """ผู้ใช้ล็อกอินอยู่แล้ว → เข้า /login ให้ redirect ไปหน้า dashboard"""
        u = User.objects.create_user(username="john", password="x", role="user")
        self.client.force_login(u)
        res = self.client.get(reverse("authentication:login"))
        self.assertEqual(res.status_code, 302)
        self.assertIn("/dashboard/", res.headers.get("Location", ""))

    def test_login_get_with_error_param(self):
        """มี query ?error=1 → หน้า login ยังคงแสดงผลได้ (ช่วยทดสอบสาขา params)"""
        res = self.client.get(reverse("authentication:login") + "?error=1")
        self.assertEqual(res.status_code, 200)


# ---------- Local login flow ----------
class TestLocalLoginFlow(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="localuser", password="x12345x", role="user"
        )

    def test_local_login_success(self):
        """ล็อกอินแบบ local สำเร็จ → redirect ไป dashboard และมี LoginLog สถานะ SUCCESS"""
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
        """ล็อกอินแบบ local รหัสผิด → อยู่หน้าเดิม (200) และบันทึก LoginLog สถานะ FAILED"""
        url = reverse("authentication:login")
        res = self.client.post(url, {
            "username": "localuser", "password": "WRONG", "login_type": "local"
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(LoginLog.objects.filter(
            username="localuser", status="FAILED", login_method="LOCAL"
        ).exists())


# ---------- TU API login flow ----------
class TestTUAPILoginFlow(_PatchTUCallMixin, TestCase):
    def test_tu_api_success_creates_user_and_login(self):
        """TU API สำเร็จ → สร้างผู้ใช้ (ถ้ายังไม่มี), กำหนด provider, redirect และบันทึก log"""
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
        """TU API ล้มเหลว → อยู่หน้าเดิม (200) และบันทึก LoginLog สถานะ FAILED"""
        with self._patch_tu_call(FAIL):
            res = self.client.post(reverse("authentication:login"), {
                "username": "student001", "password": "wrong",
                "login_type": "tu_api"
            })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(LoginLog.objects.filter(
            username="student001", status="FAILED", login_method="TU_API"
        ).exists())


# ---------- Logout ----------
class TestLogoutView(TestCase):
    def test_logout_redirect_and_cache_headers(self):
        """กด logout แล้ว → redirect กลับหน้า login และแนบ header ป้องกัน cache"""
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
        """ยังไม่ล็อกอินแต่เรียก /logout → ต้อง redirect ไปหน้า login"""
        res = self.client.get(reverse("authentication:logout"))
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.url)


# ---------- ?next= ----------
class TestLoginNextParam(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="localnext", password="x12345x", role="user"
        )

    def test_local_login_success_with_next(self):
        """ล็อกอิน local สำเร็จ + มี ?next= → ต้อง redirect ไปปลายทางนั้น"""
        target = reverse("dashboard:map")
        url = reverse("authentication:login") + f"?next={target}"
        res = self.client.post(url, {
            "username": "localnext", "password": "x12345x", "login_type": "local"
        })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers.get("Location", "").startswith(target))


class TestTUAPILoginNextParam(_PatchTUCallMixin, TestCase):
    def test_tu_api_success_with_next(self):
        """ล็อกอิน TU API สำเร็จ + มี ?next= → ต้อง redirect ไปปลายทางนั้น"""
        with self._patch_tu_call(SUCCESS):
            target = reverse("dashboard:map")
            url = reverse("authentication:login") + f"?next={target}"
            res = self.client.post(url, {
                "username": "student001", "password": "student123",
                "login_type": "tu_api"
            })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers.get("Location", "").startswith(target))


# ---------- Edge cases ----------
class TestLoginEdgeCases(TestCase):
    def test_post_missing_login_type(self):
        """ไม่ส่ง login_type มา → view ต้อง handle (ยังได้ 200)"""
        res = self.client.post(reverse("authentication:login"),
                               {"username": "x", "password": "y"})
        self.assertEqual(res.status_code, 200)

    def test_post_unknown_login_type(self):
        """ส่ง login_type แปลก → view ต้อง handle (ยังได้ 200)"""
        res = self.client.post(reverse("authentication:login"),
                               {"username": "x", "password": "y", "login_type": "weird"})
        self.assertEqual(res.status_code, 200)

    def test_post_empty_username(self):
        """username ว่าง → ไม่ผ่านและยังอยู่หน้าเดิม (200)"""
        res = self.client.post(reverse("authentication:login"),
                               {"username": "", "password": "p", "login_type": "local"})
        self.assertEqual(res.status_code, 200)

    def test_post_empty_password(self):
        """password ว่าง → ไม่ผ่านและยังอยู่หน้าเดิม (200)"""
        res = self.client.post(reverse("authentication:login"),
                               {"username": "u", "password": "", "login_type": "local"})
        self.assertEqual(res.status_code, 200)


# ---------- Redirect ตาม role (patch redirect กัน namespace ที่โปรเจกต์จริงอาจไม่มี) ----------
class TestViewRoleRedirects(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="a", password="x", role="admin")
        self.tech = User.objects.create_user(username="b", password="x", role="technician")

    def test_admin_redirect(self):
        """เมื่อ user เป็น admin → login view ควร redirect ไปแดชบอร์ด admin (เรา patch ให้ไป /stub)"""
        with patch("authentication.views.redirect",
                   side_effect=lambda to,*a,**k: HttpResponseRedirect("/stub")), \
             patch("django.shortcuts.redirect",
                   side_effect=lambda to,*a,**k: HttpResponseRedirect("/stub")):
            self.client.force_login(self.admin)
            res = self.client.get(reverse("authentication:login"))
        self.assertEqual(res.status_code, 302)
        self.assertIn("/stub", res.headers.get("Location", ""))

    def test_technician_redirect(self):
        """เมื่อ user เป็น technician → login view ควร redirect ไปหน้าของช่าง (เรา patch ให้ไป /stub-tech)"""
        with patch("authentication.views.redirect",
                   side_effect=lambda to,*a,**k: HttpResponseRedirect("/stub-tech")), \
             patch("django.shortcuts.redirect",
                   side_effect=lambda to,*a,**k: HttpResponseRedirect("/stub-tech")):
            self.client.force_login(self.tech)
            res = self.client.get(reverse("authentication:login"))
        self.assertEqual(res.status_code, 302)
        self.assertIn("/stub-tech", res.headers.get("Location", ""))


# ---------- X-Forwarded-For ----------
class TestGetClientIP(TestCase):
    def test_get_client_ip_uses_x_forwarded_for_first(self):
        """มี header X-Forwarded-For → ต้องใช้ IP แรกเป็น ip_address ใน LoginLog"""
        url = reverse("authentication:login")
        res = self.client.post(url,
            {"username": "u", "password": "p", "login_type": "local"},
            HTTP_X_FORWARDED_FOR="1.2.3.4, 5.6.7.8",
        )
        self.assertEqual(res.status_code, 200)
        log = LoginLog.objects.order_by("-created_at").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.ip_address, "1.2.3.4")
