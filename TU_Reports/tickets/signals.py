# tickets/signals.py
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from .models import TechnicianPresence

User = get_user_model()

def _is_technician(user):
    role = (getattr(user, "role", "") or "")
    return role.casefold() == "technician"

def _presence_defaults():
    return {
        "is_available": getattr(settings, "TECH_DEFAULT_AVAILABLE", True),
        "latitude":  getattr(settings, "TECH_DEFAULT_LAT", Decimal("14.0730")),
        "longitude": getattr(settings, "TECH_DEFAULT_LON", Decimal("100.6060")),
    }

def ensure_presence_for_queryset(qs):
    """
    สร้าง TechnicianPresence ให้ user ใน queryset ที่ยังไม่มี
    """
    existing_ids = set(
        TechnicianPresence.objects.filter(technician__in=qs).values_list("technician_id", flat=True)
    )
    to_create = []
    for u in qs:
        if u.id not in existing_ids:
            to_create.append(
                TechnicianPresence(technician=u, **_presence_defaults())
            )
    if to_create:
        TechnicianPresence.objects.bulk_create(to_create, ignore_conflicts=True)
    return len(to_create)

@receiver(post_migrate)
def create_presence_after_migrate(sender, **kwargs):
    """หลัง migrate ของโปรเจ็กต์ ให้แน่ใจว่าช่างทุกคนมี presence"""
    try:
        tech_qs = User.objects.filter(is_active=True)
        tech_qs = [u for u in tech_qs if _is_technician(u)]
        ensure_presence_for_queryset(tech_qs)
    except Exception:
        # อย่าให้การ migrate พังเพราะสัญญาณ
        pass

@receiver(post_save, sender=User)
def ensure_presence_on_user_save(instance, created, **kwargs):
    """ทุกครั้งที่มีการสร้าง/อัปเดต User: ถ้าเป็นช่างและ active ให้ ensure presence"""
    try:
        if instance.is_active and _is_technician(instance):
            TechnicianPresence.objects.get_or_create(
                technician=instance,
                defaults=_presence_defaults()
            )
    except Exception:
        # ไม่ให้การบันทึก user พังเพราะสัญญาณ
        pass


@receiver(post_migrate)
def ensure_presence_after_migrate(sender, **kwargs):
    # ทำงานเฉพาะตอน migrate ของโปรเจกต์ (ไม่รันตอนทดสอบ third-party app)
    app_label = getattr(sender, "label", None) or getattr(sender, "__name__", "")
    if not app_label or not app_label.startswith(("tickets", "authentication", "technician", "dashboard")):
        return

    from tickets.models import TechnicianPresence

    User = get_user_model()
    techs = User.objects.filter(role__iexact="technician", is_active=True)

    DEFAULT_LAT = Decimal("14.0730")
    DEFAULT_LON = Decimal("100.6060")

    for u in techs:
        TechnicianPresence.objects.get_or_create(
            technician=u,
            defaults={
                "is_available": True,
                "latitude": DEFAULT_LAT,
                "longitude": DEFAULT_LON,
            },
        )