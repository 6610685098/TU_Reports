from django.test import TestCase
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from unittest.mock import patch

from authentication.models import LoginLog

User = get_user_model()


# ---------- Mock TU API responses ----------
TU_SUCCESS_STUDENT = {
    "status": True,
    "message": "Success",
    "type": "student",
    "username": "student001",
    "displayname_th": "สมชาย ใจดี",
    "displayname_en": "Somchai Jaidee",
    "email": "student001@tu.ac.th",
    "tu_status": "ปกติ",
    "faculty": "วิศวกรรมศาสตร์",
    "department": "วิศวกรรมคอมพิวเตอร์",
}

TU_SUCCESS_ADMIN = {
    **TU_SUCCESS_STUDENT,
    "username": "admin001",
    "email": "admin001@tu.ac.th",
    "role": "admin",
}

TU_SUCCESS_EMPLOYEE_NO_ROLE = {
    "status": True,
    "message": "Success",
    "type": "employee",
    "username": "tech1",
    "displayname_th": "ช่างหนึ่ง",
    "displayname_en": "Technician One",
    "email": "tech1@tu.ac.th",
    "tu_status": "ปกติ",
    "organization": "Maintenance",
    "department": "Maintenance Dept.",
}

TU_FAIL = {"status": False, "message": "Invalid credential"}


# ---------- Helper สำหรับ patch mock_tu_verify ----------
class PatchTUMixin:
    def _patch_tu_verify(self, return_value):
        """
        views.py import mock_tu_verify จาก authentication.utils.mock_tu_api
        ดังนั้น patch ที่จุดนั้นได้เลย
        """
        return patch(
            "authentication.utils.mock_tu_api.mock_tu_verify",
            return_value=return_value,
        )


# ---------- Login Page (GET) ----------
class TestLoginPageRender(TestCase):
    def test_get_login_page_anonymous(self):
        """GET /login โดยยังไม่ล็อกอิน → status 200 และมีฟอร์ม username/password"""
        url = reverse("authentication:login")
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "username")
        self.assertContains(res, "password")

    @patch("authentication.views.redirect")
    def test_get_login_page_authenticated_admin_redirects_summary(
        self, mock_redirect
    ):
        """
        ผู้ใช้ role=admin เรียก /login →
        view ต้องเรียก redirect('dashboard:summary')
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

        mock_redirect.assert_called_once_with("dashboard:summary")

    def test_get_login_page_authenticated_technician_redirects_job_list(self):
        """ผู้ใช้ role=technician เรียก /login → redirect ไป technician:job_list"""
        user = User.objects.create_user(
            username="techuser",
            password="x12345x",
            role="technician",
        )
        self.client.force_login(user)

        res = self.client.get(reverse("authentication:login"))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers.get("Location"), reverse("technician:job_list"))

    def test_get_login_page_authenticated_normal_user_redirects_map(self):
        """ผู้ใช้ role=user เรียก /login → redirect ไป dashboard:map"""
        user = User.objects.create_user(
            username="normal",
            password="x12345x",
            role="user",
        )
        self.client.force_login(user)

        res = self.client.get(reverse("authentication:login"))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers.get("Location"), reverse("dashboard:map"))


# ---------- Local login ----------
class TestLocalLoginFlow(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="localuser",
            password="localpass",
            role="user",
        )

    def test_local_login_success_redirects_to_dashboard_map_and_logs(self):
        """Local login สำเร็จ → redirect dashboard:map และสร้าง LoginLog SUCCESS/LOCAL"""
        url = reverse("authentication:login")
        res = self.client.post(
            url,
            {
                "username": "localuser",
                "password": "localpass",
                "login_type": "local",
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers.get("Location"), reverse("dashboard:map"))

        log = LoginLog.objects.latest("created_at")
        self.assertEqual(log.username, "localuser")
        self.assertEqual(log.status, "SUCCESS")
        self.assertEqual(log.login_method, "LOCAL")

        messages = list(get_messages(res.wsgi_request))
        self.assertTrue(any("ยินดีต้อนรับ" in str(m) for m in messages))

    def test_local_login_fail_stays_on_login_and_logs_failed(self):
        """Local login รหัสผิด → อยู่หน้าเดิม และ LoginLog เป็น FAILED/LOCAL"""
        url = reverse("authentication:login")
        res = self.client.post(
            url,
            {
                "username": "localuser",
                "password": "WRONG",
                "login_type": "local",
            },
        )
        self.assertEqual(res.status_code, 200)

        log = LoginLog.objects.latest("created_at")
        self.assertEqual(log.username, "localuser")
        self.assertEqual(log.status, "FAILED")
        self.assertEqual(log.login_method, "LOCAL")

        messages = list(get_messages(res.wsgi_request))
        self.assertTrue(any("ไม่ถูกต้อง" in str(m) for m in messages))

    @patch("authentication.views.redirect")
    def test_local_login_admin_redirects_summary(self, mock_redirect):
        """Local login + role=admin → เรียก redirect('dashboard:summary')"""
        admin_user = User.objects.create_user(
            username="localadmin",
            password="adminpass",
            role="admin",
        )
        mock_redirect.return_value = HttpResponseRedirect("/dummy-admin")

        res = self.client.post(
            reverse("authentication:login"),
            {
                "username": "localadmin",
                "password": "adminpass",
                "login_type": "local",
            },
        )

        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, "/dummy-admin")
        mock_redirect.assert_called_once_with("dashboard:summary")

        # ยืนยันว่า auth ผ่านจริง
        logged = LoginLog.objects.latest("created_at")
        self.assertEqual(logged.username, "localadmin")
        self.assertEqual(logged.status, "SUCCESS")
        self.assertEqual(logged.login_method, "LOCAL")

    @patch("authentication.views.redirect")
    def test_local_login_technician_redirects_job_list(self, mock_redirect):
        """Local login + role=technician → เรียก redirect('technician:job_list')"""
        tech_user = User.objects.create_user(
            username="localtech",
            password="techpass",
            role="technician",
        )
        mock_redirect.return_value = HttpResponseRedirect("/dummy-tech")

        res = self.client.post(
            reverse("authentication:login"),
            {
                "username": "localtech",
                "password": "techpass",
                "login_type": "local",
            },
        )

        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, "/dummy-tech")
        mock_redirect.assert_called_once_with("technician:job_list")

        logged = LoginLog.objects.latest("created_at")
        self.assertEqual(logged.username, "localtech")
        self.assertEqual(logged.status, "SUCCESS")
        self.assertEqual(logged.login_method, "LOCAL")


# ---------- TU API login ----------
class TestTUAPILoginFlow(PatchTUMixin, TestCase):
    @patch("authentication.views.redirect")
    def test_tu_api_success_with_role_admin_redirects_summary(
        self, mock_redirect
    ):
        """TU API success + result['role']='admin' → role=admin + redirect('dashboard:summary')"""
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
        mock_redirect.assert_called_once_with("dashboard:summary")

        user = User.objects.get(username="admin001")
        self.assertEqual(user.role, "admin")
        if hasattr(user, "auth_provider"):
            self.assertEqual(user.auth_provider, "TU_API")

    def test_tu_api_success_student_role_user_redirects_to_map(self):
        """TU API success แบบ student ทั่วไป → role=user → redirect dashboard:map"""
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
        self.assertEqual(res.headers.get("Location"), reverse("dashboard:map"))

        user = User.objects.get(username="student001")
        self.assertEqual(user.role, "user")
        if hasattr(user, "displayname_th"):
            self.assertEqual(
                user.displayname_th, TU_SUCCESS_STUDENT["displayname_th"]
            )

    def test_tu_api_success_employee_tech_prefix_redirects_job_list(self):
        """TU API success (employee) + username ขึ้นต้นด้วย 'tech' → role=technician → redirect technician:job_list"""
        with self._patch_tu_verify(TU_SUCCESS_EMPLOYEE_NO_ROLE):
            res = self.client.post(
                reverse("authentication:login"),
                {
                    "username": "tech1",
                    "password": "techpass",
                    "login_type": "tu_api",
                },
            )

        self.assertEqual(res.status_code, 302)
        self.assertEqual(
            res.headers.get("Location"), reverse("technician:job_list")
        )

        user = User.objects.get(username="tech1")
        self.assertEqual(user.role, "technician")
        if hasattr(user, "organization"):
            self.assertEqual(
                user.organization, TU_SUCCESS_EMPLOYEE_NO_ROLE["organization"]
            )

    def test_tu_api_fail_stays_on_login_and_logs_failed(self):
        """TU API ล้มเหลว → อยู่หน้าเดิม 200 และ LoginLog FAILED/TU_API"""
        with self._patch_tu_verify(TU_FAIL):
            res = self.client.post(
                reverse("authentication:login"),
                {
                    "username": "student001",
                    "password": "Wrong",
                    "login_type": "tu_api",
                },
            )

        self.assertEqual(res.status_code, 200)

        log = LoginLog.objects.latest("created_at")
        self.assertEqual(log.username, "student001")
        self.assertEqual(log.status, "FAILED")
        self.assertEqual(log.login_method, "TU_API")

        messages = list(get_messages(res.wsgi_request))
        self.assertTrue(
            any("TU API" in str(m) or "ไม่ถูกต้อง" in str(m) for m in messages)
        )


# ---------- Edge cases & get_client_ip ----------
class TestGetClientIPAndEdgeCases(TestCase):
    def test_post_without_login_type_treated_as_local_failed(self):
        """
        ถ้าไม่ส่ง login_type →
        view จะถือว่าเป็น local login และเมื่อ credential ไม่ถูกต้อง → FAILED/LOCAL
        """
        res = self.client.post(
            reverse("authentication:login"),
            {
                "username": "someone",
                "password": "pass",
            },
        )
        self.assertEqual(res.status_code, 200)

        log = LoginLog.objects.latest("created_at")
        self.assertEqual(log.username, "someone")
        self.assertEqual(log.status, "FAILED")
        self.assertEqual(log.login_method, "LOCAL")

    def test_get_client_ip_prefers_x_forwarded_for(self):
        """มี header X-Forwarded-For → ip_address ใน LoginLog ต้องเป็นค่าแรก"""
        User.objects.create_user(
            username="ipuser", password="ippass", role="user"
        )
        res = self.client.post(
            reverse("authentication:login"),
            {
                "username": "ipuser",
                "password": "ippass",
                "login_type": "local",
            },
            HTTP_X_FORWARDED_FOR="1.2.3.4, 5.6.7.8",
        )
        self.assertEqual(res.status_code, 302)

        log = LoginLog.objects.latest("created_at")
        self.assertEqual(log.ip_address, "1.2.3.4")

    def test_get_client_ip_uses_remote_addr_when_no_forwarded_for(self):
        """ถ้าไม่มี X-Forwarded-For → ใช้ REMOTE_ADDR เป็น ip_address"""
        User.objects.create_user(
            username="ipuser2", password="ippass2", role="user"
        )
        res = self.client.post(
            reverse("authentication:login"),
            {
                "username": "ipuser2",
                "password": "ippass2",
                "login_type": "local",
            },
            REMOTE_ADDR="9.8.7.6",
        )
        self.assertEqual(res.status_code, 302)

        log = LoginLog.objects.latest("created_at")
        self.assertEqual(log.ip_address, "9.8.7.6")


# ---------- Logout ----------
class TestLogoutView(TestCase):
    def test_logout_authenticated_user_redirects_to_login_with_cache_headers(
        self,
    ):
        """logout → redirect login และตั้ง header ป้องกัน cache"""
        user = User.objects.create_user(
            username="logoutuser", password="x12345x"
        )
        self.client.force_login(user)

        res = self.client.get(reverse("authentication:logout"))
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

    def test_logout_anonymous_still_redirects_login(self):
        """ถ้ายังไม่ล็อกอินแล้วเรียก /logout → ก็ redirect login พร้อม header เดิม"""
        res = self.client.get(reverse("authentication:logout"))
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
