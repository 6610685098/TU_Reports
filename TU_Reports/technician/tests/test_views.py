import os
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from unittest.mock import patch, MagicMock
import sys
import importlib
from technician import views
from django.test import RequestFactory

# Import models จากแอปที่ถูกต้องตามที่คุณให้มา
from tickets.models import Ticket, Category, TicketStatusHistory, TechnicianPresence, BeforeAfterPhoto
from authentication.models import User

class TechnicianViewsTestCase(TestCase):
    """
    Test case สำหรับ views ในแอป technician
    """
    @classmethod
    def setUpTestData(cls):
        """
        ตั้งค่าข้อมูลเริ่มต้นครั้งเดียวสำหรับ Test Case ทั้งหมดในคลาสนี้
        เพื่อประสิทธิภาพที่ดีกว่าการใช้ setUp สำหรับข้อมูลที่ไม่เปลี่ยนแปลง
        """
        # 1. สร้าง Users ที่มี role ต่างกัน
        cls.tech_user = User.objects.create_user(
            username='tech1', password='password123', role='technician', displayname_th='ช่างหนึ่ง'
        )
        cls.other_tech_user = User.objects.create_user(
            username='tech2', password='password123', role='technician', displayname_th='ช่างสอง'
        )
        cls.normal_user = User.objects.create_user(
            username='user1', password='password123', role='user'
        )

        # 2. สร้าง Category
        cls.cat_hardware = Category.objects.create(name='Hardware')
        cls.cat_software = Category.objects.create(name='Software')

        # 3. สร้าง Tickets สำหรับการทดสอบ
        cls.ticket_pending = Ticket.objects.create(
            title='PC not turning on',
            description='Searchable keyword: computer',
            created_by=cls.normal_user, assigned_to=cls.tech_user,
            category=cls.cat_hardware, status='PENDING', urgency_level='HIGH'
        )
        cls.ticket_in_progress = Ticket.objects.create(
            title='Install new software',
            description='Searchable keyword: program',
            created_by=cls.normal_user, assigned_to=cls.tech_user,
            category=cls.cat_software, status='IN_PROGRESS', urgency_level='LOW'
        )
        cls.ticket_other_tech = Ticket.objects.create(
            title='Other ticket',
            created_by=cls.normal_user, assigned_to=cls.other_tech_user,
            category=cls.cat_hardware, status='PENDING'
        )

    def setUp(self):
        """
        ตั้งค่าที่จะรันก่อนทุกๆ test method (เช่นการ login)
        """
        self.client = Client()
        self.client.login(username='tech1', password='password123')

    # === Tests for job_list (Authentication & Access) ===
    def test_job_list_view_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('technician:job_list'))
        # Django's default login URL is /accounts/login/
        self.assertRedirects(response, '/login/?next=/technician/jobs/')

    def test_job_list_view_requires_technician_role(self):
        self.client.login(username='user1', password='password123')
        response = self.client.get(reverse('technician:job_list'))
        self.assertRedirects(response, reverse('technician:my_tickets_tech'), fetch_redirect_response=False)

    # === Tests for job_list (Content & Filtering) ===
    def test_job_list_displays_correct_tickets(self):
        response = self.client.get(reverse('technician:job_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'technician/job_list.html')
        self.assertIn(self.ticket_pending, response.context['assigned_tickets'])
        self.assertIn(self.ticket_in_progress, response.context['assigned_tickets'])
        self.assertNotIn(self.ticket_other_tech, response.context['assigned_tickets'])

    def test_job_list_search_filter(self):
        url = reverse('technician:job_list') + '?search=software'
        response = self.client.get(url)
        self.assertIn(self.ticket_in_progress, response.context['assigned_tickets'])
        self.assertNotIn(self.ticket_pending, response.context['assigned_tickets'])
        self.assertEqual(response.context['filtered_count'], 1)

    def test_job_list_status_filter(self):
        url = reverse('technician:job_list') + '?status=PENDING'
        response = self.client.get(url)
        self.assertIn(self.ticket_pending, response.context['assigned_tickets'])
        self.assertNotIn(self.ticket_in_progress, response.context['assigned_tickets'])

    def test_job_list_category_filter(self):
        url = f"{reverse('technician:job_list')}?category={self.cat_hardware.id}"
        response = self.client.get(url)
        self.assertIn(self.ticket_pending, response.context['assigned_tickets'])
        self.assertNotIn(self.ticket_in_progress, response.context['assigned_tickets'])

    # === Tests for accept_job ===
    def test_accept_job_success(self):
        response = self.client.post(reverse('technician:accept_job', args=[self.ticket_pending.id]))
        self.assertRedirects(response, reverse('technician:job_list'))
        self.ticket_pending.refresh_from_db()
        self.assertEqual(self.ticket_pending.status, 'IN_PROGRESS')
        # ตรวจสอบ History ตาม Model ที่ถูกต้อง (ใช้ note)
        self.assertTrue(TicketStatusHistory.objects.filter(
            ticket=self.ticket_pending, status='IN_PROGRESS', note='ช่างรับงานแล้ว'
        ).exists())

    def test_accept_job_fail_if_not_pending(self):
        response = self.client.post(reverse('technician:accept_job', args=[self.ticket_in_progress.id]))
        self.assertRedirects(response, reverse('technician:job_list'))
        self.ticket_in_progress.refresh_from_db()
        self.assertEqual(self.ticket_in_progress.status, 'IN_PROGRESS') # Status should not change

    # === Tests for reject_job ===
    @patch('technician.views.auto_dispatch_ticket')
    def test_reject_job_and_reassign_success(self, mock_auto_dispatch):
        def dispatch_side_effect(ticket):
            ticket.assigned_to = self.other_tech_user
            ticket.save()
        mock_auto_dispatch.side_effect = dispatch_side_effect

        response = self.client.post(reverse('technician:reject_job', args=[self.ticket_pending.id]))
        self.assertRedirects(response, reverse('technician:job_list'))
        mock_auto_dispatch.assert_called_once_with(self.ticket_pending)
        self.ticket_pending.refresh_from_db()
        self.assertEqual(self.ticket_pending.assigned_to, self.other_tech_user)
        # ตรวจสอบ History การ Reject (ใช้ note)
        self.assertTrue(TicketStatusHistory.objects.filter(
            ticket=self.ticket_pending,
            status='PENDING',
            note__contains=f'ช่าง {self.tech_user.get_display_name()} ปฏิเสธงาน'
        ).exists())

    # === Tests for complete_job ===
    def test_complete_job_success_with_photo(self):
        dummy_image = SimpleUploadedFile("after.jpg", b"file_content", content_type="image/jpeg")
        response = self.client.post(reverse('technician:complete_job', args=[self.ticket_in_progress.id]), {
            'comment': 'Work completed successfully', # view อ่านค่าจาก POST ชื่อ 'comment'
            'after_photo': dummy_image
        })
        self.assertRedirects(response, reverse('technician:job_list'))
        self.ticket_in_progress.refresh_from_db()
        self.assertEqual(self.ticket_in_progress.status, 'COMPLETED')
        self.assertTrue(BeforeAfterPhoto.objects.filter(ticket=self.ticket_in_progress, photo_type='AFTER').exists())
        # ตรวจสอบ History (ใช้ note)
        self.assertTrue(TicketStatusHistory.objects.filter(
            ticket=self.ticket_in_progress, status='COMPLETED', note='Work completed successfully'
        ).exists())

    def test_complete_job_fail_without_photo(self):
        response = self.client.post(reverse('technician:complete_job', args=[self.ticket_in_progress.id]), {
            'comment': 'Trying to complete without photo'
        })
        self.assertEqual(response.status_code, 200) # Re-renders the form with an error message
        self.ticket_in_progress.refresh_from_db()
        self.assertNotEqual(self.ticket_in_progress.status, 'COMPLETED')

    # === Tests for update_availability ===
    def test_update_availability_toggle(self):
        presence, created = TechnicianPresence.objects.get_or_create(
            technician=self.tech_user, defaults={'is_available': True}
        )
        self.assertTrue(presence.is_available)

        # First POST: Toggle to False
        self.client.post(reverse('technician:update_availability'))
        presence.refresh_from_db()
        self.assertFalse(presence.is_available)

        # Second POST: Toggle back to True
        self.client.post(reverse('technician:update_availability'))
        presence.refresh_from_db()
        self.assertTrue(presence.is_available)

# เพิ่มเทสเหล่านี้เข้าไปในไฟล์ technician/test_views.py

    def test_job_list_urgency_filter(self):
        """ทดสอบการกรองด้วยความเร่งด่วน"""
        url = reverse('technician:job_list') + '?urgency=HIGH'
        response = self.client.get(url)
        self.assertIn(self.ticket_pending, response.context['assigned_tickets'])
        self.assertNotIn(self.ticket_in_progress, response.context['assigned_tickets'])

    # เพิ่มเทสนี้ในไฟล์ technician/test_views.py

    def test_views_access_denied_for_normal_user(self):
        """ทดสอบว่า user ทั่วไปไม่สามารถเข้าถึง views ของช่างได้"""
        # Login ด้วย user ธรรมดา
        self.client.login(username='user1', password='password123')

        # URL ที่ต้องการทดสอบ
        urls_to_test = [
            reverse('technician:accept_job', args=[self.ticket_pending.id]),
            reverse('technician:reject_job', args=[self.ticket_pending.id]),
            reverse('technician:complete_job', args=[self.ticket_in_progress.id]),
            reverse('technician:update_availability'),
        ]

        for url in urls_to_test:
            # ใช้ POST request เพราะ view ส่วนใหญ่ทำงานกับ POST
            response = self.client.post(url)
            # คาดหวังว่าจะ redirect ไปที่หน้า my_tickets (ตามโค้ดของคุณ)
            # ใช้ fetch_redirect_response=False เพื่อป้องกัน redirect ซ้อน
            self.assertRedirects(response, reverse('tickets:my_tickets'), fetch_redirect_response=False)

    # เพิ่มเทสนี้ในไฟล์ technician/test_views.py

    def test_reject_job_fail_if_not_pending(self):
        """ทดสอบว่าไม่สามารถปฏิเสธงานที่ไม่ได้อยู่ในสถานะ PENDING"""
        url = reverse('technician:reject_job', args=[self.ticket_in_progress.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('technician:job_list'))
        # ตรวจสอบว่าสถานะไม่เปลี่ยนแปลง
        self.ticket_in_progress.refresh_from_db()
        self.assertEqual(self.ticket_in_progress.status, 'IN_PROGRESS')


    def test_update_status_success(self):
        """ทดสอบการอัปเดตสถานะผ่านฟอร์ม"""
        url = reverse('technician:update_status', args=[self.ticket_in_progress.id])
        response = self.client.post(url, {
            'new_status': 'WORKING',
            'comment': 'Starting to work on it now.' # ชื่อ field ในฟอร์ม
        })
        self.assertRedirects(response, reverse('technician:job_list'))
        self.ticket_in_progress.refresh_from_db()
        self.assertEqual(self.ticket_in_progress.status, 'WORKING')
        self.assertTrue(TicketStatusHistory.objects.filter(
            ticket=self.ticket_in_progress,
            status='WORKING',
            note='Starting to work on it now.' # ชื่อ field ใน model
        ).exists())

    def test_update_status_get_request_redirects(self):
        """ทดสอบว่าการเข้าหน้า update_status ด้วย GET จะ redirect กลับ"""
        url = reverse('technician:update_status', args=[self.ticket_in_progress.id])
        response = self.client.get(url)
        # ตามโค้ดของคุณ มันจะ redirect ไปที่ ticket_detail
        self.assertRedirects(response, reverse('tickets:ticket_detail', args=[self.ticket_in_progress.id]))

# เพิ่มเทสนี้ในไฟล์ technician/test_views.py

    def test_job_list_default_sorting(self):
        """ทดสอบการเรียงลำดับ default (ไม่มี parameter 'sort')"""
        # สร้าง ticket ใหม่เพื่อให้มันขึ้นมาเป็นอันแรกเมื่อเรียงตาม -created_at
        from django.utils import timezone
        import time
        time.sleep(0.01) # หน่วงเวลาเล็กน้อยเพื่อให้ created_at ต่างกันแน่นอน
        newest_ticket = Ticket.objects.create(
            title='Newest Ticket', created_by=self.normal_user, assigned_to=self.tech_user,
            created_at=timezone.now()
        )
        response = self.client.get(reverse('technician:job_list'))
        # ตรวจสอบว่า ticket ใหม่ล่าสุด อยู่เป็นอันดับแรกใน list
        self.assertEqual(response.context['assigned_tickets'][0], newest_ticket)

    def test_job_list_date_range_filter(self):
        """ทดสอบการกรองด้วยช่วงวันที่"""
        from django.utils import timezone
        from datetime import timedelta
        # สร้าง ticket เก่าโดยใช้ timezone-aware datetime
        old_ticket = Ticket.objects.create(
            title='Old Ticket', created_by=self.normal_user, assigned_to=self.tech_user,
            created_at=timezone.now() - timedelta(days=10)
        )
        date_from = (timezone.now() - timedelta(days=15)).strftime('%Y-%m-%d')
        date_to = (timezone.now() - timedelta(days=5)).strftime('%Y-%m-%d')

        url = f"{reverse('technician:job_list')}?date_from={date_from}&date_to={date_to}"
        response = self.client.get(url)

        self.assertIn(old_ticket, response.context['assigned_tickets'])
        self.assertNotIn(self.ticket_pending, response.context['assigned_tickets'])


        # เพิ่มเทสนี้ในไฟล์ technician/test_views.py

    @patch('technician.views.auto_dispatch_ticket')
    def test_reject_job_and_reassign_fails(self, mock_auto_dispatch):
        """ทดสอบการปฏิเสธงาน แต่ไม่สามารถหาช่างใหม่ได้ (เพื่อให้ครอบคลุม else)"""
        # ตั้งค่าให้ mock function ไม่ทำอะไร (เหมือนหาช่างใหม่ไม่เจอ)
        mock_auto_dispatch.return_value = None

        # สร้าง ticket ใหม่สำหรับเทสนี้โดยเฉพาะ
        ticket_to_reject = Ticket.objects.create(
            title='Reject Test No Reassign', created_by=self.normal_user,
            assigned_to=self.tech_user, status='PENDING'
        )

        self.client.post(reverse('technician:reject_job', args=[ticket_to_reject.id]))
        ticket_to_reject.refresh_from_db()
        # ตรวจสอบว่า ticket ถูก unassign แต่ไม่มีช่างใหม่
        self.assertIsNone(ticket_to_reject.assigned_to)

    def test_complete_job_get_page(self):
        """ทดสอบการเข้าหน้าฟอร์ม complete job (GET request)"""
        url = reverse('technician:complete_job', args=[self.ticket_in_progress.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'technician/complete_job.html')

    def test_complete_job_on_pending_ticket_fails(self):
        """ทดสอบว่าไม่สามารถปิดงานที่มีสถานะ PENDING ได้"""
        url = reverse('technician:complete_job', args=[self.ticket_pending.id])
        response = self.client.post(url) # หรือ .get() ก็ได้
        # View จะ redirect กลับไปเพราะสถานะไม่ถูกต้อง
        self.assertRedirects(response, reverse('technician:job_list'))

    def test_my_tickets_tech_view_loads_correctly(self):
        """ทดสอบ view my_tickets_tech สำหรับช่างว่าโหลดได้และข้อมูลถูกต้อง"""
        # สร้าง ticket ที่ tech_user เป็นคนสร้างเอง
        my_created_ticket = Ticket.objects.create(
            title='Ticket created by tech', created_by=self.tech_user
        )
        url = reverse('technician:my_tickets_tech')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'technician/job_list.html')
        # ควรจะเห็น ticket ที่ตัวเองสร้าง
        self.assertIn(my_created_ticket, response.context['assigned_tickets'])
        # ไม่ควรเห็น ticket ที่คนอื่นสร้าง
        self.assertNotIn(self.ticket_pending, response.context['assigned_tickets'])

    def test_job_list_sorting_with_invalid_param(self):
        """ทดสอบการเรียงลำดับเมื่อใส่ parameter 'sort' ที่ไม่รู้จัก (เพื่อให้ครอบคลุม else)"""
        response = self.client.get(reverse('technician:job_list') + '?sort=invalid_key')
        # ควรจะ fallback ไปที่ default sorting (-created_at) และไม่พัง
        self.assertEqual(response.status_code, 200)

    def test_job_list_for_new_technician_without_presence(self):
        """ทดสอบ job_list สำหรับช่างใหม่ที่ยังไม่มี TechnicianPresence"""
        new_tech = User.objects.create_user(username='newtech', password='password123', role='technician')
        self.client.login(username='newtech', password='password123')
        response = self.client.get(reverse('technician:job_list'))
        self.assertEqual(response.status_code, 200)
        # ตรวจสอบว่า is_available ใน context เป็น True ตาม default ใน except block
        self.assertTrue(response.context['is_available'])

    def test_my_tickets_tech_view_comprehensive_filters(self):
        """ทดสอบ view my_tickets_tech พร้อมการกรองหลายเงื่อนไข"""
        # สร้าง ticket ที่ tech_user เป็นคนสร้างเอง
        my_ticket1 = Ticket.objects.create(
            title='My Urgent Hardware Ticket', created_by=self.tech_user,
            status='PENDING', category=self.cat_hardware, urgency_level='HIGH'
        )
        my_ticket2 = Ticket.objects.create(
            title='My Normal Software Ticket', created_by=self.tech_user,
            status='IN_PROGRESS', category=self.cat_software, urgency_level='MEDIUM'
        )

        # ทดสอบกรองด้วย category, urgency และ sort
        url = (f"{reverse('technician:my_tickets_tech')}"
            f"?category={self.cat_hardware.id}&urgency=HIGH&sort=created_at")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn(my_ticket1, response.context['assigned_tickets'])
        self.assertNotIn(my_ticket2, response.context['assigned_tickets'])

    # เพิ่มเทสนี้ในไฟล์ technician/test_views.py

    def test_update_status_access_denied_for_normal_user(self):
        """ทดสอบว่า user ทั่วไปไม่สามารถเข้าถึงหน้า update_status ได้"""
        self.client.login(username='user1', password='password123')
        url = reverse('technician:update_status', args=[self.ticket_in_progress.id])
        response = self.client.post(url)
        # คาดหวังว่าจะ redirect ไปที่หน้า my_tickets (ตามโค้ดของคุณ)
        self.assertRedirects(response, reverse('tickets:my_tickets'), fetch_redirect_response=False)

    # เพิ่มเทสนี้ในไฟล์ technician/test_views.py

    def test_job_list_invalid_date_filter_does_not_crash(self):
        """ทดสอบว่าการกรองด้วยวันที่ผิดรูปแบบไม่ทำให้ server crash และคืนค่า queryset เดิม"""
        initial_count = Ticket.objects.filter(assigned_to=self.tech_user).count()
        url = reverse('technician:job_list') + '?date_from=invalid-date'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # ตรวจสอบว่าจำนวน ticket ไม่เปลี่ยนแปลง เพราะการกรองควรจะถูกข้ามไป
        self.assertEqual(response.context['assigned_tickets'].count(), initial_count)

    # แทนที่ฟังก์ชันเดิมด้วยฟังก์ชันนี้ ในไฟล์ technician/test_views.py

    def test_my_tickets_tech_view_with_all_filters_and_sort(self):
        """ทดสอบ view my_tickets_tech พร้อมการกรองและเรียงลำดับทุกเงื่อนไข"""
        from django.utils import timezone
        from datetime import timedelta

        # สร้าง ticket ที่ tech_user เป็นคนสร้างเอง
        ticket1 = Ticket.objects.create(
            title='My Urgent Hardware Ticket', description='Searchable keyword: computer',
            created_by=self.tech_user, status='PENDING', category=self.cat_hardware,
            urgency_level='HIGH', created_at=timezone.now() - timedelta(days=5)
        )
        ticket2 = Ticket.objects.create(
            title='My Normal Software Ticket', description='Another keyword',
            created_by=self.tech_user, status='IN_PROGRESS', category=self.cat_software,
            urgency_level='MEDIUM', created_at=timezone.now() - timedelta(days=2)
        )

        # 1. ทดสอบ Filter ทั้งหมดพร้อมกัน
        date_from = (timezone.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        date_to = (timezone.now() - timedelta(days=4)).strftime('%Y-%m-%d')
        url = (f"{reverse('technician:my_tickets_tech')}"
            f"?search=computer"
            f"&status=PENDING"
            f"&category={self.cat_hardware.id}"
            f"&urgency=HIGH"
            f"&date_from={date_from}"
            f"&date_to={date_to}")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn(ticket1, response.context['assigned_tickets'])
        self.assertNotIn(ticket2, response.context['assigned_tickets'])
        self.assertEqual(response.context['filtered_count'], 1)

        # 2. ทดสอบการเรียงลำดับ (Sort)
        url_sort = f"{reverse('technician:my_tickets_tech')}?sort=created_at" # เรียงจากเก่าไปใหม่
        response_sort = self.client.get(url_sort)
        self.assertEqual(response_sort.context['assigned_tickets'][0], ticket1)

        # 3. ทดสอบ Default Sort (else block)
        url_default_sort = f"{reverse('technician:my_tickets_tech')}?sort=invalid"
        response_default_sort = self.client.get(url_default_sort)
        self.assertEqual(response_default_sort.context['assigned_tickets'][0], ticket2) # ใหม่กว่าจะขึ้นก่อน

        # 4. ทดสอบ except ValueError
        url_invalid_date = f"{reverse('technician:my_tickets_tech')}?date_from=invalid-date"
        response_invalid_date = self.client.get(url_invalid_date)
        self.assertEqual(response_invalid_date.status_code, 200) # ควรจะไม่พัง

    # เพิ่มเทสนี้เข้าไปด้วย เพื่อเก็บตกบรรทัด 300-301

    def test_my_tickets_tech_access_denied_for_normal_user(self):
        """ทดสอบว่า user ทั่วไปไม่สามารถเข้าถึงหน้า my_tickets_tech ได้"""
        self.client.login(username='user1', password='password123')
        url = reverse('technician:my_tickets_tech')
        response = self.client.post(url)
        # คาดหวังว่าจะ redirect ไปที่หน้า my_tickets (ตามโค้ดของคุณ)
        self.assertRedirects(response, reverse('tickets:my_tickets'), fetch_redirect_response=False)

        # เพิ่มเทสนี้ในไฟล์ technician/test_views.py

    def test_views_load_and_run_without_notify_module(self):
        """
        ทดสอบว่า view ทำงานได้เมื่อไม่มีโมดูล notify โดยการ reload module
        """
        # 1. ใช้ patch เพื่อซ่อนโมดูล 'notify.utils' ชั่วคราว
        with patch.dict('sys.modules', {'notify.utils': None}):
            # 2. นี่คือหัวใจสำคัญ: สั่งให้ Python โหลดไฟล์ views.py ใหม่อีกครั้ง
            # ตอนนี้ 'from notify.utils import ...' จะล้มเหลว และโค้ดใน except จะทำงาน
            importlib.reload(views)

            # 3. สร้าง request จำลองขึ้นมาเพื่อเรียก view โดยตรง
            # เพราะเราไม่สามารถใช้ self.client ซึ่งอาจจะยังใช้ views ตัวเก่าที่โหลดไว้แล้ว
            factory = RequestFactory()
            request = factory.post('/') # path ไม่สำคัญ
            request.user = self.tech_user

            # เพิ่ม middleware ที่จำเป็นสำหรับ messages framework
            from django.contrib.sessions.middleware import SessionMiddleware
            from django.contrib.messages.middleware import MessageMiddleware
            SessionMiddleware(lambda req: None).process_request(request)
            MessageMiddleware(lambda req: None).process_request(request)
            request.session.save()

            # 4. เรียกใช้ view ที่มีการเรียกใช้ฟังก์ชัน notify โดยตรง
            # เพื่อให้แน่ใจว่าฟังก์ชันที่ถูกสร้างใน except block ทำงานได้จริง
            response = views.accept_job(request, self.ticket_pending.id)

            # 5. ตรวจสอบว่า view ทำงานจนจบและ redirect ได้ถูกต้อง
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse('technician:job_list'), response.url)

        # 6. Reload views อีกครั้งหลังจบเทส เพื่อให้เทสอื่นๆ ไม่ได้รับผลกระทบ
        importlib.reload(views)