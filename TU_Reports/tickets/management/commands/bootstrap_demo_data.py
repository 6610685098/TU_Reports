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
        usernames = ["tech1", "tech2", "tech3", "tech4", "tech5"]
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
            u.set_password("tech123")
            u.save(update_fields=["password"])
            if created:

                users_created += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  [+] Created user: {uname} / tech123")
                )

        # 1.5) Create Admin User
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "role": "admin",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
                "department": "IT Support",
                "displayname_th": "ผู้ดูแลระบบ",
            },
        )
        if created:
            admin_user.set_password("admin1234")
            admin_user.save()
            self.stdout.write(
                self.style.SUCCESS("  [+] Created admin user: admin / admin1234")
            )

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
            "ไฟฟ้า",  # Electrical
            "ประปา",  # Plumbing/Water
            "แอร์ / ปรับอากาศ",  # HVAC
            "อินเทอร์เน็ต / เครือข่าย",  # Network
            "คอมพิวเตอร์ / อุปกรณ์",  # IT/Hardware
            "อาคาร / โครงสร้าง",  # Building/Structure
            "ความสะอาด / สิ่งแวดล้อม",  # Cleaning/Environment
        ]

        categories = []
        cat_created = 0
        for name in default_categories:
            cat, created = Category.objects.get_or_create(name=name)
            categories.append(cat)
            if created:
                cat_created += 1
                self.stdout.write(self.style.SUCCESS(f"  [+] Created category: {name}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"bootstrap_demo_data: users_created={users_created}, "
                f"presence_created={presence_created}, presence_existing={presence_existing}, "
                f"categories_created={cat_created}"
            )
        )
