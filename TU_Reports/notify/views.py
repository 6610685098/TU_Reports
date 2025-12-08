from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Notification


@login_required
def notification_list(request):
    """Notification Center - รายการแจ้งเตือนทั้งหมด"""
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')[:50]

    # Filter by type if specified
    filter_type = request.GET.get('type')
    if filter_type:
        notifications = notifications.filter(notification_type=filter_type)

    # Filter by read status
    filter_read = request.GET.get('read')
    if filter_read == 'unread':
        notifications = notifications.filter(is_read=False)
    elif filter_read == 'read':
        notifications = notifications.filter(is_read=True)

    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()

    context = {
        'notifications': notifications,
        'unread_count': unread_count,
        'filter_type': filter_type,
        'filter_read': filter_read,
    }

    return render(request, 'notify/notification_list.html', context)


@login_required
def mark_as_read(request, notification_id):
    """ทำเครื่องหมายอ่านแล้ว"""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.mark_as_read()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})

    messages.success(request, 'ทำเครื่องหมายอ่านแล้ว')
    return redirect('notify:list')


@login_required
def mark_all_as_read(request):
    """ทำเครื่องหมายอ่านทั้งหมด"""
    notifications = Notification.objects.filter(recipient=request.user, is_read=False)
    count = notifications.count()

    for notification in notifications:
        notification.mark_as_read()

    messages.success(request, f'ทำเครื่องหมายอ่านแล้ว {count} รายการ')
    return redirect('notify:list')
