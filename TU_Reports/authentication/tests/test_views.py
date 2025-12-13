from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from unittest.mock import patch

from authentication.models import LoginLog
from authentication.views import get_client_ip

User = get_user_model()


# ---------- Mock TU API responses ----------
TU_SUCCESS_STUDENT = {
    "status": True,
    "message": "Success",
    "type": "student",
    "username": "student001",
    "tu_status": "ปกติ",
    "displayname_th": "สมชาย นักศึกษา",
    "displayname_en": "Somchai Student",
    "email": "student001@dome.tu.ac.th",
    "faculty": "วิศวกรรมศาสตร์",
    "department": "ไฟฟ้าและคอมพิวเตอร์",
    "role": "user",
}

TU_SUCCESS_ADMIN = {
    "status": True,
    "message": "Success",
    "type": "officer",
    "username": "admin001",
    "tu_status": "ปกติ",
    "displayname_th": "สมศักดิ์ เจ้าหน้าที่",
    "displayname_en": "Somsak Officer",
    "email": "admin001@dome.tu.ac.th",
    "organization": "กองเทคโนโลยีสารสนเทศ",
    "department": "ส่วนกลาง",
    "role": "admin",
}

TU_EMPLOYEE_NO_ROLE = {
    "status": True,
    "message": "Success",
    "type": "employee",
    "username": "techx",  # ต้องขึ้นต้นด้วย 'tech' เพื่อเข้า fallback branch
    "tu_status": "ปกติ",
    "displayname_th": "ช่าง ไม่มี role",
    "displayname_en": "Tech No Role",
    "email": "techx@staff.tu.ac.th",
    "department": "งานบริการเทคนิค",
    "organization": "สำนักงานอาคารสถานที่",
    # ไม่มี 'role'
}

TU_FAIL_INVALID = {
    "status": False,
    "message": "Invalid username or password",
}

TU_ERROR_EXCEPTION = {
    "status": False,
    "message": "Exception occurred",
}


# ---------- Helper Mixin for patching TU API ----------
class PatchTUMixin:
    def _patch_tu_verify(self, return_value):
        return patch(
            "authentication.utils.mock_tu_api.mock_tu_verify",
            return_value=return_value,
        )


# ---------- get_client_ip ----------
class TestGetClientIP(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_get_client_ip_from_x_forwarded_for(self):
        """
        กรณีมี HTTP_X_FORWARDED_FOR →
        ต้องดึง IP ตัวแรกก่อนคอมม่า
        """
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "1.2.3.4, 5.6.7.8"

        ip = get_client_ip(request)
        self.assertEqual(ip, "1.2.3.4")


# ---------- Login Page (GET) ----------
class TestLoginPageRender(TestCase):
    def test_get_login_page_anonymous(self):
        url = reverse("authentication:login")
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "username")
        self.assertContains(res, "password")

    @patch("authentication.views.redirect")
    def test_get_login_page_authenticated_admin_redirects_analytics_dashboard(
        self, mock_redirect
    ):
        """
        ผู้ใช้ role=admin เรียก /login →
        view ต้องเรียก redirect('analytics:dashboard')
        """
        user = User.objects.create_user(
            username="admin",
            password="x12345x",
            role="admin",
        )
        self.client.force_login(user)

        mock_redirect.return_value = HttpResponseRedirect("/dummy-admin")

        res = self.client.get(reverse("authentication:login"))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, "/dummy-admin")

        mock_redirect.assert_called_once_with("analytics:dashboard")

    def test_get_login_page_authenticated_technician_redirects_job_list(self):
        user = User.objects.create_user(
            username="tech",
            password="x12345x",
            role="technician",
        )
        self.client.force_login(user)

        res = self.client.get(reverse("authentication:login"))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("technician:job_list"))

    def test_get_login_page_authenticated_user_redirects_map(self):
        user = User.objects.create_user(
            username="student",
            password="x12345x",
            role="user",
        )
        self.client.force_login(user)

        res = self.client.get(reverse("authentication:login"))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("dashboard:map"))


# ---------- Local Login (POST) ----------
class TestLocalLoginFlow(TestCase):
    def setUp(self):
        self.url = reverse("authentication:login")
        self.user_admin = User.objects.create_user(
            username="admin",
            password="admin123",
            role="admin",
        )
        self.user_tech = User.objects.create_user(
            username="tech",
            password="tech123",
            role="technician",
        )
        self.user_normal = User.objects.create_user(
            username="user",
            password="user123",
            role="user",
        )

    @patch("authentication.views.redirect")
    def test_post_local_login_success_admin_redirects_dashboard_summary(
        self, mock_redirect
    ):
        """
        Local login + role=admin →
        view ต้องเรียก redirect('dashboard:summary')
        (patch redirect เพื่อไม่ต้องมี URL นี้จริง ๆ ใน project)
        """
        mock_redirect.return_value = HttpResponseRedirect("/dummy-admin")

        res = self.client.post(
            self.url,
            {
                "username": "admin",
                "password": "admin123",
                "login_type": "local",
            },
        )

        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, "/dummy-admin")
        mock_redirect.assert_called_once_with("dashboard:summary")

    def test_post_local_login_success_technician_redirects_job_list(self):
        res = self.client.post(
            self.url,
            {
                "username": "tech",
                "password": "tech123",
                "login_type": "local",
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("technician:job_list"))

    def test_post_local_login_success_user_redirects_dashboard_map(self):
        res = self.client.post(
            self.url,
            {
                "username": "user",
                "password": "user123",
                "login_type": "local",
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("dashboard:map"))

    def test_post_local_login_invalid_credentials_shows_error(self):
        res = self.client.post(
            self.url,
            {
                "username": "user",
                "password": "wrongpass",
                "login_type": "local",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

    def test_post_local_login_missing_login_type_default_local(self):
        """
        ถ้าไม่ได้ส่ง login_type มา →
        view ควรใช้ local เป็น default
        """
        res = self.client.post(
            self.url,
            {
                "username": "user",
                "password": "user123",
                # no login_type
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("dashboard:map"))


# ---------- TU API Login (POST) ----------
class TestTUAPILoginFlow(PatchTUMixin, TestCase):
    @patch("authentication.views.redirect")
    def test_tu_api_success_with_role_admin_redirects_analytics_dashboard(
        self, mock_redirect
    ):
        """
        TU API success + result['role']='admin'
        → role=admin + redirect('analytics:dashboard')
        """
        mock_redirect.return_value = HttpResponseRedirect("/dummy-admin")

        with self._patch_tu_verify(TU_SUCCESS_ADMIN):
            res = self.client.post(
                reverse("authentication:login"),
                {
                    "username": "admin001",
                    "password": "adminpass",
                    "login_type": "tu_api",
                },
            )

        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, "/dummy-admin")
        mock_redirect.assert_called_once_with("analytics:dashboard")

        user = User.objects.get(username="admin001")
        self.assertEqual(user.role, "admin")
        if hasattr(user, "auth_provider"):
            self.assertEqual(user.auth_provider, "TU_API")

    def test_tu_api_success_student_role_user_redirects_to_map(self):
        with self._patch_tu_verify(TU_SUCCESS_STUDENT):
            res = self.client.post(
                reverse("authentication:login"),
                {
                    "username": "student001",
                    "password": "student123",
                    "login_type": "tu_api",
                },
            )

        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("dashboard:map"))

        user = User.objects.get(username="student001")
        self.assertEqual(user.role, "user")
        if hasattr(user, "auth_provider"):
            self.assertEqual(user.auth_provider, "TU_API")

    def test_tu_api_fail_invalid_credentials_shows_message(self):
        """
        TU API ตอบกลับ status=False →
        ควร render หน้า login เดิม และแสดงข้อความ error
        """
        with self._patch_tu_verify(TU_FAIL_INVALID):
            res = self.client.post(
                reverse("authentication:login"),
                {
                    "username": "wronguser",
                    "password": "wrongpass",
                    "login_type": "tu_api",
                },
            )

        self.assertEqual(res.status_code, 200)
        # ตาม view: ใช้ข้อความ 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง (TU API)'
        self.assertContains(res, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง (TU API)")

    def test_tu_api_exception_dict_shows_same_error_message(self):
        """
        ถ้า mock_tu_verify คืน dict สถานะ False (เช่นจาก error ภายใน) →
        ควรแสดงข้อความ error เดียวกับกรณี invalid
        """
        with self._patch_tu_verify(TU_ERROR_EXCEPTION):
            res = self.client.post(
                reverse("authentication:login"),
                {
                    "username": "exception",
                    "password": "pass",
                    "login_type": "tu_api",
                },
            )

        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง (TU API)")

    def test_tu_api_employee_without_role_falls_back_to_technician(self):
        """
        กรณี TU API ตอบเป็น employee แต่ไม่มี 'role' →
        username ขึ้นต้นด้วย 'tech' → ต้องตั้ง role='technician'
        และ redirect ไป technician:job_list
        """
        with self._patch_tu_verify(TU_EMPLOYEE_NO_ROLE):
            res = self.client.post(
                reverse("authentication:login"),
                {
                    "username": "techx",
                    "password": "anypass",
                    "login_type": "tu_api",
                },
            )

        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("technician:job_list"))

        user = User.objects.get(username="techx")
        self.assertEqual(user.role, "technician")
        self.assertEqual(user.organization, "สำนักงานอาคารสถานที่")
        self.assertEqual(user.department, "งานบริการเทคนิค")


# ---------- Logout ----------
class TestLogoutView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user",
            password="user123",
            role="user",
        )

    def test_logout_redirects_to_login_and_session_cleared(self):
        self.client.force_login(self.user)
        url = reverse("authentication:logout")
        res = self.client.get(url)

        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("authentication:login"))

        # หลัง logout แล้วไปหน้า protected → ต้องโดน redirect login
        res2 = self.client.get(reverse("dashboard:map"))
        self.assertEqual(res2.status_code, 302)
        self.assertIn("login", res2.url)

    def test_logout_anonymous_still_redirects_login_with_no_cache_headers(self):
        """
        ถ้ายังไม่ล็อกอินแล้วเรียก /logout →
        ก็ redirect login พร้อม header no-cache
        """
        url = reverse("authentication:logout")
        res = self.client.get(url)

        self.assertEqual(res.status_code, 302)
        self.assertEqual(
            res.headers.get("Location"), reverse("authentication:login")
        )
        self.assertEqual(
            res.headers.get("Cache-Control"),
            "no-cache, no-store, must-revalidate, private",
        )
        self.assertEqual(res.headers.get("Pragma"), "no-cache")
        self.assertEqual(res.headers.get("Expires"), "0")


# ---------- LoginLog creation ----------
class TestLoginLogCreation(PatchTUMixin, TestCase):
    def setUp(self):
        self.url = reverse("authentication:login")
        self.user = User.objects.create_user(
            username="user",
            password="user123",
            role="user",
        )

    def test_login_creates_loginlog_entry_local(self):
        """
        ทุกครั้งที่ login สำเร็จด้วย local →
        ต้องมีการสร้าง LoginLog (อิงจากฟิลด์ username เพราะไม่มี FK user)
        """
        res = self.client.post(
            self.url,
            {
                "username": "user",
                "password": "user123",
                "login_type": "local",
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("dashboard:map"))

        logs = LoginLog.objects.filter(username=self.user.username)
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.login_method, "LOCAL")
        self.assertEqual(log.status, "SUCCESS")
        self.assertIsNotNone(log.ip_address)

    def test_tu_api_login_creates_loginlog_entry(self):
        """
        Login ผ่าน TU API สำเร็จ →
        สร้าง LoginLog ด้วย login_method='TU_API'
        """
        with self._patch_tu_verify(TU_SUCCESS_STUDENT):
            res = self.client.post(
                self.url,
                {
                    "username": "student001",
                    "password": "student123",
                    "login_type": "tu_api",
                },
            )

        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("dashboard:map"))

        logs = LoginLog.objects.filter(username="student001")
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.login_method, "TU_API")
        self.assertEqual(log.status, "SUCCESS")
        self.assertIsNotNone(log.ip_address)


# ---------- Messages test ----------
class TestLoginMessages(PatchTUMixin, TestCase):
    def setUp(self):
        self.url = reverse("authentication:login")
        self.user = User.objects.create_user(
            username="user",
            password="user123",
            role="user",
        )

    def test_invalid_local_login_shows_message(self):
        res = self.client.post(
            self.url,
            {
                "username": "user",
                "password": "wrongpass",
                "login_type": "local",
            },
        )
        self.assertEqual(res.status_code, 200)
        messages = list(get_messages(res.wsgi_request))
        self.assertTrue(
            any("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง" in str(m) for m in messages)
        )

    def test_tu_api_fail_shows_message(self):
        with self._patch_tu_verify(TU_FAIL_INVALID):
            res = self.client.post(
                self.url,
                {
                    "username": "nouser",
                    "password": "nopass",
                    "login_type": "tu_api",
                },
            )

        self.assertEqual(res.status_code, 200)
        messages = list(get_messages(res.wsgi_request))
        self.assertTrue(
            any("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง (TU API)" in str(m) for m in messages)
        )
