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
            }
        )
        if created:
            admin_user.set_password("admin1234")
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("  [+] Created admin user: admin / admin1234"))

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
        
        categories = []
        cat_created = 0
        for name in default_categories:
            cat, created = Category.objects.get_or_create(name=name)
            categories.append(cat)
            if created:
                cat_created += 1

        # 4) Generate Mock Tickets (50+ items)
        from tickets.models import Ticket
        import random
        from django.utils import timezone
        from datetime import timedelta

        # Ensure we have some student users for 'created_by'
        student_usernames = ["student001", "student002", "staff001", "staff002"]
        students = []
        for uname in student_usernames:
            u, _ = User.objects.get_or_create(username=uname, defaults={"role": "user", "is_active": True})
            if _: u.set_password("pass1234"); u.save()
            students.append(u)

        existing_tickets_count = Ticket.objects.count()
        
        if existing_tickets_count < 50:
            target_count = 50 - existing_tickets_count
            self.stdout.write(f"  [+] Generating {target_count} mock tickets...")

            titles = [
                "ไฟดับ", "แอร์ไม่เย็น", "น้ำรั่ว", "เน็ตหลุด", "คอมเปิดไม่ติด", 
                "ก๊อกน้ำหัก", "เปลี่ยนหลอดไฟ", "ทำความสะอาด", "ประตูพัง", "หน้าต่างแตก",
                "ขอรหัส Wifi", "ปริ้นเตอร์พัง", "โปรเจคเตอร์ดับ", "ลิฟต์ค้าง", "ท่อตัน"
            ]
            locations = [
                "ตึก SC ชั้น 1", "ตึก SC ชั้น 2", "ตึก SC ชั้น 3", 
                "ตึก วิดวะ ชั้น 1", "ตึก วิดวะ ชั้น 4", 
                "โรงอาหารกลาง", "ห้องสมุด", "อาคารเรียนรวม 3"
            ]
            statuses = ['PENDING', 'IN_PROGRESS', 'INSPECTING', 'WORKING', 'COMPLETED', 'CLOSED', 'REJECTED']

            for _ in range(target_count):
                # Randomize date within last 30 days
                days_ago = random.randint(0, 30)
                created_at = timezone.now() - timedelta(days=days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59))
                
                status = random.choice(statuses)
                assigned_to = None
                
                # Assign logic based on status
                if status in ['IN_PROGRESS', 'INSPECTING', 'WORKING', 'COMPLETED', 'CLOSED']:
                    assigned_to = random.choice(techs) if techs else None

                ticket = Ticket.objects.create(
                    title=f"{random.choice(titles)} - {random.randint(100,999)}",
                    description="ทดสอบระบบ Mock Data สำหรับ Analytics Dashboard",
                    category=random.choice(categories),
                    urgency_level=random.choice(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']),
                    address_description=random.choice(locations),
                    status=status,
                    created_by=random.choice(students),
                    assigned_to=assigned_to
                )
                
                # Mock created_at (Django auto_now_add makes it read-only on create, need update)
                ticket.created_at = created_at
                ticket.save(update_fields=['created_at'])

        self.stdout.write(
            self.style.SUCCESS(
                f"bootstrap_demo_data: users_created={users_created}, "
                f"presence_created={presence_created}, presence_existing={presence_existing}, "
                f"categories_created={cat_created}, tickets_total={Ticket.objects.count()}"
            )
        )
