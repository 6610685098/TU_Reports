"""
Management command to create 20 dummy tickets with fake images
Usage: python manage.py create_dummy_tickets
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone
from tickets.models import Ticket, Category, TicketStatusHistory, BeforeAfterPhoto
import random
import requests
from io import BytesIO
from datetime import timedelta

User = get_user_model()


class Command(BaseCommand):
    help = 'Create 20 dummy tickets with fake images from placeholder service'

    def handle(self, *args, **kwargs):
        self.stdout.write('Creating 20 dummy tickets...')

        try:
            admin = User.objects.filter(role='admin').first()
            users = list(User.objects.filter(role='user')[:5])
            technicians = list(User.objects.filter(role='technician'))

            if not users:
                self.stdout.write(self.style.ERROR('No users found. Please create users first.'))
                return

            if not technicians:
                self.stdout.write(self.style.WARNING('No technicians found. Tickets will be unassigned.'))
                technicians = [None]

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error fetching users: {e}'))
            return

        categories = list(Category.objects.filter(is_active=True))
        if not categories:
            self.stdout.write(self.style.ERROR('No categories found. Please create categories first.'))
            return

        titles = [
            "ไฟหน้าห้อง A301",
            "ท่อน้ำรั่ว ห้องน้ำชั้น 3",
            "ประตูห้องเรียน ชำรุด",
            "เครื่องปรับอากาศชำรุด",
            "สัญญาณ WiFi ช้า",
            "โปรเจคเตอร์ไม่ทำงาน",
            "ห้องน้ำตันและเหม็น",
            "พัดลมเพดานส่งเสียงดัง",
            "ม่านห้องเรียนหลุด",
            "เก้าอี้ขาหัก",
            "ห้องน้ำไฟไม่ติด",
            "โต๊ะชำรุด",
            "หลอดไฟกระพริบ",
            "แอร์รั่ว",
            "ปลั๊กไฟไม่ทำงาน",
            "โปรเจคเตอร์เบลอภาพไม่ชัด",
            "กระจกหน้าต่างร้าว",
            "หลอดไฟหน้าโรงอาหารขาด",
            "หนูมีในห้องประชุม",
            "พื้นแตก"
        ]

        descriptions = [
            "ไฟหน้าห้องเรียนไม่ติด ต้องเปลี่ยนหลอด",
            "ท่อน้ำรั่วมีน้ำไหลซึมออกมาเรื่อยๆ",
            "ประตูห้องเรียน ลูกบิดหลุด ปิดไม่สนิท",
            "เครื่องปรับอากาศเปิดไม่ติด ไม่มีลมเย็น",
            "สัญญาณ WiFi อ่อนมาก ใช้งานไม่ได้",
            "โปรเจคเตอร์เปิดไม่ติด เสียงดัง ไม่มีภาพ",
            "ห้องน้ำตัน น้ำไหลไม่ลง มีกลิ่นเหม็น",
            "พัดลมเพดานส่งเสียงดังมาก หมุนช้า",
            "ม่านห้องเรียนหลุด ห้อยลงมา",
            "เก้าอี้ขาหัก ไม่สามารถนั่งได้ เสี่ยงอันตราย",
            "ห้องน้ำไฟไม่ติด มืดมาก",
            "โต๊ะชำรุดผิวสึก กระจกแตก",
            "หลอดไฟกระพริบ อาจจะหลุด ต้องเปลี่ยน",
            "แอร์รั่ว น้ำหยดลงมา",
            "ปลั๊กไฟไม่ทำงาน ชาร์จไม่ได้",
            "โปรเจคเตอร์เบลอ ภาพไม่ชัด ต้องซ่อม",
            "กระจกหน้าต่างร้าว อันตราย",
            "หลอดไฟหน้าโรงอาหารขาด มืดมาก",
            "หนูมีในห้องประชุม พบเจอทุกวัน",
            "พื้นแตกมีรอยร้าว เป็นอันตราย"
        ]

        statuses = ['PENDING', 'IN_PROGRESS', 'INSPECTING', 'WORKING', 'COMPLETED', 'CLOSED']
        urgencies = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

        base_lat = 14.0703
        base_lng = 100.6034

        created_count = 0

        for i in range(20):
            try:
                title = titles[i]
                description = descriptions[i]
                category = random.choice(categories)
                created_by = random.choice(users) if users else admin
                assigned_to = random.choice(technicians) if technicians and technicians[0] else None
                status = random.choice(statuses)
                urgency = random.choice(urgencies)

                lat = base_lat + random.uniform(-0.01, 0.01)
                lng = base_lng + random.uniform(-0.01, 0.01)
                days_ago = random.randint(0, 30)
                created_at = timezone.now() - timedelta(days=days_ago)

                ticket = Ticket.objects.create(
                    title=title,
                    description=description,
                    category=category,
                    created_by=created_by,
                    assigned_to=assigned_to,
                    latitude=lat,
                    longitude=lng,
                    address_description=f"อาคาร {random.choice(['A', 'B', 'C', 'D', 'E'])} ชั้น {random.randint(1, 5)} ห้อง {random.randint(101, 599)}",
                    urgency_level=urgency,
                    status=status,
                    priority_score=random.uniform(0, 100),
                    created_at=created_at,
                    completed_at=timezone.now() if status in ['COMPLETED', 'CLOSED'] else None
                )

                TicketStatusHistory.objects.create(
                    ticket=ticket,
                    old_status='',
                    new_status='PENDING',
                    changed_by=created_by,
                    comment='สร้าง Ticket ใหม่',
                    timestamp=created_at
                )

                if status != 'PENDING' and assigned_to:
                    TicketStatusHistory.objects.create(
                        ticket=ticket,
                        old_status='PENDING',
                        new_status='IN_PROGRESS',
                        changed_by=assigned_to,
                        comment='รับงาน',
                        timestamp=created_at + timedelta(hours=random.randint(1, 6))
                    )

                if status in ['INSPECTING', 'WORKING', 'COMPLETED', 'CLOSED'] and assigned_to:
                    TicketStatusHistory.objects.create(
                        ticket=ticket,
                        old_status='IN_PROGRESS',
                        new_status=status,
                        changed_by=assigned_to,
                        comment=f'เปลี่ยนสถานะเป็น {ticket.get_status_display()}',
                        timestamp=created_at + timedelta(hours=random.randint(6, 24))
                    )

                try:
                    before_url = f"https://via.placeholder.com/800x600.png?text=Before+Photo+{i+1}"
                    response = requests.get(before_url, timeout=10)

                    if response.status_code == 200:
                        before_image = ContentFile(response.content, name=f'before_{ticket.id}.png')
                        BeforeAfterPhoto.objects.create(
                            ticket=ticket,
                            photo_type='BEFORE',
                            image=before_image,
                            uploaded_by=created_by,
                            file_size=len(response.content)
                        )
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Could not download before image for ticket {ticket.id}: {e}'))

                if status in ['COMPLETED', 'CLOSED'] and assigned_to:
                    try:
                        after_url = f"https://via.placeholder.com/800x600.png?text=After+Photo+{i+1}"
                        response = requests.get(after_url, timeout=10)

                        if response.status_code == 200:
                            after_image = ContentFile(response.content, name=f'after_{ticket.id}.png')
                            BeforeAfterPhoto.objects.create(
                                ticket=ticket,
                                photo_type='AFTER',
                                image=after_image,
                                uploaded_by=assigned_to,
                                file_size=len(response.content)
                            )
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'Could not download after image for ticket {ticket.id}: {e}'))

                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'[OK] Created ticket #{ticket.id}: {title}'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error creating ticket {i+1}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'\nDone! Created {created_count}/20 dummy tickets.'))