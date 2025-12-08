"""
Notification Helper Functions
"""
from .models import Notification
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def create_notification(user, title, message, ticket=None, notification_type='INFO'):
    """
    สร้าง notification ใหม่ และส่ง real-time notification ผ่าน WebSocket

    Args:
        user: ผู้รับ notification
        title: หัวข้อ
        message: ข้อความ
        ticket: Ticket ที่เกี่ยวข้อง (optional)
        notification_type: ประเภท (ASSIGNED, STATUS_CHANGE, COMPLETED, etc.)
    """
    # Create notification in database
    notification = Notification.objects.create(
        recipient=user,
        title=title,
        message=message,
        ticket=ticket,
        notification_type=notification_type
    )

    # Send real-time notification via WebSocket
    send_notification_to_user(user.id, notification)

    return notification


def send_notification_to_user(user_id, notification):
    """
    ส่ง real-time notification ผ่าน WebSocket

    Args:
        user_id: ID ของผู้ใช้
        notification: Notification object
    """
    channel_layer = get_channel_layer()
    group_name = f'notifications_{user_id}'

    # Get unread count
    unread_count = Notification.objects.filter(
        recipient_id=user_id,
        is_read=False
    ).count()

    # Prepare notification data
    notification_data = {
        'id': notification.id,
        'title': notification.title,
        'message': notification.message,
        'notification_type': notification.notification_type,
        'ticket_id': notification.ticket.id if notification.ticket else None,
        'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'is_read': notification.is_read,
    }

    # Send to WebSocket group
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification_message',
                'notification': notification_data,
                'unread_count': unread_count,
            }
        )


def notify_ticket_assigned(ticket):
    """แจ้งเตือนเมื่อ ticket ถูก assign ให้ช่าง"""
    if ticket.assigned_to:
        create_notification(
            user=ticket.assigned_to,
            title='งานใหม่ถูกมอบหมาย',
            message=f'คุณได้รับมอบหมายงาน: {ticket.title}',
            ticket=ticket,
            notification_type='ASSIGNED'
        )


def notify_ticket_accepted(ticket):
    """แจ้งเตือนผู้แจ้งเมื่อช่างรับงาน"""
    create_notification(
        user=ticket.created_by,
        title='ช่างรับงานแล้ว',
        message=f'ช่าง {ticket.assigned_to.get_display_name()} รับงาน: {ticket.title}',
        ticket=ticket,
        notification_type='STATUS_CHANGE'
    )


def notify_ticket_rejected(ticket, technician):
    """แจ้งเตือนผู้แจ้งเมื่อช่างปฏิเสธงาน"""
    create_notification(
        user=ticket.created_by,
        title='ช่างปฏิเสธงาน',
        message=f'ช่าง {technician.get_display_name()} ปฏิเสธงาน: {ticket.title} (กำลังหาช่างใหม่)',
        ticket=ticket,
        notification_type='REASSIGNED'
    )


def notify_ticket_completed(ticket):
    """แจ้งเตือนผู้แจ้งเมื่องานเสร็จ"""
    create_notification(
        user=ticket.created_by,
        title='งานเสร็จสิ้น',
        message=f'งาน: {ticket.title} เสร็จสิ้นแล้ว กรุณาให้คะแนน',
        ticket=ticket,
        notification_type='COMPLETED'
    )


def notify_status_changed(ticket, old_status, new_status):
    """แจ้งเตือนเมื่อสถานะเปลี่ยน"""
    create_notification(
        user=ticket.created_by,
        title='สถานะงานเปลี่ยนแปลง',
        message=f'งาน: {ticket.title} เปลี่ยนสถานะเป็น {ticket.get_status_display()}',
        ticket=ticket,
        notification_type='STATUS_CHANGE'
    )
