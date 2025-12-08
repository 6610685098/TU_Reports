"""
Context Processor สำหรับ Notification
ใช้เพื่อแสดง unread notification count ใน navbar ทุกหน้า
"""
from .models import Notification


def unread_notifications(request):
    """
    เพิ่ม unread_notifications_count ให้ทุก template
    """
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()
        return {
            'unread_notifications_count': unread_count
        }
    return {
        'unread_notifications_count': 0
    }
