# tickets/signals.py
from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate, post_save, pre_save
from django.dispatch import receiver

from .models import Ticket, TechnicianPresence

User = get_user_model()

@receiver(post_migrate)
def ensure_presences_on_migrate(sender, **kwargs):
    """
    หลัง migrate เสร็จ: สร้าง TechnicianPresence ให้ช่างทุกคนที่ active
    (กันเคสเครื่องใหม่ดึงโค้ดแล้วไม่มี presence -> auto-assign ไม่ทำงาน)
    """
    # ทำเฉพาะตอน migrate แอป tickets
    app_label = getattr(sender, "label", None) or getattr(sender, "name", None)
    if app_label != "tickets":
        return

    for u in User.objects.filter(is_active=True, role__iexact="technician"):
        TechnicianPresence.objects.get_or_create(technician=u, defaults={
            "is_available": True,
            # ไม่จำเป็นต้องใส่ lat/lon ตั้งต้น หากโมเดลอนุญาตให้เป็น null/blank
        })

@receiver(post_save, sender=User)
def ensure_presence_on_user_save(sender, instance, **kwargs):
    """
    เมื่อมีการสร้าง/แก้ไข User: ถ้าเป็นช่างที่ active ให้มี presence เสมอ
    """
    if getattr(instance, "role", "").lower() == "technician" and instance.is_active:
        TechnicianPresence.objects.get_or_create(technician=instance)

@receiver(pre_save, sender=Ticket)
def fill_department_name_on_ticket(sender, instance: Ticket, **kwargs):
    """
    ก่อนบันทึก Ticket: เติม department_name จากผู้แจ้ง (created_by)
    หากฟิลด์ยังว่างอยู่
    """
    if not getattr(instance, "department_name", None):
        created_by = getattr(instance, "created_by", None)
        dep = getattr(created_by, "department", None) if created_by else None
        if dep:
            instance.department_name = dep
