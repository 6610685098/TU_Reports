# tickets/management/commands/bootstrap_demo_data.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal

class Command(BaseCommand):
    help = "Create demo users, ensure TechnicianPresence and default Categories."

    def add_arguments(self, parser):
        parser.add_argument("--reset-presence", action="store_true")

    def handle(self, *args, **options):
        from tickets.models import TechnicianPresence, Category
        User = get_user_model()

        # 1) สร้าง/อัปเดตผู้ใช้ช่างเดโม่
        usernames = ["tech1","tech2","tech3","tech4","tech5"]
        users_created = 0
        for i, uname in enumerate(usernames, start=1):
            u, created = User.objects.get_or_create(
                username=uname,
                defaults={
                    "role": "technician",
                    "is_active": True,
                    "department": "งานบริการเทคนิค" if i in (1, 4) else None,
                },
            )
            if created:
                u.set_password("pass1234")
                u.save(update_fields=["password"])
                users_created += 1

        # 2) Ensure TechnicianPresence สำหรับทุกช่าง
        DEFAULT_LAT = Decimal("14.0730")
        DEFAULT_LON = Decimal("100.6060")

        techs = User.objects.filter(role__iexact="technician", is_active=True)
        presence_created = 0
        presence_existing = 0
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
            else:
                presence_existing += 1

        if options.get("reset_presence"):
            TechnicianPresence.objects.update(is_available=True)

        # 3) สร้างหมวดหมู่เริ่มต้น (idempotent)
        default_categories = [
            "ไฟฟ้า",              # Electrical
            "ประปา",              # Plumbing/Water
            "แอร์ / ปรับอากาศ",   # HVAC
            "อินเทอร์เน็ต / เครือข่าย", # Network
            "คอมพิวเตอร์ / อุปกรณ์",    # IT/Hardware
            "อาคาร / โครงสร้าง",  # Building/Structure
            "ความสะอาด / สิ่งแวดล้อม",  # Cleaning/Environment
        ]
        cat_created = 0
        for name in default_categories:
            _, created = Category.objects.get_or_create(name=name)
            if created:
                cat_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"bootstrap_demo_data: users_created={users_created}, "
                f"presence_created={presence_created}, presence_existing={presence_existing}, "
                f"categories_created={cat_created}"
            )
        )
