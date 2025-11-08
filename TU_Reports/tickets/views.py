# tickets/views.py
from datetime import datetime, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .forms import TicketForm
from .models import (
    Ticket, TicketStatusHistory, BeforeAfterPhoto, TicketFeedback, Category
)
from tickets.utils.images import resize_and_compress


# -------------------------------------------------------------------
# สร้าง Ticket ใหม่ ได้แล้ว
# -------------------------------------------------------------------
@login_required
def create_ticket(request):
    if request.method == 'POST':
        form = TicketForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.created_by = request.user

            # รับ lat/lng จากฟอร์ม (ถ้ามี)
            lat = request.POST.get('latitude')
            lng = request.POST.get('longitude')
            if lat and lng:
                try:
                    ticket.latitude = float(lat)
                    ticket.longitude = float(lng)
                except ValueError:
                    messages.warning(request, 'พิกัดไม่ถูกต้อง ระบบจะบันทึกโดยไม่ใช้พิกัด')

            ticket.save()

            # BEFORE photos (รองรับทั้ง before_photo เดี่ยว และ photos_before หลายไฟล์)
            before_files = []
            if request.FILES.get('before_photo'):
                before_files.append(request.FILES['before_photo'])
            before_files.extend(request.FILES.getlist('photos_before'))

            for photo in before_files:
                try:
                    optimized = resize_and_compress(
                        photo,
                        max_width=1600, max_height=1600,
                        quality=80, target_format=None, keep_exif=False
                    )
                except Exception:
                    optimized = photo  # ถ้าบีบอัดพัง ยังเซฟไฟล์เดิมได้

                BeforeAfterPhoto.objects.create(
                    ticket=ticket,
                    photo_type='BEFORE',
                    image=optimized,
                    uploaded_by=request.user,
                )

            # ประวัติสถานะเริ่มต้น
            TicketStatusHistory.objects.create(
                ticket=ticket,
                status='PENDING',
                changed_by=request.user,
                note='สร้าง Ticket ใหม่',
            )
            return redirect('tickets:ticket_detail', ticket_id=ticket.id)
    else:
            form = TicketForm()
            # มาใส่มอบหมายงานช่างที่หลัง

    return render(request, 'user/create_ticket.html', {'form': form})


# -------------------------------------------------------------------
# รายการ Ticket ของฉัน + ค้นหา/กรอง ได้แล้ว
# -------------------------------------------------------------------
@login_required
def my_tickets(request):
    tickets = Ticket.objects.filter(created_by=request.user).select_related(
        'category', 'assigned_to'
    )

    search_query   = request.GET.get('search', '').strip()
    status_filter  = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')
    urgency_filter = request.GET.get('urgency', '')
    date_from      = request.GET.get('date_from', '')
    date_to        = request.GET.get('date_to', '')
    sort_by        = request.GET.get('sort', '-created_at')

    if search_query:
        tickets = tickets.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query))
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    if category_filter:
        tickets = tickets.filter(category_id=category_filter)
    if urgency_filter:
        tickets = tickets.filter(urgency_level=urgency_filter)

    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            tickets = tickets.filter(created_at__gte=date_from_obj)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            tickets = tickets.filter(created_at__lt=date_to_obj + timedelta(days=1))
        except ValueError:
            pass

    if sort_by in ['-created_at', 'created_at', '-urgency_level', 'urgency_level']:
        tickets = tickets.order_by(sort_by)
    else:
        tickets = tickets.order_by('-created_at')

    categories = Category.objects.filter(is_active=True)
    all_tickets = Ticket.objects.filter(created_by=request.user)

    context = {
        'tickets': tickets,
        'categories': categories,
        'pending_count': all_tickets.filter(status='PENDING').count(),
        'in_progress_count': all_tickets.filter(status__in=['IN_PROGRESS', 'INSPECTING', 'WORKING']).count(),
        'completed_count': all_tickets.filter(status__in=['COMPLETED', 'CLOSED']).count(),
        'search_query': search_query,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'urgency_filter': urgency_filter,
        'date_from': date_from,
        'date_to': date_to,
        'sort_by': sort_by,
        'filtered_count': tickets.count(),
    }
    return render(request, 'user/my_tickets.html', context)

# -------------------------------------------------------------------
# รายละเอียด Ticket + อัปเดตโดยช่าง ได้แล้ว
# -------------------------------------------------------------------
@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(
        Ticket.objects.select_related('category', 'created_by', 'assigned_to'),
        id=ticket_id
    )

    # สิทธิ์เข้าถึง
    if ticket.created_by != request.user and getattr(request.user, 'role', None) not in ['admin', 'technician']:
        messages.error(request, 'คุณไม่มีสิทธิ์เข้าถึง Ticket นี้')
        return redirect('tickets:my_tickets')

    # ฝั่งช่างอัปโหลด AFTER / อัปเดตสถานะ / ส่งงาน
    if request.method == 'POST' and getattr(request.user, 'role', None) == 'technician' and ticket.assigned_to == request.user:
        action = request.POST.get('action')

        # อัปโหลดรูป AFTER
        if request.FILES.get('after_photo'):
            after_photo_file = request.FILES['after_photo']
            try:
                optimized = resize_and_compress(after_photo_file, max_width=1600, max_height=1600, quality=80)
            except Exception:
                optimized = after_photo_file

            # ให้มี AFTER ล่าสุดเพียงรูปเดียว (พฤติกรรมเดิม)
            old_after = ticket.before_after_photos.filter(photo_type='AFTER').first()
            if old_after:
                old_after.delete()

            BeforeAfterPhoto.objects.create(
                ticket=ticket,
                photo_type='AFTER',
                image=optimized,
                uploaded_by=request.user,
            )
            messages.success(request, 'อัปโหลดรูป AFTER สำเร็จ')

        if action == 'update_status':
            new_status = request.POST.get('new_status')
            comment = request.POST.get('comment', '').strip()

            if new_status and new_status != ticket.status:
                ticket.status = new_status
                ticket.save()

                TicketStatusHistory.objects.create(
                    ticket=ticket,
                    status=new_status,
                    changed_by=request.user,
                    note=comment if comment else f'เปลี่ยนสถานะเป็น {ticket.get_status_display()}',
                )
                messages.success(request, f'อัปเดตสถานะเป็น "{ticket.get_status_display()}" สำเร็จ')
            else:
                if not new_status:
                    messages.warning(request, 'กรุณาเลือกสถานะใหม่')
                else:
                    messages.info(request, 'สถานะไม่เปลี่ยนแปลง')

        elif action == 'submit_work':
            # ต้องมี AFTER อย่างน้อย 1 รูป
            after_photo_exists = ticket.before_after_photos.filter(photo_type='AFTER').exists()
            if not after_photo_exists:
                messages.error(request, 'ต้องอัปโหลดรูป AFTER ก่อนส่งงาน')
            else:
                ticket.status = 'COMPLETED'
                ticket.completed_at = timezone.now()
                ticket.save()

                comment = request.POST.get('comment', '').strip()
                TicketStatusHistory.objects.create(
                    ticket=ticket,
                    status='COMPLETED',
                    changed_by=request.user,
                    note=comment if comment else 'ส่งงานเสร็จสิ้น',
                )
                messages.success(request, 'ส่งงานสำเร็จ! สถานะเปลี่ยนเป็น "เสร็จสิ้น"')

        return redirect('tickets:ticket_detail', ticket_id=ticket.id)

    # แสดงผล
    history = ticket.status_histories.order_by('created_at')  # related_name ปัจจุบัน
    attachments = ticket.attachments.all()

    before_after_photos = ticket.before_after_photos.all()
    before_photo = before_after_photos.filter(photo_type='BEFORE').first()
    after_photo = before_after_photos.filter(photo_type='AFTER').first()

    context = {
        'ticket': ticket,
        'history': history,
        'attachments': attachments,
        'before_photo': before_photo,
        'after_photo': after_photo,
    }
    return render(request, 'user/ticket_detail.html', context)


# -------------------------------------------------------------------
# แก้ไข Ticket (เฉพาะ PENDING) ได้แล้ว
# -------------------------------------------------------------------
@login_required
def edit_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id, created_by=request.user)

    if ticket.status != 'PENDING':
        messages.error(request, 'สามารถแก้ไขได้เฉพาะ Ticket ที่มีสถานะ "รอดำเนินการ" เท่านั้น')
        return redirect('tickets:ticket_detail', ticket_id=ticket_id)

    if request.method == 'POST':
        form = TicketForm(request.POST, request.FILES, instance=ticket)
        if form.is_valid():
            updated_ticket = form.save()
            TicketStatusHistory.objects.create(
                ticket=updated_ticket,
                status=updated_ticket.status,
                changed_by=request.user,
                note=f'แก้ไขข้อมูล Ticket โดย {request.user.get_display_name()}',
            )
            messages.success(request, 'แก้ไข Ticket สำเร็จ')
            return redirect('tickets:ticket_detail', ticket_id=ticket_id)
    else:
        form = TicketForm(instance=ticket)

    categories = Category.objects.filter(is_active=True)
    context = {'form': form, 'ticket': ticket, 'categories': categories}
    return render(request, 'user/edit_ticket.html', context)


# -------------------------------------------------------------------
# ยกเลิก Ticket ได้แล้ว
# -------------------------------------------------------------------
@login_required
def cancel_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id, created_by=request.user)

    if ticket.status not in ['PENDING', 'IN_PROGRESS', 'INSPECTING', 'WORKING']:
        messages.error(request, 'ไม่สามารถยกเลิก Ticket ที่มีสถานะนี้ได้')
        return redirect('tickets:ticket_detail', ticket_id=ticket_id)

    if request.method == 'POST':
        assigned_tech = ticket.assigned_to
        ticket.status = 'REJECTED'
        ticket.reject_reason = f'ยกเลิกโดยผู้แจ้ง: {request.POST.get("reason", "ไม่ระบุเหตุผล")}'
        ticket.assigned_to = None
        ticket.save()

        TicketStatusHistory.objects.create(
            ticket=ticket,
            status='REJECTED',
            changed_by=request.user,
            note=ticket.reject_reason,
        )

        messages.success(request, f'ยกเลิก Ticket #{ticket.id} สำเร็จ')
        if assigned_tech:
            messages.info(request, f'ได้ทำการแจ้งช่าง {assigned_tech.get_display_name()} แล้ว')

        return redirect('tickets:my_tickets')

    return render(request, 'user/cancel_ticket.html', {'ticket': ticket})
