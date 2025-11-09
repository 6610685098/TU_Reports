from django.core.management.base import BaseCommand
from authentication.models import User
from tickets.models import Category, Ticket, TechnicianPresence
import random


class Command(BaseCommand):
    help = 'Create demo data for testing'

    def handle(self, *args, **options):
        self.stdout.write('Creating demo data...')

        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'role': 'admin',
                'displayname_th': 'ผู้ดูแลระบบ',
                'is_staff': True,
                'is_superuser': True
            }
        )
        admin.set_password('admin123')
        admin.save()
        if created:
            self.stdout.write(self.style.SUCCESS(' Created admin user'))

        techs = []
        for i in range(1, 6):
            tech, created = User.objects.get_or_create(
                username=f'tech00{i}',
                defaults={
                    'role': 'technician',
                    'displayname_th': f'ช่าง {i}',
                }
            )
            tech.set_password('tech123')
            tech.save()

            TechnicianPresence.objects.get_or_create(
                technician=tech,
                defaults={
                    'latitude': 14.070 + (i * 0.001),
                    'longitude': 100.605 + (i * 0.001),
                    'is_available': True
                }
            )

            techs.append(tech)
            if created:
                self.stdout.write(self.style.SUCCESS(f' Created technician: tech00{i}'))

        users = []
        for i in range(1, 4):
            user, created = User.objects.get_or_create(
                username=f'user00{i}',
                defaults={
                    'role': 'user',
                    'displayname_th': f'ผู้ใช้ {i}',
                }
            )
            user.set_password('user123')
            user.save()
            users.append(user)
            if created:
                self.stdout.write(self.style.SUCCESS(f' Created user: user00{i}'))

        categories_data = [
            {'name': 'ไฟฟ้า', 'icon': 'bolt', 'color': 'yellow'},
            {'name': 'ประปา', 'icon': 'droplet', 'color': 'blue'},
            {'name': 'IT/คอมพิวเตอร์', 'icon': 'laptop', 'color': 'purple'},
            {'name': 'แอร์/ระบายอากาศ', 'icon': 'wind', 'color': 'cyan'},
            {'name': 'อาคาร/โครงสร้าง', 'icon': 'building', 'color': 'gray'},
        ]

        for cat_data in categories_data:
            cat, created = Category.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'icon': cat_data['icon'],
                    'color': cat_data['color'],
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f' Created category: {cat.name}'))

        categories = list(Category.objects.all())
        if categories:
            urgency_levels = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

            for i in range(10):
                ticket = Ticket.objects.create(
                    title=f'ตัวอย่างปัญหา #{i+1}',
                    description=f'รายละเอียดปัญหาตัวอย่างที่ {i+1}',
                    category=random.choice(categories),
                    created_by=random.choice(users),
                    urgency_level=random.choice(urgency_levels),
                    latitude=14.070 + random.uniform(-0.01, 0.01),
                    longitude=100.605 + random.uniform(-0.01, 0.01),
                    address_description=f'อาคาร {random.choice(["A", "B", "C", "D"])} ชั้น {random.randint(1,5)} ห้อง {random.randint(100,500)}'
                )
                self.stdout.write(self.style.SUCCESS(f' Created sample ticket: {ticket.title}'))

        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('Demo data created successfully!'))
        self.stdout.write('='*50)
        self.stdout.write('\nTest Accounts:')
        self.stdout.write('  Admin:      admin / admin123')
        self.stdout.write('  Technician: tech001-tech005 / tech123')
        self.stdout.write('  User:       user001-user003 / user123')
        self.stdout.write('\nTU API Mock Accounts:')
        self.stdout.write('  Student:    student001 / student123')
        self.stdout.write('  Personnel:  personnel001 / personnel123')
        self.stdout.write('='*50 + '\n')
