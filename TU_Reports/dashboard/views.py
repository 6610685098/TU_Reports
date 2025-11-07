from datetime import timedelta
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from tickets.models import (
    Ticket, Category, TicketFeedback, BeforeAfterPhoto,
    TechnicianPresence, TicketStatusHistory
)
from authentication.models import User

# ใช้
@login_required
def map_view(request):
    """
    หน้าแผนที่หลัก + ตาราง "Latest 10 Tickets"
    - รับได้ทั้ง status=... และ latest_status=...
    """
    # ฟิลเตอร์ของแผนที่
    status_filter = request.GET.get('status')
    latest_status = request.GET.get('latest_status')  # ปุ่ม/ลิงก์เก่าใช้ชื่อนี้
    if not status_filter:
        status_filter = latest_status if latest_status else 'all'

    category_filter = request.GET.get('category', 'all')

    # ====== สำหรับแผนที่ ======
    qs = (Ticket.objects
          .filter(latitude__isnull=False, longitude__isnull=False)
          .select_related('category', 'created_by', 'assigned_to')
          .prefetch_related('before_after_photos', 'attachments')
          .order_by('-created_at'))

    if status_filter == 'pending':
        qs = qs.filter(status='PENDING')
    elif status_filter == 'in_progress':
        qs = qs.filter(status__in=['IN_PROGRESS', 'INSPECTING', 'WORKING'])
    elif status_filter == 'completed':
        qs = qs.filter(status__in=['COMPLETED', 'CLOSED'])

    if category_filter != 'all':
        qs = qs.filter(category_id=category_filter)

    # สร้าง GeoJSON
    features = []
    for t in qs:
        before_photo = None
        after_photo = None
        for p in t.before_after_photos.all():
            if p.photo_type == 'BEFORE' and not before_photo:
                before_photo = p.image.url
            elif p.photo_type == 'AFTER' and not after_photo:
                after_photo = p.image.url

        a = t.attachments.first()
        if not before_photo and a:
            before_photo = a.file.url

        features.append({
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [float(t.longitude), float(t.latitude)]
            },
            'properties': {
                'id': t.id,
                'title': t.title,
                'description': t.description,
                'status': t.status,
                'status_display': t.get_status_display(),
                'category': t.category.name if t.category_id else None,
                'category_id': t.category_id,
                'category_color': getattr(t.category, 'color', '#3B82F6') if t.category_id else '#3B82F6',
                'urgency': t.urgency_level,
                'urgency_display': t.get_urgency_level_display(),
                'created_at': t.created_at.strftime('%d/%m/%Y %H:%M'),
                'before_photo': before_photo,
                'after_photo': after_photo,
            }
        })

    # ====== สำหรับ "Latest 10 Tickets" ======
    latest_status_filter = request.GET.get('latest_status', 'all')
    latest_qs = (Ticket.objects
                 .select_related('category', 'created_by', 'assigned_to')
                 .order_by('-created_at'))

    if latest_status_filter == 'pending':
        latest_qs = latest_qs.filter(status='PENDING')
    elif latest_status_filter == 'in_progress':
        latest_qs = latest_qs.filter(status__in=['IN_PROGRESS', 'INSPECTING', 'WORKING'])
    elif latest_status_filter == 'completed':
        latest_qs = latest_qs.filter(status__in=['COMPLETED', 'CLOSED'])

    latest_qs = latest_qs[:10]

    categories = Category.objects.filter(is_active=True)

    context = {
        'tickets_geojson': json.dumps(
        {'type': 'FeatureCollection', 'features': features},cls=DjangoJSONEncoder,),
        'tickets': qs,
        'categories': categories,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'total_tickets': Ticket.objects.count(),
        'pending_count': Ticket.objects.filter(status='PENDING').count(),
        'in_progress_count': Ticket.objects.filter(status__in=['IN_PROGRESS', 'INSPECTING', 'WORKING']).count(),
        'completed_count': Ticket.objects.filter(status__in=['COMPLETED', 'CLOSED']).count(),
        # ตารางล่าสุด
        'latest_tickets': latest_qs,
        'latest_status_filter': latest_status_filter,
    }
    return render(request, 'dashboard/main_page.html', context)
