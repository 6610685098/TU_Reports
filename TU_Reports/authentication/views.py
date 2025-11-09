from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from .models import User, LoginLog

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@require_http_methods(["GET", "POST"])
def login_view(request):
    """Login page - รองรับทั้ง TU API และ Local"""
    if request.user.is_authenticated:
        if request.user.role == 'admin':
            return redirect('dashboard:summary')
        elif request.user.role == 'technician':
            return redirect('technician:job_list')
        else:
            return redirect('dashboard:map')  # User ไป dashboard หลัก

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        login_type = request.POST.get('login_type')  # 'tu_api' or 'local'

        if login_type == 'tu_api':
            from .utils.mock_tu_api import mock_tu_verify

            result = mock_tu_verify(username, password)

            if result.get('status'):
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'auth_provider': 'TU_API',
                        'role': 'user',  # Default role
                    }
                )

                user.displayname_th = result.get('displayname_th')
                user.displayname_en = result.get('displayname_en')
                user.email = result.get('email', '')
                user.tu_status = result.get('tu_status', '')

                if result.get('type') == 'student':
                    user.faculty = result.get('faculty', '')
                    user.department = result.get('department', '')
                elif result.get('type') == 'employee':
                    user.organization = result.get('organization', '')
                    user.department = result.get('department', '')

                user.save()

                login(request, user, backend='django.contrib.auth.backends.ModelBackend')

                LoginLog.objects.create(
                    username=username,
                    description=f"Login Success via TU API: {username}",
                    status='SUCCESS',
                    login_method='TU_API',
                    ip_address=get_client_ip(request)
                )

                messages.success(request, f'ยินดีต้อนรับ {user.get_display_name()}')

                if user.role == 'admin':
                    return redirect('dashboard:summary')
                elif user.role == 'technician':
                    return redirect('technician:job_list')
                else:
                    return redirect('dashboard:map')  # User ไป dashboard หลัก
            else:
                LoginLog.objects.create(
                    username=username,
                    description=f"Login Failed via TU API: {result.get('message')}",
                    status='FAILED',
                    login_method='TU_API',
                    ip_address=get_client_ip(request)
                )
                messages.error(request, 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง (TU API)')

        else:  # Local login
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)

                LoginLog.objects.create(
                    username=username,
                    description=f"Login Success via Local: {username}",
                    status='SUCCESS',
                    login_method='LOCAL',
                    ip_address=get_client_ip(request)
                )

                messages.success(request, f'ยินดีต้อนรับ {user.get_display_name()}')

                if user.role == 'admin':
                    return redirect('dashboard:summary')
                elif user.role == 'technician':
                    return redirect('technician:job_list')
                else:
                    return redirect('dashboard:map')  # User ไป dashboard หลัก
            else:
                LoginLog.objects.create(
                    username=username,
                    description="Login Failed via Local: Invalid credentials",
                    status='FAILED',
                    login_method='LOCAL',
                    ip_address=get_client_ip(request)
                )
                messages.error(request, 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')

    return render(request, 'authentication/login.html')

def logout_view(request):
    """Logout - ป้องกันการกดย้อนกลับ"""
    request.session['_logout_triggered'] = True

    logout(request)
    request.session.flush()

    messages.info(request, 'ออกจากระบบเรียบร้อยแล้ว')

    response = redirect('authentication:login')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'

    return response
