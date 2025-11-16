from django.test import TestCase
from django.test.utils import override_settings
from authentication.utils import mock_tu_api
from unittest.mock import patch, MagicMock
import requests


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
    
    def test_mock_tu_departments_filter_org_name_en(self):
        """filter ด้วย org_nam_en → ต้องกรองจาก org_name_en ภาษาอังกฤษให้ถูก"""
        res = mock_tu_api.mock_tu_departments(
            org_nam_en="Building Management Office"
        )
        self.assertTrue(res["status"])
        # ทุกแถวควรมีคำว่า Building Management Office ใน org_name_en
        self.assertTrue(
            all(
                "Building Management Office" in d["org_name_en"]
                for d in res["data"]
            )
        )

    def test_mock_tu_employee_info_filter_displayname_en(self):
        """filter ด้วย displayname_en → ใช้ชื่อภาษาอังกฤษ"""
        res = mock_tu_api.mock_tu_employee_info(displayname_en="Admin Test")
        self.assertTrue(res["status"])
        self.assertGreaterEqual(len(res["data"]), 1)
        self.assertTrue(
            all("Admin Test" in e["displayname_en"] for e in res["data"])
        )

    def test_mock_tu_employee_info_no_match_returns_false(self):
        """กรณี filter แล้วไม่เจอเลย → status=False, data=[], message='No data found'"""
        res = mock_tu_api.mock_tu_employee_info(username="no_such_user_xyz")
        self.assertFalse(res["status"])
        self.assertEqual(res["data"], [])
        self.assertEqual(res["message"], "No data found")

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

class TestMockTuAPIFullBranches(TestCase):

    def _set_api(self):
        return override_settings(
            TU_API_BASE_URL="https://restapi.tu.ac.th",
            TU_APPLICATION_KEY="TESTKEY"
        )

    @patch("requests.post")
    def test_real_api_400_returns_error(self, mock_post):
        """กรณี API ตอบ 400 → mock_tu_verify ต้องคืน status=False"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid request"
        mock_post.return_value = mock_response

        with self._set_api():
            res = mock_tu_api.mock_tu_verify("nouser", "nopass")

        self.assertFalse(res["status"])
        self.assertIn("Real API returned 400", res["message"])

    @patch("requests.post")
    def test_real_api_500_fallback_to_verify2(self, mock_post):
        """API verify แรก 500 → ต้อง fallback verify2"""
        first = MagicMock()
        first.status_code = 500
        first.text = "Server error"

        second = MagicMock()
        second.status_code = 200
        second.json.return_value = {"status": True, "message": "fallback ok"}

        mock_post.side_effect = [first, second]

        with self._set_api():
            res = mock_tu_api.mock_tu_verify("realuser", "pass")

        self.assertTrue(res["status"])
        self.assertEqual(res["message"], "fallback ok")
        self.assertEqual(mock_post.call_count, 2)

    @patch("requests.post")
    def test_real_api_json_decode_error(self, mock_post):
        """API 200 แต่ JSON เสีย → ปัจจุบันโค้ดจริงปล่อย ValueError ออกมา"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("bad json")
        mock_response.text = "not a json"
        mock_post.return_value = mock_response

        # โค้ดจริงไม่ได้จับ ValueError → เราคาดหวังให้มัน raise
        with self._set_api(), self.assertRaises(ValueError):
            mock_tu_api.mock_tu_verify("realbad", "pass")


    @patch("requests.post")
    def test_real_api_request_exception(self, mock_post):
        """requests.post โยน exception"""
        mock_post.side_effect = requests.exceptions.RequestException("boom")

        with self._set_api():
            res = mock_tu_api.mock_tu_verify("exception", "pass")

        self.assertFalse(res["status"])
        self.assertIn("API call failed", res["message"])

    @patch("requests.post")
    def test_api_base_url_missing_slash(self, mock_post):
        """base URL ผิดรูปแบบ → ต้องจับ error"""
        with override_settings(
            TU_API_BASE_URL="https://restapi.tu.ac.th///",
            TU_APPLICATION_KEY="KKK"
        ):
            mock_post.side_effect = requests.RequestException("URL Error")

            res = mock_tu_api.mock_tu_verify("user", "pass")

        self.assertFalse(res["status"])
        self.assertIn("API call failed", res["message"])

    def test_real_api_empty_username_password_returns_missing_app_key(self):
        """
        username=None/password=None และไม่มี APP_KEY
        → ต้องไม่เรียก TU API จริง และคืน status=False พร้อมข้อความ Missing TU_APPLICATION_KEY
        """
        with override_settings(
            TU_API_BASE_URL="https://restapi.tu.ac.th",
            TU_APPLICATION_KEY=""  # ไม่มี key เลย
        ):
            res = mock_tu_api.mock_tu_verify(None, None)

        self.assertFalse(res["status"])
        self.assertIn("Missing TU_APPLICATION_KEY", res["message"])

   
