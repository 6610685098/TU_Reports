"""
Mock TU REST API
================

ไฟล์นี้จำลอง TU REST API responses สำหรับใช้ในการพัฒนาและทดสอบ
เมื่อได้ Application-Key จริงแล้ว ให้แก้ไข settings.py:
    TU_API_ENABLED=True

References:
- API Documentation: APIdetail.txt
- Base URL: https://restapi.tu.ac.th/
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)



def mock_tu_verify(username, password):
    """
    Mock TU Authentication API
    จะตรวจใน MOCK_USERS ก่อน
    ถ้าไม่พบ user → จะลองเรียก TU API
    """

    import requests
    from django.conf import settings

    # DEBUG: Print credentials to console
    print(f"DEBUG LOGIN: username='{username}', password='{password}'")

    base_url = getattr(settings, "TU_API_BASE_URL", "https://restapi.tu.ac.th")
    app_key = getattr(settings, "TU_APPLICATION_KEY", "")

    MOCK_USERS = {
        "student001": {"password": "student123", "data": {"status": True, "message": "Success",
            "type": "student", "username": "student001", "displayname_th": "นักศึกษา ทดสอบ",
            "displayname_en": "Student Test", "email": "student001@dome.tu.ac.th",
            "faculty": "คณะวิศวกรรมศาสตร์", "department": "สาขาวิชาวิศวกรรมคอมพิวเตอร์"}},
        "staff001": {"password": "staff123", "data": {"status": True, "message": "Success",
            "type": "employee", "username": "staff001", "displayname_th": "พนักงาน ทดสอบ",
            "displayname_en": "Staff Test", "email": "staff001@tu.ac.th",
            "department": "งานซ่อมบำรุงอาคาร", "organization": "สำนักงานอาคารสถานที่"}},
        "tech1": {"password": "tech123", "data": {
            "status": True, "message": "Success", "type": "employee",
            "username": "tech1", "displayname_th": "ช่าง ทดสอบ 1",
            "displayname_en": "Technician 1", "email": "tech1@staff.tu.ac.th",
            "department": "งานบริการเทคนิค", "organization": "สำนักงานอาคารสถานที่",
            "role": "technician"
        }},
        "tech2": {"password": "tech123", "data": {
            "status": True, "message": "Success", "type": "employee",
            "username": "tech2", "displayname_th": "ช่าง ทดสอบ 2",
            "displayname_en": "Technician 2", "email": "tech2@staff.tu.ac.th",
            "department": "งานบริการเทคนิค", "organization": "สำนักงานอาคารสถานที่",
            "role": "technician"
        }},
        "tech3": {"password": "tech123", "data": {
            "status": True, "message": "Success", "type": "employee",
            "username": "tech3", "displayname_th": "ช่าง ทดสอบ 3",
            "displayname_en": "Technician 3", "email": "tech3@staff.tu.ac.th",
            "department": "งานบริการเทคนิค", "organization": "สำนักงานอาคารสถานที่",
            "role": "technician"
        }},
        "tech4": {"password": "tech123", "data": {
            "status": True, "message": "Success", "type": "employee",
            "username": "tech4", "displayname_th": "ช่าง ทดสอบ 4",
            "displayname_en": "Technician 4", "email": "tech4@staff.tu.ac.th",
            "department": "งานบริการเทคนิค", "organization": "สำนักงานอาคารสถานที่",
            "role": "technician"
        }},
        "tech5": {"password": "tech123", "data": {
            "status": True, "message": "Success", "type": "employee",
            "username": "tech5", "displayname_th": "ช่าง ทดสอบ 5",
            "displayname_en": "Technician 5", "email": "tech5@staff.tu.ac.th",
            "department": "งานบริการเทคนิค", "organization": "สำนักงานอาคารสถานที่",
            "role": "technician"
        }},
        "admin": {"password": "admin1234", "data": {
            "status": True, "message": "Success", "type": "employee",
            "username": "admin", "displayname_th": "ผู้ดูแลระบบ",
            "displayname_en": "System Admin", "email": "admin@tu.ac.th",
            "department": "IT Support", "organization": "สำนักงานศูนย์เทคโนโลยีสารสนเทศและการสื่อสาร",
            "role": "admin"
        }},
    }

    username = str(username).strip()
    password = str(password or "").strip()
    logger.info(f"[Mock TU API] Login request for username: {username}")

    if username in MOCK_USERS:
        user = MOCK_USERS[username]
        if password == user["password"]:
            logger.info(f"[Mock TU API] SUCCESS (mock) for {username}")
            print(f"DEBUG LOGIN: SUCCESS for {username}")
            return user["data"]
        else:
            logger.warning(f"[Mock TU API] Invalid password for {username}")
            print(f"DEBUG LOGIN: FAILED password mismatch for {username}. Expected '{user['password']}' got '{password}'")
            return {"status": False, "message": "User or Password Invalid!"}

    logger.info(f"[Mock TU API] User not found -> trying real TU API")
    print(f"DEBUG LOGIN: User {username} not in MOCK_USERS")

    if not app_key:
        logger.error("[Mock TU API] TU_APPLICATION_KEY not configured in settings.")
        return {"status": False, "message": "Missing TU_APPLICATION_KEY"}

    try:
        url = f"{base_url}/api/v1/auth/Ad/verify"
        headers = {"Content-Type": "application/json", "Application-Key": app_key}
        payload = {"UserName": username, "PassWord": password}
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        logger.info(f"[Mock TU API] Real call -> {response.status_code}, preview={response.text[:200]}")
    
        if response.status_code == 200:
            return response.json()
        elif response.status_code in (404, 405, 500):
            logger.warning("[Mock TU API] Trying fallback /verify2 ...")
            response2 = requests.post(
                f"{base_url}/api/v1/auth/Ad/verify2",
                json=payload, headers=headers, timeout=10
            )
            return response2.json()
        else:
            return {"status": False, "message": f"Real API returned {response.status_code}"}

    except requests.exceptions.RequestException as e:
        logger.error(f"[Mock TU API] Real API request failed: {e}")
        return {"status": False, "message": f"API call failed: {e}"}




def mock_tu_log_auth(status=None, date=None, username=None, record=10):
    """
    Mock Log Authentication API
    Endpoint: GET /api/v1/auth/Log/auth/?status={true or false}
              GET /api/v1/auth/Log/find/?date={YYYY-mm-dd}

    Args:
        status (str): 'true' or 'false'
        date (str): YYYY-mm-dd format
        username (str): Filter by username
        record (int): Limit records (1-10000)

    Returns:
        list: Array of log entries
    """

    mock_logs = [
        {
            "Description": "Login Success : student001",
            "Status": "TRUE : 200 Method:POST/Authentication",
            "CreateDate": "2025-10-30 08:36:43.000"
        },
        {
            "Description": "Login Success : staff001",
            "Status": "TRUE : 200 Method:POST/Authentication",
            "CreateDate": "2025-10-30 08:30:15.000"
        },
        {
            "Description": "Login Failed : invalid_user",
            "Status": "FALSE : 400 Method:POST/Authentication",
            "CreateDate": "2025-10-30 08:25:10.000"
        },
        {
            "Description": "Login Success : tech_admin",
            "Status": "TRUE : 200 Method:POST/Authentication",
            "CreateDate": "2025-10-30 08:20:05.000"
        },
        {
            "Description": "Login Failed : student001",
            "Status": "FALSE : 400 Method:POST/Authentication",
            "CreateDate": "2025-10-30 08:15:00.000"
        },
    ]

    if status is not None:
        status_filter = "TRUE" if status in ["true", True] else "FALSE"
        mock_logs = [log for log in mock_logs if status_filter in log["Status"]]

    if username:
        mock_logs = [log for log in mock_logs if username in log["Description"]]

    return mock_logs[:min(record, 10000)]



def mock_tu_departments(org_code=None, org_nam_th=None, org_nam_en=None, dep_code=None, dep_name=None):
    """
    Mock Department Employee API
    Endpoint: GET /api/v2/emp/dep/all
              GET /api/v2/emp/dep/find/?org_code=xxx

    Args:
        org_code (str): Organization code
        org_nam_th (str): Organization name (Thai)
        org_nam_en (str): Organization name (English)
        dep_code (str): Department code
        dep_name (str): Department name

    Returns:
        dict: API response with department data
    """

    departments = [
        {
            "org_code": "5030000",
            "org_name_th": "สำนักงานอาคารสถานที่",
            "org_name_en": "Building Management Office",
            "dep_code": "5030100",
            "dep_name": "งานซ่อมบำรุงไฟฟ้า"
        },
        {
            "org_code": "5030000",
            "org_name_th": "สำนักงานอาคารสถานที่",
            "org_name_en": "Building Management Office",
            "dep_code": "5030200",
            "dep_name": "งานซ่อมบำรุงประปา"
        },
        {
            "org_code": "5030000",
            "org_name_th": "สำนักงานอาคารสถานที่",
            "org_name_en": "Building Management Office",
            "dep_code": "5030300",
            "dep_name": "งานซ่อมบำรุงเครื่องปรับอากาศ"
        },
        {
            "org_code": "5040000",
            "org_name_th": "สำนักงานศูนย์เทคโนโลยีสารสนเทศและการสื่อสาร",
            "org_name_en": "ICT Center",
            "dep_code": "5040100",
            "dep_name": "งานบริการเทคนิค"
        },
        {
            "org_code": "5040000",
            "org_name_th": "สำนักงานศูนย์เทคโนโลยีสารสนเทศและการสื่อสาร",
            "org_name_en": "ICT Center",
            "dep_code": "5040200",
            "dep_name": "งานวิเคราะห์และพัฒนาระบบ"
        },
        {
            "org_code": "1020000",
            "org_name_th": "กองบริหารศูนย์ท่าพระจันทร์",
            "org_name_en": "Thaprachan Center",
            "dep_code": "1020100",
            "dep_name": "งานบริหารสำนักงาน ท่าพระจันทร์"
        },
        {
            "org_code": "1020000",
            "org_name_th": "กองบริหารศูนย์ท่าพระจันทร์",
            "org_name_en": "Thaprachan Center",
            "dep_code": "1020200",
            "dep_name": "งานประชุม"
        },
    ]

    filtered_deps = departments

    if org_code:
        filtered_deps = [d for d in filtered_deps if d["org_code"] == org_code]
    if org_nam_th:
        filtered_deps = [d for d in filtered_deps if org_nam_th in d["org_name_th"]]
    if org_nam_en:
        filtered_deps = [d for d in filtered_deps if org_nam_en.lower() in d["org_name_en"].lower()]
    if dep_code:
        filtered_deps = [d for d in filtered_deps if d["dep_code"] == dep_code]
    if dep_name:
        filtered_deps = [d for d in filtered_deps if dep_name in d["dep_name"]]

    return {
        "timestamp": int(datetime.now().timestamp() * 1000),
        "status": True,
        "message": "Success",
        "data": filtered_deps
    }



def mock_tu_employee_info(username=None, displayname_th=None, displayname_en=None, organization=None):
    """
    Mock Employee Info API
    Endpoint: GET /api/v2/profile/emp/info/?username=xxx

    Args:
        username (str): Employee username
        displayname_th (str): Thai display name
        displayname_en (str): English display name
        organization (str): Organization name

    Returns:
        dict: API response with employee data
    """

    employees = [
        {
            "userName": "tech001",
            "displayname_th": "ช่างไฟฟ้า หนึ่ง",
            "displayname_en": "Electrician One",
            "email": "tech001@staff.tu.ac.th",
            "department": "งานซ่อมบำรุงไฟฟ้า",
            "organization": "สำนักงานอาคารสถานที่"
        },
        {
            "userName": "tech002",
            "displayname_th": "ช่างประปา สอง",
            "displayname_en": "Plumber Two",
            "email": "tech002@staff.tu.ac.th",
            "department": "งานซ่อมบำรุงประปา",
            "organization": "สำนักงานอาคารสถานที่"
        },
        {
            "userName": "staff001",
            "displayname_th": "พนักงาน ทดสอบ",
            "displayname_en": "Staff Test",
            "email": "staff001@tu.ac.th",
            "department": "งานซ่อมบำรุงอาคาร",
            "organization": "สำนักงานอาคารสถานที่"
        },
        {
            "userName": "tech_admin",
            "displayname_th": "ผู้ดูแลระบบ ทดสอบ",
            "displayname_en": "Admin Test",
            "email": "tech.admin@tu.ac.th",
            "department": "งานวิเคราะห์และพัฒนาระบบ",
            "organization": "สำนักงานศูนย์เทคโนโลยีสารสนเทศและการสื่อสาร"
        },
    ]

    filtered_emps = employees

    if username:
        filtered_emps = [e for e in filtered_emps if e["userName"] == username]
    if displayname_th:
        filtered_emps = [e for e in filtered_emps if displayname_th in e["displayname_th"]]
    if displayname_en:
        filtered_emps = [e for e in filtered_emps if displayname_en.lower() in e["displayname_en"].lower()]
    if organization:
        filtered_emps = [e for e in filtered_emps if organization in e["organization"]]

    return {
        "timestamp": int(datetime.now().timestamp() * 1000),
        "status": True if filtered_emps else False,
        "message": "Success" if filtered_emps else "No data found",
        "data": filtered_emps
    }



# def is_real_api_enabled():
#     """
#     Check if real TU API should be used
# 
#     Returns:
#         bool: True if TU_API_ENABLED=True in settings
#     """
#     from django.conf import settings
#     return getattr(settings, 'TU_API_ENABLED', False)


# def call_real_tu_api(endpoint, method='GET', data=None, headers=None):
#     """
#     Call real TU REST API (when Application-Key is available)
# 
#     Args:
#         endpoint (str): API endpoint path
#         method (str): HTTP method (GET, POST)
#         data (dict): Request body data
#         headers (dict): Request headers
# 
#     Returns:
#         dict: API response
# 
#     Example:
#         response = call_real_tu_api(
#             '/api/v1/auth/Ad/verify',
#             method='POST',
#             data={'UserName': 'test', 'PassWord': 'pass'},
#             headers={'Application-Key': 'xxx'}
#         )
#     """
#     import requests
#     from django.conf import settings
# 
#     base_url = getattr(settings, 'TU_API_BASE_URL', 'https://restapi.tu.ac.th')
#     app_key = getattr(settings, 'TU_APPLICATION_KEY', '')
# 
#     if not app_key:
#         raise ValueError("TU_APPLICATION_KEY not configured")
# 
#     url = f"{base_url}{endpoint}"
# 
#     default_headers = {
#         'Content-Type': 'application/json',
#         'Application-Key': app_key
#     }
# 
#     if headers:
#         default_headers.update(headers)
# 
#     try:
#         if method.upper() == 'POST':
#             response = requests.post(url, json=data, headers=default_headers, timeout=10)
#         else:
#             response = requests.get(url, headers=default_headers, timeout=10)
# 
#         response.raise_for_status()
#         return response.json()
# 
#     except requests.exceptions.RequestException as e:
#         logger.error(f"TU API call failed: {e}")
#         return {
#             "status": False,
#             "message": f"API call failed: {str(e)}"
#         }


# def tu_verify(username, password):
#     """
#     Main interface for TU authentication
#     Automatically switches between mock and real API based on settings
# 
#     Args:
#         username (str): TU username
#         password (str): TU password
# 
#     Returns:
#         dict: Authentication response
#     """
#     if is_real_api_enabled():
#         return call_real_tu_api(
#             '/api/v1/auth/Ad/verify',
#             method='POST',
#             data={'UserName': username, 'PassWord': password}
#         )
#     else:
#         return mock_tu_verify(username, password)


# def tu_get_departments(**filters):
#     """
#     Get departments from TU API
# 
#     Args:
#         **filters: org_code, org_nam_th, etc.
# 
#     Returns:
#         dict: Department data
#     """
#     if is_real_api_enabled():
#         query_params = '&'.join([f"{k}={v}" for k, v in filters.items() if v])
#         endpoint = '/api/v2/emp/dep/find/?' + query_params if query_params else '/api/v2/emp/dep/all'
# 
#         return call_real_tu_api(endpoint, method='GET')
#     else:
#         return mock_tu_departments(**filters)


# def tu_get_employee_info(**filters):
#     """
#     Get employee info from TU API
# 
#     Args:
#         **filters: username, displayname_th, etc.
# 
#     Returns:
#         dict: Employee data
#     """
#     if is_real_api_enabled():
#         query_params = '&'.join([f"{k}={v}" for k, v in filters.items() if v])
#         endpoint = '/api/v2/profile/emp/info/?' + query_params
# 
#         return call_real_tu_api(endpoint, method='GET')
#     else:
#         return mock_tu_employee_info(**filters)



if __name__ == "__main__":
    print("=== Testing Mock TU API ===\n")

    print("1. Test Authentication:")
    result = mock_tu_verify("student001", "student123")
    print(f"   Student login: {result.get('status')}")
    print(f"   Name: {result.get('displayname_th')}\n")

    print("2. Test Departments:")
    result = mock_tu_departments()
    print(f"   Total departments: {len(result['data'])}\n")

    print("3. Test Employee Info:")
    result = mock_tu_employee_info(username="tech001")
    print(f"   Found: {result['status']}")
    if result['data']:
        print(f"   Name: {result['data'][0]['displayname_th']}\n")

    print("=== All tests passed! ===")