from django.test import TestCase
from django.test.utils import override_settings
from authentication.utils import mock_tu_api


# ---------- ทดสอบฟังก์ชันหลัก mock_tu_verify ----------
class TestMockTUAPIBasic(TestCase):
    def test_valid_user(self):
        """ล็อกอินด้วย mock user ที่ถูกต้อง → คืนค่า status=True"""
        res = mock_tu_api.mock_tu_verify("student001", "student123")
        self.assertTrue(res["status"])

    def test_invalid_user(self):
        """username ไม่มีใน MOCK_USERS → ต้อง status=False"""
        res = mock_tu_api.mock_tu_verify("unknown_user_xyz", "123")
        self.assertFalse(res["status"])

    def test_wrong_password_logs_warning(self):
        """รหัสผ่านผิด → ต้องคืน status=False และ log ระดับ WARNING"""
        with self.assertLogs("authentication.utils.mock_tu_api", level="WARNING"):
            res = mock_tu_api.mock_tu_verify("student001", "wrongpass")
        self.assertFalse(res["status"])

    def test_case_insensitive_username(self):
        """ทดสอบ username ตัวใหญ่/เล็กต่างกัน → ไม่ผ่าน"""
        res = mock_tu_api.mock_tu_verify("STUDENT001", "student123")
        self.assertFalse(res["status"])

    def test_empty_and_none_inputs(self):
        """กรณีช่องว่างหรือ None → ต้อง handle ได้ไม่ error"""
        self.assertIn("status", mock_tu_api.mock_tu_verify("", ""))
        self.assertIn("status", mock_tu_api.mock_tu_verify(None, None))


# ---------- ทดสอบ logging และ settings ----------
class TestMockTUAPILoggingAndSettings(TestCase):
    def test_debug_true_logs_unknown_user_info(self):
        """เปิด DEBUG=True → ต้อง log INFO เมื่อเจอ user ไม่รู้จัก"""
        with override_settings(DEBUG=True):
            with self.assertLogs("authentication.utils.mock_tu_api", level="INFO"):
                res = mock_tu_api.mock_tu_verify("unknown_user", "xxx")
        self.assertIn("status", res)

    def test_enabled_without_app_key_is_safe(self):
        """เปิด TU_API_ENABLED แต่ไม่มี APP_KEY → ต้องไม่ crash"""
        with override_settings(TU_API_BASE_URL="https://example.test", TU_APPLICATION_KEY=""):
            res = mock_tu_api.mock_tu_verify("student001", "student123")
        self.assertIn("status", res)

    def test_error_user_path_logs_info(self):
        """กรณีจำลอง network error หรือ error path → ต้อง log INFO"""
        with self.assertLogs("authentication.utils.mock_tu_api", level="INFO"):
            res = mock_tu_api.mock_tu_verify("error_user", "anything")
        self.assertIn("status", res)


# ---------- ทดสอบ helper function อื่น ๆ ----------
class TestMockTuOtherHelpers(TestCase):
    def test_mock_tu_log_auth_filters_and_limit(self):
        """ทดสอบระบบบันทึก log: filter ด้วย status, username, และจำกัด record"""
        logs_all = mock_tu_api.mock_tu_log_auth()
        self.assertGreaterEqual(len(logs_all), 1)

        logs_true = mock_tu_api.mock_tu_log_auth(status="true")
        self.assertTrue(all("TRUE" in l["Status"] for l in logs_true))

        logs_false = mock_tu_api.mock_tu_log_auth(status="false")
        self.assertTrue(all("FALSE" in l["Status"] for l in logs_false))

        logs_user = mock_tu_api.mock_tu_log_auth(status="true", username="student001")
        self.assertTrue(all("student001" in l["Description"] for l in logs_user))

        huge = mock_tu_api.mock_tu_log_auth(record=20000)
        self.assertLessEqual(len(huge), 10000)

    def test_mock_tu_departments_filters(self):
        """ทดสอบฟังก์ชัน mock_tu_departments() — filter org/dep/name"""
        res_all = mock_tu_api.mock_tu_departments()
        self.assertTrue(res_all["status"])

        res_filter = mock_tu_api.mock_tu_departments(org_code="1001", dep_code="1001-01")
        self.assertTrue(all(d.get("org_code") == "1001" for d in res_filter["data"]))

        res_name = mock_tu_api.mock_tu_departments(org_nam_th="อาคาร", dep_name="ซ่อม")
        self.assertTrue(res_name["status"])

    def test_mock_tu_employee_info_filters(self):
        """ทดสอบ mock_tu_employee_info() — filter username, displayname, org"""
        res_all = mock_tu_api.mock_tu_employee_info()
        self.assertTrue(res_all["status"])

        by_user = mock_tu_api.mock_tu_employee_info(username="tech001")
        self.assertTrue(all(p["userName"] == "tech001" for p in by_user["data"]))

        by_th = mock_tu_api.mock_tu_employee_info(displayname_th="ช่าง")
        self.assertTrue(len(by_th["data"]) >= 1)

        by_org = mock_tu_api.mock_tu_employee_info(organization="สำนักงานอาคารสถานที่")
        self.assertTrue(all("สำนักงานอาคารสถานที่" in p["organization"] for p in by_org["data"]))
