from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, LoginLog


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'auth_provider', 'is_active', 'created_at')
    list_filter = ('role', 'auth_provider', 'is_active')
    search_fields = ('username', 'email', 'displayname_th', 'displayname_en')

    fieldsets = BaseUserAdmin.fieldsets + (
        ('TU Report Info', {
            'fields': ('role', 'auth_provider', 'displayname_th', 'displayname_en',
                      'faculty', 'department', 'organization', 'tu_status')
        }),
        ('Security', {
            'fields': ('failed_login_attempts', 'locked_until')
        }),
    )


@admin.register(LoginLog)
class LoginLogAdmin(admin.ModelAdmin):
    list_display = ('username', 'status', 'login_method', 'ip_address', 'created_at')
    list_filter = ('status', 'login_method', 'created_at')
    search_fields = ('username', 'description')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
