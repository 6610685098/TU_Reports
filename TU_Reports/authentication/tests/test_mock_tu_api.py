from django.test import TestCase
from django.test.utils import override_settings
from authentication.utils import mock_tu_api

class TestMockTUAPIBasic(TestCase):
    def test_valid_user(self):
        res = mock_tu_api.mock_tu_verify("student001", "student123")
        self.assertTrue(res["status"])
        self.assertEqual(res.get("username"), "student001")

    def test_invalid_user(self):
        res = mock_tu_api.mock_tu_verify("unknown_user_xyz", "123")
        self.assertFalse(res["status"])
        msg = str(res.get("message", "")).lower()
        self.assertTrue("invalid" in msg or "400" in msg)

    def test_wrong_password_logs_warning(self):
        with self.assertLogs("authentication.utils.mock_tu_api", level="WARNING"):
            res = mock_tu_api.mock_tu_verify("student001", "wrongpass")
        self.assertFalse(res["status"])
        msg = str(res.get("message", "")).lower()
        self.assertTrue("invalid" in msg or "400" in msg)

    def test_case_insensitive_username(self):
        res = mock_tu_api.mock_tu_verify("STUDENT001", "student123")
        self.assertFalse(res["status"])
        msg = str(res.get("message", "")).lower()
        self.assertTrue("invalid" in msg or "400" in msg)

    def test_empty_and_none_inputs(self):
        self.assertIn("status", mock_tu_api.mock_tu_verify("", ""))
        self.assertIn("status", mock_tu_api.mock_tu_verify(None, None))


class TestMockTUAPILoggingAndSettings(TestCase):
    def test_debug_true_logs_unknown_user_info(self):
        with override_settings(DEBUG=True):
            with self.assertLogs("authentication.utils.mock_tu_api", level="INFO"):
                res = mock_tu_api.mock_tu_verify("unknown_user", "xxx")
        self.assertIn("status", res)

    def test_enabled_without_app_key_is_safe(self):
        with override_settings(TU_API_BASE_URL="https://example.test", TU_APPLICATION_KEY=""):
            res = mock_tu_api.mock_tu_verify("student001", "student123")
        self.assertIn("status", res)
        if res["status"]:
            self.assertEqual(res.get("username"), "student001")
            self.assertIn("email", res)
        else:
            self.assertTrue(str(res.get("message", "")))

    def test_error_user_path_logs_info(self):
        with self.assertLogs("authentication.utils.mock_tu_api", level="INFO"):
            res = mock_tu_api.mock_tu_verify("error_user", "anything")
        self.assertIn("status", res)


class TestMockTuOtherHelpers(TestCase):
    def test_mock_tu_log_auth_filters_and_limit(self):
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
        res_all = mock_tu_api.mock_tu_departments()
        self.assertTrue(res_all["status"])

        res_filter = mock_tu_api.mock_tu_departments(org_code="1001", dep_code="1001-01")
        self.assertTrue(res_filter["status"])
        self.assertTrue(all(d.get("org_code") == "1001" for d in res_filter["data"]))
        self.assertTrue(all(d.get("dep_code") == "1001-01" for d in res_filter["data"]))

        res_name = mock_tu_api.mock_tu_departments(org_nam_th="อาคาร", dep_name="ซ่อม")
        self.assertTrue(res_name["status"])

    def test_mock_tu_employee_info_filters(self):
        res_all = mock_tu_api.mock_tu_employee_info()
        self.assertTrue(res_all["status"])
        self.assertGreaterEqual(len(res_all["data"]), 1)

        by_user = mock_tu_api.mock_tu_employee_info(username="tech001")
        self.assertTrue(all(p["userName"] == "tech001" for p in by_user["data"]))

        by_th = mock_tu_api.mock_tu_employee_info(displayname_th="ช่าง")
        self.assertTrue(len(by_th["data"]) >= 1)

        by_org = mock_tu_api.mock_tu_employee_info(organization="สำนักงานอาคารสถานที่")
        self.assertTrue(all("สำนักงานอาคารสถานที่" in p["organization"] for p in by_org["data"]))
