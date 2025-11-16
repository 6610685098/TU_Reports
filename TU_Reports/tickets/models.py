# tickets/models.py
from __future__ import annotations

from decimal import Decimal
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone


# =========================
# หมวดหมู่ / แผนก
# =========================
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=7, default="#3B82F6")  # ex. #3B82F6
    is_active = models.BooleanField(default=True)

    # ใช้ default=timezone.now เพื่อกันปัญหาเวลามีแถวเก่าใน DB
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Department(models.Model):
    # เวอร์ชันสุดท้าย: non-null + unique
    # name = models.CharField(max_length=150, unique=True)  # non-nullable
    name = models.CharField(max_length=150, unique=True, null=True, blank=True)  # ชั่วคราว
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


# =========================
# Ticket หลัก
# =========================
class Ticket(models.Model):
    URGENCY_CHOICES = [
        ("LOW", "ต่ำ"),
        ("MEDIUM", "ปานกลาง"),
        ("HIGH", "สูง"),
        ("CRITICAL", "วิกฤติ"),
    ]
    STATUS_CHOICES = [
        ("PENDING", "รอดำเนินการ"),
        ("IN_PROGRESS", "กำลังดำเนินการ"),
        ("INSPECTING", "ตรวจสอบหน้างาน"),
        ("WORKING", "ลงมือแก้ไข"),
        ("COMPLETED", "เสร็จสิ้น"),
        ("CLOSED", "ปิดงาน"),
        ("REJECTED", "ปฏิเสธงาน"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="tickets",
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets_created",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="tickets_assigned",
        null=True,
        blank=True,
    )

    # พิกัดแทน PointField
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    address_description = models.TextField(blank=True)

    urgency_level = models.CharField(max_length=10, choices=URGENCY_CHOICES, default="MEDIUM")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="PENDING")

    # ให้มีค่าเสมอเมื่อเพิ่มฟิลด์: default=Decimal("0.00")
    priority_score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))

    # ปัญหา non-null ตอนเพิ่มฟิลด์ → ใช้ default='' + ไม่ต้อง null
    reject_reason = models.TextField(blank=True, default="")

    # เวลาต่าง ๆ ใช้ default=timezone.now เพื่อกัน migration prompt
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} - {self.title}"

    def save(self, *args, **kwargs):
        # อัปเดต updated_at อัตโนมัติแบบไม่พึ่ง auto_now (กันปัญหา default ตอนเพิ่มฟิลด์)
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    def mark_completed(self):
        self.status = "COMPLETED"
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])

# =========================
# สถานะความพร้อมของช่าง
# =========================
class TechnicianPresence(models.Model):
    technician = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="presence",
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_available = models.BooleanField(default=True)

    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["technician"]),
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["is_available"]),
        ]

    def __str__(self) -> str:
        return f"{self.technician} @({self.latitude}, {self.longitude})"

    def save(self, *args, **kwargs):
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)


# =========================
# กฎการมอบหมายงาน
# =========================
class AssignmentRule(models.Model):
    name = models.CharField(max_length=120, default="Default Rule")
    is_active = models.BooleanField(default=True)

    max_open_tickets = models.PositiveIntegerField(default=5)
    weight_distance = models.FloatField(default=1.0)
    weight_workload = models.FloatField(default=1.0)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-is_active", "-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({'ACTIVE' if self.is_active else 'inactive'})"

    @classmethod
    def get_active_or_default(cls) -> "AssignmentRule":
        rule = cls.objects.filter(is_active=True).order_by("-created_at").first()
        if rule:
            return rule
        return cls.objects.create(is_active=True)


# =========================
# ประวัติสถานะ Ticket
# =========================
class TicketStatusHistory(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="status_histories")

    # เพิ่มฟิลด์ใหม่ให้ไม่เด้งถาม default: ใส่ default เป็นสถานะเริ่มต้น
    status = models.CharField(max_length=15, choices=Ticket.STATUS_CHOICES, default="PENDING")
    note = models.TextField(blank=True)

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="status_changes",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["ticket", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"Ticket #{self.ticket_id} -> {self.status}"


# =========================
# ไฟล์แนบ / รูปก่อน-หลัง / ฟีดแบ็ก
# =========================
def attachment_upload_to(instance: "Attachment", filename: str) -> str:
    return f"tickets/{instance.ticket_id}/attachments/{filename}"

def photo_upload_to(instance: "BeforeAfterPhoto", filename: str) -> str:
    return f"tickets/{instance.ticket_id}/photos/{instance.photo_type.lower()}/{filename}"


class Attachment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=attachment_upload_to)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"Attachment #{self.pk} of Ticket #{self.ticket_id}"


class BeforeAfterPhoto(models.Model):
    PHOTO_TYPE = [
        ("BEFORE", "ก่อนซ่อม"),
        ("AFTER", "หลังซ่อม"),
    ]
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="before_after_photos")
    photo_type = models.CharField(max_length=6, choices=PHOTO_TYPE)
    image = models.ImageField(upload_to=photo_upload_to)

    # เดิม uploaded_at → เปลี่ยนเป็น created_at แล้ว
    created_at = models.DateTimeField(default=timezone.now)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["ticket", "photo_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.photo_type} of Ticket #{self.ticket_id}"

