"""
Security Middleware for TU REPORT
- Prevent back button after logout
- Clear cache headers
- Session validation
"""

from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.contrib import messages


class NoCacheAfterLogoutMiddleware(MiddlewareMixin):
    """
    ป้องกันการกดปุ่มย้อนกลับหลังจาก Logout
    โดยการตั้ค่า Cache-Control headers
    """
    def process_response(self, request, response):
        if request.user.is_authenticated:
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'

        return response


class SessionSecurityMiddleware(MiddlewareMixin):
    """
    ตรวจสอบความปลอดภัยของ Session
    - ตรวจสอบว่า Session ยังใช้งานได้
    - ป้องกัน Session Hijacking
    """
    def process_request(self, request):
        if request.user.is_authenticated:
            if request.session.get('_logout_triggered'):
                request.session.flush()
                messages.warning(request, 'เซสชันหมดอายุ กรุณาเข้าสระบบใหม่')
                return redirect('authentication:login')

        return None


class LoginRequiredMiddleware(MiddlewareMixin):
    """
    บังคับให้ Login ก่อนเข้าถึงหน้าต่างๆ
    ยกเว้นหน้า Login, Static files
    """
    EXEMPT_URLS = [
        '/login/',
        '/logout/',
        '/static/',
        '/media/',
        '/admin/',
    ]

    def process_request(self, request):
        if request.user.is_authenticated:
            return None

        path = request.path_info
        for exempt_url in self.EXEMPT_URLS:
            if path.startswith(exempt_url):
                return None

        messages.info(request, 'กรุณาเข้าสระบบก่อนใช้งาน')
        return redirect('authentication:login')
