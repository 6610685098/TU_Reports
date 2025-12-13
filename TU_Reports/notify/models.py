from django.db import models
from django.conf import settings


class Notification(models.Model):
    """
    การแจ้งเตือนในระบบ - Real-time Notification Center
    """
    TYPE_CHOICES = [
        ('NEW_TICKET', 'Ticket ใหม่'),
        ('STATUS_CHANGE', 'เปลี่ยนสถานะ'),
        ('ASSIGNED', 'มอบหมายงาน'),
        ('REASSIGNED', 'มอบหมายงานใหม่'),
        ('COMPLETED', 'ปิดงาน'),
        ('URGENT', 'เร่งด่วน'),
        ('COMMENT', 'ข้อความใหม่'),
        ('FEEDBACK', 'ความคิดเห็น'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()

    # Link to related ticket
    ticket = models.ForeignKey(
        'tickets.Ticket',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )

    # Action button (optional)
    action_url = models.CharField(max_length=500, blank=True)
    action_text = models.CharField(max_length=100, blank=True)

    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type', '-created_at']),
        ]

    def __str__(self):
        return f"{self.recipient.username}: {self.title}"

    def mark_as_read(self):
        """Mark notification as read"""
        from django.utils import timezone
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class NotificationSettings(models.Model):
    """
    ตั้งค่าการแจ้งเตือนของผู้ใช้แต่ละคน
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_settings'
    )

    # Channel preferences
    enable_in_app = models.BooleanField(default=True)
    enable_browser_push = models.BooleanField(default=True)
    enable_email = models.BooleanField(default=False)
    enable_sound = models.BooleanField(default=True)

    # Type preferences
    notify_new_ticket = models.BooleanField(default=True)
    notify_status_change = models.BooleanField(default=True)
    notify_assigned = models.BooleanField(default=True)
    notify_messages = models.BooleanField(default=True)
    notify_urgent = models.BooleanField(default=True)  # Always true (can't disable)

    # Timestamps
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_settings'

    def __str__(self):
        return f"{self.user.username}'s notification settings"
