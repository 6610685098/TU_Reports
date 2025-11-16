from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from tickets.models import Ticket, TicketStatusHistory, BeforeAfterPhoto, TechnicianPresence
from tickets.dispatcher import auto_dispatch_ticket
from django.db.models import Q
try:
    from notify.utils import (
        notify_ticket_accepted,
        notify_ticket_rejected,
        notify_ticket_completed,
        notify_status_changed,
    )
except Exception:
    # ถ้าไม่มีแพ็กเกจ/โมดูล notify ให้ทำเป็น no-op
    def notify_ticket_accepted(*args, **kwargs): 
        return None
    def notify_ticket_rejected(*args, **kwargs): 
        return None
    def notify_ticket_completed(*args, **kwargs): 
        return None
    def notify_status_changed(*args, **kwargs): 
        return None

@login_required
def job_list(request):
    """รายการงานของช่าง พร้อม Search & Filter"""
    if request.user.role != 'technician':
        messages.error(request, 'คุณไม่มีสิทธิ์เข้าถึงหน้านี้')
        return redirect('technician:my_tickets_tech')

    # Base queryset - งานที่ได้รับมอบหมาย
    assigned_tickets = Ticket.objects.filter(assigned_to=request.user).exclude(
        status__in=['CLOSED', 'REJECTED']
    ).select_related('category', 'created_by')

    # Get filter parameters
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')
    urgency_filter = request.GET.get('urgency', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    sort_by = request.GET.get('sort', '-created_at')

    # Apply search
    if search_query:
        from django.db.models import Q
        assigned_tickets = assigned_tickets.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Apply filters
    if status_filter:
        assigned_tickets = assigned_tickets.filter(status=status_filter)

    if category_filter:
        assigned_tickets = assigned_tickets.filter(category_id=category_filter)

    if urgency_filter:
        assigned_tickets = assigned_tickets.filter(urgency_level=urgency_filter)

    if date_from:
        from datetime import datetime
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            assigned_tickets = assigned_tickets.filter(created_at__gte=date_from_obj)
        except ValueError:
            pass

    if date_to:
        from datetime import datetime, timedelta
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            assigned_tickets = assigned_tickets.filter(created_at__lt=date_to_obj + timedelta(days=1))
        except ValueError:
            pass

    # Apply sorting
    if sort_by in ['-created_at', 'created_at', '-urgency_level', 'urgency_level']:
        assigned_tickets = assigned_tickets.order_by(sort_by)
    else:
        assigned_tickets = assigned_tickets.order_by('-created_at')

    # Get categories for filter dropdown
    from tickets.models import Category
    categories = Category.objects.filter(is_active=True)

    # Get availability status
    try:
        presence = TechnicianPresence.objects.get(technician=request.user)
        is_available = presence.is_available
    except TechnicianPresence.DoesNotExist:
        is_available = True  # Default to available

    # Count statistics (all assigned tickets, not filtered)
    all_assigned = Ticket.objects.filter(assigned_to=request.user).exclude(status__in=['CLOSED', 'REJECTED'])

    context = {
        'assigned_tickets': assigned_tickets,
        'categories': categories,
        'pending_count': all_assigned.filter(status='PENDING').count(),
        'in_progress_count': all_assigned.filter(status__in=['IN_PROGRESS', 'INSPECTING', 'WORKING']).count(),
        'is_available': is_available,
        # Pass filter values back to template
        'search_query': search_query,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'urgency_filter': urgency_filter,
        'date_from': date_from,
        'date_to': date_to,
        'sort_by': sort_by,
        'filtered_count': assigned_tickets.count(),
    }

    return render(request, 'technician/job_list.html', context)

@login_required
def update_status(request, ticket_id):
    """อัปเดตสถานะ Ticket"""
    if request.user.role != 'technician':
        messages.error(request, 'คุณไม่มีสิทธิ์')
        return redirect('tickets:my_tickets')

    ticket = get_object_or_404(Ticket, id=ticket_id, assigned_to=request.user)

    if request.method == 'POST':
        new_status = request.POST.get('new_status')
        comment = request.POST.get('comment', '')

        old_status = ticket.status
        ticket.status = new_status
        ticket.save()

        # Save history
        TicketStatusHistory.objects.create(
            ticket=ticket,
            status=new_status,
            changed_by=request.user,
            note=comment
        )

        messages.success(request, f'อัปเดตสถานะเป็น "{ticket.get_status_display()}" แล้ว')
        return redirect('technician:job_list')

    return redirect('tickets:ticket_detail', ticket_id=ticket_id)

@login_required
def accept_job(request, ticket_id):
    """รับงาน - TODO: Implement full logic"""
    if request.user.role != 'technician':
        messages.error(request, 'คุณไม่มีสิทธิ์')
        return redirect('tickets:my_tickets')

    ticket = get_object_or_404(Ticket, id=ticket_id, assigned_to=request.user)

    if ticket.status != 'PENDING':
        messages.error(request, 'ไม่สามารถรับงานนี้ได้')
        return redirect('technician:job_list')

    # Update status to IN_PROGRESS
    old_status = ticket.status
    ticket.status = 'IN_PROGRESS'
    ticket.save()

    # Save history
    TicketStatusHistory.objects.create(
        ticket=ticket,
        status='IN_PROGRESS',
        changed_by=request.user,
        note='ช่างรับงานแล้ว'
    )

    # Send notification to ticket creator
    notify_ticket_accepted(ticket)

    messages.success(request, f'รับงาน Ticket #{ticket.id} เรียบร้อยแล้ว')
    return redirect('technician:job_list')

@login_required
def reject_job(request, ticket_id):
    """ปฏิเสธงาน + Reassign อัตโนมัติ"""
    if request.user.role != 'technician':
        messages.error(request, 'คุณไม่มีสิทธิ์')
        return redirect('tickets:my_tickets')

    ticket = get_object_or_404(Ticket, id=ticket_id, assigned_to=request.user)

    if ticket.status != 'PENDING':
        messages.error(request, 'ไม่สามารถปฏิเสธงานนี้ได้')
        return redirect('technician:job_list')

    # Save old technician name before unassigning
    old_tech = ticket.assigned_to

    # Unassign current technician
    ticket.assigned_to = None
    ticket.save()

    # Record rejection in history
    TicketStatusHistory.objects.create(
        ticket=ticket,
        status='PENDING',
        changed_by=request.user,
        note=f'ช่าง {old_tech.get_display_name()} ปฏิเสธงาน'
    )

    # Notify creator about rejection
    notify_ticket_rejected(ticket, old_tech)

    # Auto-dispatch to find new technician
    auto_dispatch_ticket(ticket)
    ticket.refresh_from_db()

    # Show result message
    if ticket.assigned_to:
        messages.success(
            request,
            f'✅ มอบหมายใหม่ให้ {ticket.assigned_to.get_display_name()} แล้ว'
        )
    else:
        messages.warning(
            request,
            '⚠️ ไม่พบช่างที่พร้อมรับงาน กรุณามอบหมายด้วยตนเอง'
        )

    return redirect('technician:job_list')

@login_required
def complete_job(request, ticket_id):
    """ทำงานเสร็จ + แนบ After Photo"""
    if request.user.role != 'technician':
        messages.error(request, 'คุณไม่มีสิทธิ์')
        return redirect('tickets:my_tickets')

    ticket = get_object_or_404(Ticket, id=ticket_id, assigned_to=request.user)

    if ticket.status not in ['IN_PROGRESS', 'INSPECTING', 'WORKING']:
        messages.error(request, 'ไม่สามารถปิดงานนี้ได้')
        return redirect('technician:job_list')

    if request.method == 'POST':
        if request.FILES.get('after_photo'):
            photo = request.FILES['after_photo']
            BeforeAfterPhoto.objects.create(
                ticket=ticket, photo_type='AFTER', image=photo,
                uploaded_by=request.user
            )
            old_status = ticket.status
            ticket.status = 'COMPLETED'
            ticket.completed_at = timezone.now()
            ticket.save()
            TicketStatusHistory.objects.create(
                ticket=ticket,
                status='COMPLETED',
                changed_by=request.user,
                note=request.POST.get('comment', 'ทำงานเสร็จแล้ว')
            )

            # Notify creator that work is completed
            notify_ticket_completed(ticket)

            messages.success(request, f'✅ ทำงาน Ticket #{ticket.id} เสร็จเรียบร้อย!')
            return redirect('technician:job_list')
        else:
            messages.error(request, 'กรุณาแนบรูปภาพหลังซ่อม')

    return render(request, 'technician/complete_job.html', {'ticket': ticket})

@login_required
def update_availability(request):
    """Toggle สถานะพร้อมทำงาน"""
    if request.user.role != 'technician':
        messages.error(request, 'คุณไม่มีสิทธิ์')
        return redirect('tickets:my_tickets')

    # Get or create TechnicianPresence
    presence, created = TechnicianPresence.objects.get_or_create(
        technician=request.user,
        defaults={'is_available': True}
    )

    # Toggle availability
    presence.is_available = not presence.is_available
    presence.save()

    # Show message
    if presence.is_available:
        messages.success(request, '✅ คุณพร้อมรับงานใหม่แล้ว')
    else:
        messages.warning(request, '⏸️ คุณหยุดรับงานใหม่ชั่วคราว (งานที่มีอยู่แล้วยังคงดำเนินการต่อ)')

    return redirect('technician:job_list')

@login_required
def my_tickets(request):
    if request.user.role != 'technician':
        messages.error(request, 'คุณไม่มีสิทธิ์เข้าถึงหน้านี้')
        return redirect('tickets:my_tickets')

    tickets_qs = Ticket.objects.filter(created_by=request.user).exclude(
        status__in=['CLOSED', 'REJECTED']
    ).select_related('category', 'assigned_to')


    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')
    urgency_filter = request.GET.get('urgency', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    sort_by = request.GET.get('sort', '-created_at')

    if search_query:
        tickets_qs = tickets_qs.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if status_filter:
        tickets_qs = tickets_qs.filter(status=status_filter)

    if category_filter:
        tickets_qs = tickets_qs.filter(category_id=category_filter)

    if urgency_filter:
        tickets_qs = tickets_qs.filter(urgency_level=urgency_filter)

    if date_from:
        from datetime import datetime
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            tickets_qs = tickets_qs.filter(created_at__gte=date_from_obj)
        except ValueError:
            pass

    if date_to:
        from datetime import datetime, timedelta
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            tickets_qs = tickets_qs.filter(created_at__lt=date_to_obj + timedelta(days=1))
        except ValueError:
            pass

    if sort_by in ['-created_at', 'created_at', '-urgency_level', 'urgency_level']:
        tickets_qs = tickets_qs.order_by(sort_by)
    else:
        tickets_qs = tickets_qs.order_by('-created_at')

    from tickets.models import Category
    categories = Category.objects.filter(is_active=True)

    all_created = Ticket.objects.filter(created_by=request.user).exclude(
        status__in=['CLOSED', 'REJECTED']
    )

    context = {
        'assigned_tickets': tickets_qs,
        'categories': categories,
        'pending_count': all_created.filter(status='PENDING').count(),
        'in_progress_count': all_created.filter(
            status__in=['IN_PROGRESS', 'INSPECTING', 'WORKING']
        ).count(),
        'is_available': True,  
        'mode': 'my_tickets_tech',   

        'search_query': search_query,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'urgency_filter': urgency_filter,
        'date_from': date_from,
        'date_to': date_to,
        'sort_by': sort_by,
        'filtered_count': tickets_qs.count(),
    }
    return render(request, 'technician/tech_my_tickets.html', context)
