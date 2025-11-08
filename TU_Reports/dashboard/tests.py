import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

# Import โมเดลจาก tickets.models โดยใช้ชื่อที่ถูกต้อง
from tickets.models import Ticket, Category, BeforeAfterPhoto, Attachment

# ดึง User model ปัจจุบันของโปรเจกต์มาใช้
User = get_user_model()

class DashboardMapViewTests(TestCase):
    """
    Test suite for the map_view in the dashboard app.
    """

    def setUp(self):
        """
        ตั้งค่าข้อมูลจำลองที่จะใช้ในทุกๆ เทสต์เมธอด
        จะถูกรันใหม่ทุกครั้งก่อนเริ่มเทสต์แต่ละอัน
        """
        self.client = Client()
        self.test_user = User.objects.create_user(
            username='testuser',
            password='testpassword123'
        )
        self.category1 = Category.objects.create(name='ไฟฟ้า', color='#FF0000')
        self.category2 = Category.objects.create(name='ประปา', color='#0000FF')

        # สร้าง Ticket หลัก 4 ใบ
        Ticket.objects.create(
            title='ไฟดับ', status='PENDING', category=self.category1,
            created_by=self.test_user, latitude=13.7, longitude=100.5
        )
        Ticket.objects.create(
            title='แอร์ไม่เย็น', status='IN_PROGRESS', category=self.category1,
            created_by=self.test_user, latitude=13.8, longitude=100.6
        )
        Ticket.objects.create(
            title='ท่อประปาแตก', status='COMPLETED', category=self.category2,
            created_by=self.test_user, latitude=13.9, longitude=100.7
        )
        Ticket.objects.create(
            title='ประตูพัง', status='PENDING', category=self.category2,
            created_by=self.test_user
        )

        # สร้าง Ticket ใบที่ 5 พร้อม Attachment เพื่อทดสอบ fallback image
        ticket_with_attachment = Ticket.objects.create(
            title='ประตูห้องน้ำล็อค', status='PENDING', created_by=self.test_user,
            latitude=13.75, longitude=100.55
        )
        
        # สร้างไฟล์จำลองในหน่วยความจำ
        dummy_file = SimpleUploadedFile("test_attachment.txt", b"file content", content_type="text/plain")
        
        # *** จุดแก้ไขสำคัญ: ใช้ชื่อโมเดลที่ถูกต้อง 'Attachment' ***
        Attachment.objects.create(
            ticket=ticket_with_attachment,
            file=dummy_file,
            uploaded_by=self.test_user
        )

        # สร้างรูป AfterPhoto สำหรับ Ticket 'ไฟดับ'
        ticket_with_photo = Ticket.objects.get(title='ไฟดับ')
        # โมเดล BeforeAfterPhoto ของคุณต้องการ field 'image'
        dummy_image = SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")
        BeforeAfterPhoto.objects.create(
            ticket=ticket_with_photo,
            photo_type='AFTER',
            image=dummy_image,
            uploaded_by=self.test_user
        )
        
        ticket_for_before_photo = Ticket.objects.get(title='แอร์ไม่เย็น')
        dummy_image_before = SimpleUploadedFile("before.jpg", b"content", content_type="image/jpeg")
        BeforeAfterPhoto.objects.create(
            ticket=ticket_for_before_photo,
            photo_type='BEFORE',
            image=dummy_image_before,
            uploaded_by=self.test_user
        )

    # --- เทสต์การเข้าถึง (Access Tests) ---

    def test_map_view_redirects_if_not_logged_in(self):
        response = self.client.get(reverse('dashboard:map'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, '/login/?next=/dashboard/')

    def test_map_view_loads_for_logged_in_user(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(reverse('dashboard:map'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/main_page.html')

    # --- เทสต์ข้อมูลใน Context (Context Data Tests) ---

    def test_map_view_context_data_no_filters(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(reverse('dashboard:map'))
        self.assertEqual(response.status_code, 200)

        # เรามี Ticket ทั้งหมด 5 ใบ
        self.assertEqual(response.context['total_tickets'], 5)
        # มีสถานะ PENDING ทั้งหมด 3 ใบ
        self.assertEqual(response.context['pending_count'], 3)
        self.assertEqual(response.context['in_progress_count'], 1)
        self.assertEqual(response.context['completed_count'], 1)

        # มี tickets 4 อันที่มีพิกัด (สำหรับแผนที่)
        self.assertEqual(len(response.context['tickets']), 4)
        # latest_tickets คือทั้งหมด 5 อัน
        self.assertEqual(len(response.context['latest_tickets']), 5)

    # --- เทสต์การกรองข้อมูล (Filtering Tests) ---

    def test_map_view_filters_by_status_pending(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(reverse('dashboard:map'), {'status': 'pending'})
        self.assertEqual(len(response.context['tickets']), 2)

    def test_map_view_filters_by_category(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(reverse('dashboard:map'), {'category': self.category1.id})
        self.assertEqual(len(response.context['tickets']), 2)

    def test_map_view_filters_by_status_in_progress(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(reverse('dashboard:map'), {'status': 'in_progress'})
        self.assertEqual(len(response.context['tickets']), 1)

    def test_map_view_filters_by_status_completed(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(reverse('dashboard:map'), {'status': 'completed'})
        self.assertEqual(len(response.context['tickets']), 1)

    def test_latest_tickets_filters_by_status(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(reverse('dashboard:map'), {'latest_status': 'pending'})
        self.assertEqual(len(response.context['latest_tickets']), 3)

    def test_latest_tickets_filters_by_other_statuses(self):
        self.client.login(username='testuser', password='testpassword123')
        response_in_progress = self.client.get(reverse('dashboard:map'), {'latest_status': 'in_progress'})
        self.assertEqual(len(response_in_progress.context['latest_tickets']), 1)
        response_completed = self.client.get(reverse('dashboard:map'), {'latest_status': 'completed'})
        self.assertEqual(len(response_completed.context['latest_tickets']), 1)

    def test_geojson_uses_attachment_as_fallback_before_photo(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(reverse('dashboard:map'))
        geojson_data = json.loads(response.context['tickets_geojson'])
        
        target_feature = next((f for f in geojson_data['features'] if f['properties']['title'] == 'ประตูห้องน้ำล็อค'), None)
        
        self.assertIsNotNone(target_feature)
        self.assertIsNotNone(target_feature['properties']['before_photo'])
        self.assertIn('.txt', target_feature['properties']['before_photo']) # ตรวจสอบว่า URL มาจากไฟล์ attachment จริง