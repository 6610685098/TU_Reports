from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import random
from decimal import Decimal
from tickets.models import Ticket, Category

class Command(BaseCommand):
    help = "Generate random mock tickets for testing (Requires bootstrap_demo_data first)"

    def handle(self, *args, **options):
        User = get_user_model()
        
        # 1. ดึงข้อมูลพื้นฐาน
        categories = list(Category.objects.all())
        techs = list(User.objects.filter(role__iexact="technician", is_active=True))

        if not categories:
            self.stdout.write(self.style.ERROR("ไม่พบ Category! กรุณารัน 'python manage.py bootstrap_demo_data' ก่อน"))
            return

        # 2. เตรียม User ผู้แจ้ง (Requesters)
        requester_usernames = ["student001", "student002", "staff001", "staff002"]
        requesters = []
        for uname in requester_usernames:
            u, created = User.objects.get_or_create(
                username=uname, 
                defaults={
                    "role": "user", 
                    "is_active": True,
                    "displayname_th": f"ผู้แจ้ง {uname}"
                }
            )
            u.set_password("pass1234")
            u.save()
            requesters.append(u)
            self.stdout.write(
                self.style.SUCCESS(f"  [+] Ensured requester user: {uname} / pass1234")
            )

        # 3. ตรวจสอบจำนวน Ticket
        existing_tickets_count = Ticket.objects.count()
        target_total = 50
        
        if existing_tickets_count >= target_total:
            self.stdout.write(self.style.WARNING(f"Tickets already exist ({existing_tickets_count}). Skipping generation."))
            return

        amount_to_create = target_total - existing_tickets_count
        self.stdout.write(f"  [+] Generating {amount_to_create} mock tickets with Lat/Long...")

        titles = [
            "ไฟดับ", "แอร์ไม่เย็น", "น้ำรั่ว", "เน็ตหลุด", 
            "คอมเปิดไม่ติด", "ก๊อกน้ำหัก", "เปลี่ยนหลอดไฟ", 
            "ทำความสะอาด", "ประตูพัง", "หน้าต่างแตก", 
            "ขอรหัส Wifi", "ปริ้นเตอร์พัง", "โปรเจคเตอร์ดับ", 
            "ลิฟต์ค้าง", "ท่อตัน", "เหม็นกลิ่นไหม้"
        ]
        
        locations = [
            "ตึก SC ชั้น 1", "ตึก SC ชั้น 2", "ตึก SC ชั้น 3", 
            "ตึก วิดวะ ชั้น 1", "ตึก วิดวะ ชั้น 4", 
            "โรงอาหารกลาง", "ห้องสมุด", "อาคารเรียนรวม 3", 
            "หอพักนักศึกษา โซน B"
        ]
        
        statuses = [
            "PENDING", "IN_PROGRESS", "INSPECTING", 
            "WORKING", "COMPLETED", "CLOSED", "REJECTED"
        ]

        # พิกัดกลาง (อิงจาก bootstrap_demo_data)
        BASE_LAT = 14.070491
        BASE_LON = 100.606447

        for i in range(amount_to_create):
            days_ago = random.randint(0, 30)
            created_at = timezone.now() - timedelta(
                days=days_ago,
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )

            status = random.choice(statuses)
            assigned_to = None

            if status in ["IN_PROGRESS", "INSPECTING", "WORKING", "COMPLETED", "CLOSED"] and techs:
                assigned_to = random.choice(techs)

            # --- ส่วนที่เพิ่ม: สุ่ม Lat/Long ---
            # สุ่มกระจายตัวประมาณ +/- 0.005 องศา (ประมาณ 500 เมตร) รอบจุดกลาง
            lat = BASE_LAT + random.uniform(-0.005, 0.005)
            lon = BASE_LON + random.uniform(-0.005, 0.005)

            ticket = Ticket.objects.create(
                title=f"{random.choice(titles)}",
                description=f"ทดสอบระบบ Mock Data #{i+1} วันที่ {created_at.strftime('%Y-%m-%d')}",
                category=random.choice(categories),
                urgency_level=random.choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
                address_description=random.choice(locations),
                status=status,
                created_by=random.choice(requesters),
                assigned_to=assigned_to,
                latitude=Decimal(f"{lat:.6f}"),   # แปลงเป็น Decimal เพื่อความชัวร์
                longitude=Decimal(f"{lon:.6f}"),  # แปลงเป็น Decimal เพื่อความชัวร์
            )

            ticket.created_at = created_at
            ticket.save(update_fields=["created_at"])

        self.stdout.write(self.style.SUCCESS(f"  [+] Successfully created {amount_to_create} tickets with locations."))