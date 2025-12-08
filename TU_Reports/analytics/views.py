from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
import json
from django.core.serializers.json import DjangoJSONEncoder

from tickets.models import Ticket, Category
from authentication.models import User, LoginLog

def is_admin(user):
    return user.is_authenticated and (user.role == 'admin' or user.is_superuser)

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    # --- Ticket Statistics ---
    total_tickets = Ticket.objects.count()
    pending_tickets = Ticket.objects.filter(status='PENDING').count()
    in_progress_tickets = Ticket.objects.filter(status__in=['IN_PROGRESS', 'INSPECTING', 'WORKING']).count()
    completed_tickets = Ticket.objects.filter(status='COMPLETED').count()

    # --- User Statistics ---
    total_users = User.objects.count()
    total_technicians = User.objects.filter(role='technician').count()

    # --- Charts Data: Ticket Status Distribution ---
    status_counts = Ticket.objects.values('status').annotate(count=Count('id'))
    status_map = {
        'PENDING': 'รอดำเนินการ',
        'IN_PROGRESS': 'รับงานแล้ว',
        'INSPECTING': 'กำลังตรวจสอบ',
        'WORKING': 'กำลังดำเนินการ',
        'COMPLETED': 'เสร็จสิ้น',
        'CLOSED': 'ปิดงาน',
        'REJECTED': 'ปฏิเสธ'
    }
    chart_status_labels = []
    chart_status_data = []
    for item in status_counts:
        chart_status_labels.append(status_map.get(item['status'], item['status']))
        chart_status_data.append(item['count'])

    # --- Charts Data: Daily Tickets (Last 30 Days) ---
    today = timezone.now().date()
    last_30_days = today - timedelta(days=29)
    
    daily_tickets = Ticket.objects.filter(created_at__date__gte=last_30_days)\
        .annotate(date=TruncDate('created_at'))\
        .values('date')\
        .annotate(count=Count('id'))\
        .order_by('date')

    daily_data_map = {item['date']: item['count'] for item in daily_tickets}
    chart_daily_labels = []
    chart_daily_data = []
    
    for i in range(30):
        d = last_30_days + timedelta(days=i)
        chart_daily_labels.append(d.strftime('%d/%m'))
        chart_daily_data.append(daily_data_map.get(d, 0))

    # --- Recent Data (Filtered & Sorted) ---
    # recent_tickets = Ticket.objects.select_related('created_by', 'assigned_to', 'category').order_by('-created_at')[:10]
    
    # Base Query
    tickets_query = Ticket.objects.select_related('created_by', 'assigned_to', 'category')

    # Filtering
    status_filter = request.GET.get('status')
    category_filter = request.GET.get('category')
    
    if status_filter:
        tickets_query = tickets_query.filter(status=status_filter)
    if category_filter:
        tickets_query = tickets_query.filter(category_id=category_filter)

    # Sorting
    sort_param = request.GET.get('sort', '-created_at') # Default sort by created_at desc
    valid_sort_fields = ['id', '-id', 'title', '-title', 'status', '-status', 'category__name', '-category__name', 'created_at', '-created_at', 'urgency_level', '-urgency_level']
    
    if sort_param in valid_sort_fields:
        tickets_query = tickets_query.order_by(sort_param)
    else:
        tickets_query = tickets_query.order_by('-created_at')

    recent_tickets = tickets_query # No limit!

    recent_logs = LoginLog.objects.order_by('-created_at')[:10]
    
    categories = Category.objects.all() # For filter dropdown

    context = {
        'total_tickets': total_tickets,
        'pending_tickets': pending_tickets,
        'in_progress_tickets': in_progress_tickets,
        'completed_tickets': completed_tickets,
        'total_users': total_users,
        'total_technicians': total_technicians,
        'recent_tickets': recent_tickets,
        'recent_logs': recent_logs,
        'categories': categories, # Pass categories to template
        # Chart Data
        'chart_status_labels': chart_status_labels,
        'chart_status_data': chart_status_data,
        'chart_daily_labels': chart_daily_labels,
        'chart_daily_data': chart_daily_data,
    }
    return render(request, 'analytics/admin_dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def admin_change_status(request):
    if request.method == 'POST':
        ticket_id = request.POST.get('ticket_id')
        new_status = request.POST.get('new_status')
        comment = request.POST.get('admin_comment')
        
        ticket = get_object_or_404(Ticket, id=ticket_id)
        ticket.status = new_status
        ticket.save()
        
        # In a real app, save 'comment' to a history model
        messages.success(request, f'เปลี่ยนสถานะ Ticket #{ticket.id} เป็น {new_status} เรียบร้อยแล้ว')
    
    return redirect('analytics:dashboard')

@login_required
@user_passes_test(is_admin)
def admin_close_ticket(request):
    if request.method == 'POST':
        ticket_id = request.POST.get('ticket_id')
        ticket = get_object_or_404(Ticket, id=ticket_id)
        
        if ticket.status == 'COMPLETED':
            ticket.status = 'CLOSED'
            ticket.save()
            messages.success(request, f'ปิดงาน Ticket #{ticket.id} เรียบร้อยแล้ว')
        else:
            messages.error(request, 'สามารถปิดงานได้เฉพาะ Ticket ที่เสร็จสิ้นแล้วเท่านั้น')

    return redirect('analytics:dashboard')

import csv
from django.http import HttpResponse

@login_required
@user_passes_test(is_admin)
def export_tickets_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="tickets_export.csv"'
    response.write(u'\ufeff'.encode('utf8')) # BOM for Excel reading Thai correctly

    writer = csv.writer(response)
    writer.writerow(['ID', 'Title', 'Category', 'Status', 'Priority', 'Created By', 'Assigned To', 'Created At'])

    tickets = Ticket.objects.all().select_related('category', 'created_by', 'assigned_to').order_by('-created_at')

    for ticket in tickets:
        writer.writerow([
            ticket.id,
            ticket.title,
            ticket.category.name if ticket.category else '-',
            ticket.get_status_display(),
            ticket.get_urgency_level_display(),
            ticket.created_by.get_display_name() if ticket.created_by else '-',
            ticket.assigned_to.get_display_name() if ticket.assigned_to else '-',
            ticket.created_at.strftime('%Y-%m-%d %H:%M'),
        ])

    return response

# =======================
# User Management Views
# =======================

@login_required
@user_passes_test(is_admin)
def user_list(request):
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'analytics/user_list.html', {'users': users})

@login_required
@user_passes_test(is_admin)
def user_edit(request, user_id):
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        user.displayname_th = request.POST.get('displayname_th')
        user.displayname_en = request.POST.get('displayname_en')
        user.email = request.POST.get('email')
        user.role = request.POST.get('role')
        user.department = request.POST.get('department')
        user.organization = request.POST.get('organization')
        user.is_active = request.POST.get('is_active') == 'on'
        
        # Only admin can set superuser/staff via Django admin, but here we can toggle
        # safe attributes.
        
        user.save()
        messages.success(request, f'บันทึกข้อมูลผู้ใช้ {user.username} เรียบร้อยแล้ว')
        return redirect('analytics:user_list')
        
    return render(request, 'analytics/user_form.html', {'target_user': user})

@login_required
@user_passes_test(is_admin)
def ticket_edit(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    categories = Category.objects.all()
    technicians = User.objects.filter(role='technician', is_active=True)
    
    if request.method == 'POST':
        ticket.title = request.POST.get('title')
        ticket.description = request.POST.get('description')
        ticket.category_id = request.POST.get('category')
        ticket.urgency_level = request.POST.get('urgency_level')
        ticket.status = request.POST.get('status')
        ticket.assigned_to_id = request.POST.get('assigned_to') or None
        
        ticket.save()
        messages.success(request, f'แก้ไข Ticket #{ticket.id} เรียบร้อยแล้ว')
        return redirect('analytics:dashboard')
        
    return render(request, 'analytics/ticket_form.html', {
        'ticket': ticket,
        'categories': categories,
        'technicians': technicians
    })
