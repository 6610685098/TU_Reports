# tickets/admin.py
from django.contrib import admin
from .models import (
    Category, Department, Ticket, TechnicianPresence,
    AssignmentRule, TicketStatusHistory, Attachment,
    BeforeAfterPhoto, 
)

# ---------- Category / Department ----------
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "color", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)

# ---------- Ticket ----------
@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "id", "title", "category", "status", "urgency_level",
        "created_by", "assigned_to", "created_at"
    )
    list_filter = ("status", "urgency_level", "category", "created_at")
    search_fields = ("title", "description", "id")
    readonly_fields = ("created_at", "updated_at", "priority_score")
    date_hierarchy = "created_at"
    fieldsets = (
        ("ข้อมูลพื้นฐาน", {
            "fields": ("title", "description", "category")
        }),
        ("ผู้รับผิดชอบ", {
            "fields": ("created_by", "assigned_to")
        }),
        ("พิกัด/ที่อยู่", {
            "fields": ("latitude", "longitude", "address_description")
        }),
        ("เร่งด่วน/สถานะ", {
            "fields": ("urgency_level", "priority_score", "status", "reject_reason")
        }),
        ("เวลา", {
            "fields": ("created_at", "updated_at", "completed_at")
        }),
    )

# ---------- Technician Presence ----------
@admin.register(TechnicianPresence)
class TechnicianPresenceAdmin(admin.ModelAdmin):
    list_display = ("technician", "is_available", "updated_at", "latitude", "longitude")
    list_filter = ("is_available",)
    search_fields = ("technician__username", "technician__first_name", "technician__last_name")

# ---------- Assignment Rule ----------
@admin.register(AssignmentRule)
class AssignmentRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "max_open_tickets", "weight_distance", "weight_workload", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)

# ---------- Ticket Status History ----------
@admin.register(TicketStatusHistory)
class TicketStatusHistoryAdmin(admin.ModelAdmin):
    # ใช้ฟิลด์จริงในโมเดล: status, note, changed_by, created_at
    list_display = ("ticket", "status", "changed_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("ticket__id", "ticket__title", "changed_by__username")
    date_hierarchy = "created_at"

# ---------- Attachments ----------
@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "ticket", "uploaded_by", "uploaded_at")
    list_filter = ("uploaded_at",)
    search_fields = ("ticket__id", "ticket__title", "uploaded_by__username")
    date_hierarchy = "uploaded_at"

# ---------- Before/After Photos ----------
@admin.register(BeforeAfterPhoto)
class BeforeAfterPhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "ticket", "photo_type", "uploaded_by", "created_at")
    list_filter = ("photo_type", "created_at")
    search_fields = ("ticket__id", "ticket__title", "uploaded_by__username")
    date_hierarchy = "created_at"

