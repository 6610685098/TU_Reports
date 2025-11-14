# tickets/management/commands/bootstrap_demo_data.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal

class Command(BaseCommand):
    help = "Create demo users and seed technician presence."

    def handle(self, *args, **options):
        from tickets.models import TechnicianPresence

        User = get_user_model()

        # 1) สร้างช่าง demo ถ้ายังไม่มี
        usernames = ["tech1", "tech2", "tech3", "tech4", "tech5"]
        users_created = 0
        for i, uname in enumerate(usernames, start=1):
            u, created = User.objects.get_or_create(
                username=uname,
                defaults={
                    "role": "technician",
                    "is_active": True,
                    # ตั้ง dept ให้บางคน เพื่อใช้ร่วมกับ auto-dispatch ตาม department
                    "department": "งานบริการเทคนิค" if i in (1, 4) else None,
                },
            )
            if created:
                u.set_password("pass1234")
                u.save(update_fields=["password"])
                users_created += 1

        # 2) สร้าง/การันตี TechnicianPresence ให้ช่างทุกคน
        DEFAULT_LAT = Decimal("14.0730")
        DEFAULT_LON = Decimal("100.6060")

        techs = User.objects.filter(role__iexact="technician", is_active=True)
        presence_created = 0
        for u in techs:
            _, created = TechnicianPresence.objects.get_or_create(
                technician=u,
                defaults={
                    "is_available": True,
                    "latitude": DEFAULT_LAT,
                    "longitude": DEFAULT_LON,
                },
            )
            if created:
                presence_created += 1

        # 3) สรุปผล
        self.stdout.write(
            self.style.SUCCESS(
                f"bootstrap_demo_data: users_created={users_created}, presence_created={presence_created}"
            )
        )
