from django.test import TestCase
from django.test.utils import override_settings
from unittest.mock import patch
import io
import contextlib
import runpy
import requests

from authentication.utils import mock_tu_api


# -------------------------
# Basic mock_tu_verify tests
# -------------------------
class TestMockTUAPIBasic(TestCase):
    def test_valid_student_user(self):
        """ล็อกอินด้วย mock user student001/student123 → status=True, ข้อมูลถูกต้อง"""
        res = mock_tu_api.mock_tu_verify("student001", "student123")
        self.assertIsInstance(res, dict)
        self.assertTrue(res.get("status"))
        self.assertEqual(res.get("username"), "student001")
        self.assertEqual(res.get("displayname_th"), "นักศึกษา ทดสอบ")

    def test_wrong_password_for_valid_user(self):
        """username ถูก แต่ password ผิด → status=False และ message บอก invalid"""
        res = mock_tu_api.mock_tu_verify("student001", "wrongpass")
        self.assertIsInstance(res, dict)
        self.assertFalse(res.get("status"))
        self.assertEqual(res.get("message"), "User or Password Invalid!")

    @override_settings(
        TU_API_BASE_URL="https://restapi.tu.ac.th",
        TU_APPLICATION_KEY=""
    )
    def test_unknown_user_without_app_key_returns_missing_key_error(self):
        """
        username ไม่มีใน MOCK_USERS และไม่มี TU_APPLICATION_KEY
        → ต้องได้ status=False + message มี 'Missing TU_APPLICATION_KEY'
        """
        res = mock_tu_api.mock_tu_verify("unknown_user_xyz", "123")
        self.assertIsInstance(res, dict)
        self.assertFalse(res.get("status"))
        self.assertIn("Missing TU_APPLICATION_KEY", res.get("message", ""))


# ---------------------------------------
# Ensure real API not called for mock user
# ---------------------------------------
class TestMockTUAPINoRealCallForMockUser(TestCase):
    @override_settings(
        TU_API_BASE_URL="https://restapi.tu.ac.th",
        TU_APPLICATION_KEY="DUMMY_KEY"
    )
    def test_mock_user_does_not_call_requests_post(self):
        """
        ถ้า username อยู่ใน MOCK_USERS → ฟังก์ชันต้องไม่เรียก requests.post เลย
        (เช็คโดย patch requests.post ตรง ๆ)
        """
        with patch("requests.post") as mock_post:
            res = mock_tu_api.mock_tu_verify("student001", "student123")

        self.assertTrue(res.get("status"))
        mock_post.assert_not_called()


# ---------------------------------------
# Network & real API branch coverage
# ---------------------------------------
class TestMockTUAPIRealCallBranches(TestCase):
    @override_settings(
        TU_API_BASE_URL="https://restapi.tu.ac.th",
        TU_APPLICATION_KEY="DUMMY_KEY"
    )
    def test_real_api_status_200_returns_json(self):
        """
        กรณี user ไม่อยู่ใน MOCK_USERS + status_code=200 →
        ต้อง return response.json() → ครอบบรรทัด 118, 120-121
        """
        class FakeResponse:
            status_code = 200
            text = '{"status": true, "msg": "ok"}'

            def json(self):
                return {"status": True, "msg": "ok"}

        with patch("requests.post", return_value=FakeResponse()) as mock_post:
            res = mock_tu_api.mock_tu_verify("realuser_ok", "pass")

        self.assertEqual(res, {"status": True, "msg": "ok"})
        self.assertEqual(mock_post.call_count, 1)

    @override_settings(
        TU_API_BASE_URL="https://restapi.tu.ac.th",
        TU_APPLICATION_KEY="DUMMY_KEY"
    )
    def test_real_api_status_404_uses_fallback_verify2(self):
        """
        status_code แรก=404 → ต้องเรียก fallback /verify2 แล้ว return json ของ response2
        → ครอบบรรทัด 122-128
        """
        class FakeResp404:
            status_code = 404
            text = "not found"

            def json(self):
                return {"status": False, "msg": "notfound"}

        class FakeResp200:
            status_code = 200
            text = '{"status": true, "msg": "fallback_ok"}'

            def json(self):
                return {"status": True, "msg": "fallback_ok"}

        with patch("requests.post", side_effect=[FakeResp404(), FakeResp200()]) as mock_post:
            res = mock_tu_api.mock_tu_verify("realuser_404", "pass")

        self.assertEqual(res, {"status": True, "msg": "fallback_ok"})
        self.assertEqual(mock_post.call_count, 2)

    @override_settings(
        TU_API_BASE_URL="https://restapi.tu.ac.th",
        TU_APPLICATION_KEY="DUMMY_KEY"
    )
    def test_real_api_other_status_returns_error_message(self):
        """
        status_code อื่น ๆ (เช่น 418) →
        ต้องคืน dict error 'Real API returned ...'
        → ครอบบรรทัด 129-130
        """
        class FakeResp418:
            status_code = 418
            text = "I'm a teapot"

            def json(self):
                return {"status": False, "msg": "teapot"}

        with patch("requests.post", return_value=FakeResp418()) as mock_post:
            res = mock_tu_api.mock_tu_verify("realuser_418", "pass")

        self.assertIsInstance(res, dict)
        self.assertFalse(res.get("status"))
        self.assertIn("Real API returned 418", res.get("message", ""))
        self.assertEqual(mock_post.call_count, 1)

    @override_settings(
        TU_API_BASE_URL="https://restapi.tu.ac.th",
        TU_APPLICATION_KEY="DUMMY_KEY"
    )
    def test_real_api_request_exception_returns_safe_response(self):
        """
        จำลองว่า requests.post โยน RequestException ตลอด (ทั้ง main และ fallback)
        → mock_tu_verify ต้อง handle แล้วคืน status=False + message มี 'API call failed'
        (ครอบ except branch 132-134)
        """
        def _raise_err(*args, **kwargs):
            raise requests.RequestException("URL Error")

        with patch("requests.post", side_effect=_raise_err) as mock_post:
            res = mock_tu_api.mock_tu_verify("realuser_err", "pass")

        self.assertIsInstance(res, dict)
        self.assertFalse(res.get("status"))
        self.assertIn("API call failed", res.get("message", ""))
        self.assertGreaterEqual(mock_post.call_count, 1)


# -------------------------
# mock_tu_log_auth tests
# -------------------------
class TestMockTUAPILogAuth(TestCase):
    def test_log_auth_default_returns_at_most_10(self):
        """
        mock_tu_log_auth() ปกติ → คืน list ยาวไม่เกิน record (default=10)
        """
        logs = mock_tu_api.mock_tu_log_auth()
        self.assertIsInstance(logs, list)
        self.assertGreater(len(logs), 0)
        self.assertLessEqual(len(logs), 10)

    def test_log_auth_filter_by_username(self):
        """
        filter ด้วย username='student001'
        → ทุก log ที่คืนมา ต้องมี 'student001' อยู่ใน Description
        """
        logs = mock_tu_api.mock_tu_log_auth(username="student001")
        self.assertIsInstance(logs, list)
        self.assertGreater(len(logs), 0)
        for log in logs:
            self.assertIn("student001", log["Description"])

    def test_log_auth_filter_by_status_true(self):
        """
        ส่ง status='true' → ต้อง filter ให้ Status มี 'TRUE' เท่านั้น
        → ครอบบรรทัด 184-185
        """
        logs = mock_tu_api.mock_tu_log_auth(status="true")
        self.assertIsInstance(logs, list)
        self.assertGreater(len(logs), 0)
        for log in logs:
            self.assertIn("TRUE", log["Status"])


# -------------------------
# mock_tu_departments tests
# -------------------------
class TestMockTUAPIDepartments(TestCase):
    def test_departments_basic_structure(self):
        """
        mock_tu_departments() → ต้องได้ dict มี status=True และ data เป็น list ของ department
        """
        res = mock_tu_api.mock_tu_departments()
        self.assertIsInstance(res, dict)
        self.assertTrue(res.get("status"))

        data = res.get("data")
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

        first = data[0]
        self.assertIn("org_code", first)
        self.assertIn("org_name_th", first)
        self.assertIn("org_name_en", first)
        self.assertIn("dep_code", first)
        self.assertIn("dep_name", first)

    def test_departments_filter_by_org_code(self):
        """
        filter ด้วย org_code='5030000' → ทุกตัวใน data ต้องมี org_code ตรงกัน
        """
        res = mock_tu_api.mock_tu_departments(org_code="5030000")
        data = res.get("data")
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        for d in data:
            self.assertEqual(d["org_code"], "5030000")

    def test_departments_filter_by_org_name_th(self):
        """
        filter ด้วย org_nam_th='สำนักงานอาคารสถานที่'
        → ครอบ branch บรรทัด 268
        """
        res = mock_tu_api.mock_tu_departments(org_nam_th="สำนักงานอาคารสถานที่")
        data = res.get("data")
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        for d in data:
            self.assertIn("สำนักงานอาคารสถานที่", d["org_name_th"])

    def test_departments_filter_by_org_name_en(self):
        """
        filter ด้วย org_nam_en='building management'
        → ครอบ branch บรรทัด 270
        """
        res = mock_tu_api.mock_tu_departments(org_nam_en="building management")
        data = res.get("data")
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        for d in data:
            self.assertIn("Building Management Office", d["org_name_en"])

    def test_departments_filter_by_dep_code(self):
        """
        filter ด้วย dep_code='5030100'
        → ครอบ branch บรรทัด 272
        """
        res = mock_tu_api.mock_tu_departments(dep_code="5030100")
        data = res.get("data")
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        for d in data:
            self.assertEqual(d["dep_code"], "5030100")

    def test_departments_filter_by_dep_name_substring(self):
        """
        dep_name มีคำว่า 'งานซ่อมบำรุง' ตาม mock data หลายอัน
        """
        res = mock_tu_api.mock_tu_departments(dep_name="งานซ่อมบำรุง")
        data = res.get("data")
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        for d in data:
            self.assertIn("งานซ่อมบำรุง", d["dep_name"])


# -------------------------
# mock_tu_employee_info tests
# -------------------------
class TestMockTUAPIEmployeeInfo(TestCase):
    def test_employee_info_known_username(self):
        """
        username='tech001' → ต้องเจอ 1 record และมี userName ตรง
        """
        res = mock_tu_api.mock_tu_employee_info(username="tech001")
        self.assertIsInstance(res, dict)
        self.assertTrue(res.get("status"))

        data = res.get("data")
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["userName"], "tech001")

    def test_employee_info_unknown_username(self):
        """
        username ที่ไม่มีอยู่เลย → status=False และ data เป็น list ว่าง
        """
        res = mock_tu_api.mock_tu_employee_info(username="unknown_emp_xxx")
        self.assertIsInstance(res, dict)
        self.assertFalse(res.get("status"))
        self.assertEqual(res.get("data"), [])

    def test_employee_info_filter_by_displayname_th(self):
        """
        filter ด้วย displayname_th='ช่างไฟฟ้า'
        → ครอบ branch บรรทัด 340
        """
        res = mock_tu_api.mock_tu_employee_info(displayname_th="ช่างไฟฟ้า")
        data = res.get("data")
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        for e in data:
            self.assertIn("ช่างไฟฟ้า", e["displayname_th"])

    def test_employee_info_filter_by_displayname_en(self):
        """
        filter ด้วย displayname_en='electrician'
        → ครอบ branch บรรทัด 342
        """
        res = mock_tu_api.mock_tu_employee_info(displayname_en="electrician")
        data = res.get("data")
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        for e in data:
            self.assertIn("Electrician", e["displayname_en"])

    def test_employee_info_filter_by_organization(self):
        """
        filter ด้วย organization='สำนักงานอาคารสถานที่'
        → ครอบ branch บรรทัด 344
        """
        res = mock_tu_api.mock_tu_employee_info(organization="สำนักงานอาคารสถานที่")
        data = res.get("data")
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        for e in data:
            self.assertIn("สำนักงานอาคารสถานที่", e["organization"])


# -------------------------
# __main__ block test
# -------------------------
class TestMockTUAPIMainBlock(TestCase):
    def test_main_block_runs_without_error(self):
        """
        รัน module ในโหมด __main__ (เหมือน python mock_tu_api.py)
        → ต้องไม่ error และมีข้อความ summary ตามท้ายไฟล์จริง
        """
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            runpy.run_module(
                "authentication.utils.mock_tu_api",
                run_name="__main__",
            )

        output = buf.getvalue()
        self.assertIn("=== Testing Mock TU API ===", output)
        self.assertIn("1. Test Authentication:", output)
        self.assertIn("2. Test Departments:", output)
        self.assertIn("3. Test Employee Info:", output)
        self.assertIn("=== All tests passed! ===", output)
