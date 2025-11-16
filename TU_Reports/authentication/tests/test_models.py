from django.test import TestCase
from django.contrib.auth import get_user_model
from authentication.models import LoginLog

User = get_user_model()


class TestUserModel(TestCase):
    def test_create_user_and_get_display_name(self):
        """สร้างผู้ใช้ที่มีชื่อภาษาไทย → get_display_name() ควรคืนชื่อไทย และ __str__ มี username"""
        u = User.objects.create_user(
            username="student001", password="x12345x", displayname_th="สมชาย ใจดี"
        )
        self.assertTrue(u.pk)
        self.assertEqual(u.get_display_name(), "สมชาย ใจดี")
        self.assertIn("student001", str(u))

    def test_get_display_name_fallback_to_username(self):
        """ไม่มี displayname_th → get_display_name() ควร fallback เป็น username"""
        u = User.objects.create_user(username="john", password="x")
        self.assertEqual(u.get_display_name(), "john")


class TestLoginLogModel(TestCase):
    def test_create_login_log(self):
        """บันทึก LoginLog ครบฟิลด์หลัก → บันทึกสำเร็จและ __str__ มี username"""
        log = LoginLog.objects.create(
            username="student001",
            description="Login Success via Local: student001",
            status="SUCCESS",
            login_method="LOCAL",
            ip_address="127.0.0.1",
            user_agent="pytest",
        )
        self.assertTrue(log.pk)
        self.assertIn("student001", str(log))
