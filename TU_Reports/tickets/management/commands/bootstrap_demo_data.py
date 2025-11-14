# tickets/management/commands/bootstrap_demo_data.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from decimal import Decimal

from tickets.models import TechnicianPresence  # ใช้รุ่น model presence ที่คุณใช้อยู่

class Command(BaseCommand):
    help = "Create default technicians and ensure TechnicianPresence for all technicians."

    def handle(self, *args, **options):
        User = get_user_model()
        created_users = 0
        updated_pw = 0
        created_presence = 0

        # 1) สร้างช่างตาม DEFAULT_TECHNICIANS (ถ้ายังไม่มี)
        for item in getattr(settings, "DEFAULT_TECHNICIANS", []):
            username = item["username"]
            user, u_created = User.objects.get_or_create(
                username=username,
                defaults={
                    "is_active": True,
                    "role": "technician",
                    "displayname_th": item.get("displayname_th") or username,
                    "department": item.get("department"),
                },
            )
            if u_created:
                created_users += 1

            # ตั้งรหัสผ่านเริ่มต้น/รีเซ็ตถ้า user ไม่มี usable password
            if u_created or not user.has_usable_password():
                user.set_password(item.get("password", "tech1234"))
                user.save(update_fields=["password"])
                if not u_created:
                    updated_pw += 1

            # presence สำหรับ user นี้
            lat = item.get("latitude", getattr(settings, "TECH_DEFAULT_LAT", "14.0730"))
            lon = item.get("longitude", getattr(settings, "TECH_DEFAULT_LON", "100.6060"))
            _, p_created = TechnicianPresence.objects.get_or_create(
                technician=user,
                defaults={
                    "is_available": getattr(settings, "TECH_DEFAULT_AVAILABLE", True),
                    "latitude": Decimal(str(lat)),
                    "longitude": Decimal(str(lon)),
                },
            )
            if p_created:
                created_presence += 1

        # 2) กันพลาด: ช่างทุกคนในระบบ ต้องมี presence
        qs_all_techs = User.objects.filter(is_active=True, role__iexact="technician")
        for u in qs_all_techs:
            _, p_created = TechnicianPresence.objects.get_or_create(
                technician=u,
                defaults={
                    "is_available": getattr(settings, "TECH_DEFAULT_AVAILABLE", True),
                    "latitude": Decimal(getattr(settings, "TECH_DEFAULT_LAT", "14.0730")),
                    "longitude": Decimal(getattr(settings, "TECH_DEFAULT_LON", "100.6060")),
                },
            )
            if p_created:
                created_presence += 1

        self.stdout.write(self.style.SUCCESS(
            f"bootstrap_demo_data: users_created={created_users}, passwords_updated={updated_pw}, presence_created={created_presence}"
        ))
