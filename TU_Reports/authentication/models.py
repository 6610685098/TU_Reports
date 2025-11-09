from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model รองรับทั้ง TU API และ Local authentication
    """
    AUTH_PROVIDER_CHOICES = [
        ('TU_API', 'TU REST API'),
        ('LOCAL', 'Local Account'),
    ]

    ROLE_CHOICES = [
        ('user', 'User'),
        ('technician', 'Technician'),
        ('admin', 'Admin'),
    ]

    auth_provider = models.CharField(
        max_length=20,
        choices=AUTH_PROVIDER_CHOICES,
        default='LOCAL'
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='user'
    )

    displayname_th = models.CharField(max_length=200, blank=True, null=True)
    displayname_en = models.CharField(max_length=200, blank=True, null=True)
    faculty = models.CharField(max_length=200, blank=True, null=True)  # Student only
    department = models.CharField(max_length=200, blank=True, null=True)
    organization = models.CharField(max_length=200, blank=True, null=True)  # Employee only
    tu_status = models.CharField(max_length=100, blank=True, null=True)

    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['role']),
            models.Index(fields=['auth_provider']),
        ]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    def get_display_name(self):
        """Return Thai display name if available, else username"""
        return self.displayname_th or self.username


class LoginLog(models.Model):
    """บันทึกประวัติการ login"""
    STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]

    METHOD_CHOICES = [
        ('TU_API', 'TU API'),
        ('LOCAL', 'Local'),
    ]

    username = models.CharField(max_length=100)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    login_method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'login_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['username', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"{self.username} - {self.status} at {self.created_at}"
