# tickets/tests/test_views.py

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta

# Import โมเดลที่จำเป็นจากแอป tickets
from tickets.models import Ticket, Category, BeforeAfterPhoto, TicketStatusHistory
# Import ฟอร์มที่ View ใช้
from tickets.forms import TicketForm

# ดึง User model ปัจจุบันของโปรเจกต์มาใช้
User = get_user_model()

class TicketCreateViewTests(TestCase):
    """
    Test suite for the create_ticket view.
    """

    def setUp(self):
        """
        ตั้งค่าข้อมูลจำลองที่จะใช้ในทุกๆ เทสต์
        จะถูกรันใหม่ทุกครั้งก่อนเริ่มเทสต์แต่ละอัน
        """
        # 1. สร้าง Client สำหรับยิง request จำลอง
        self.client = Client()

        # 2. สร้าง User สำหรับทดสอบ
        self.user = User.objects.create_user(username='testuser', password='testpassword123')

        # 3. สร้าง Category จำลอง เพราะฟอร์มบังคับให้ต้องเลือก
        self.category = Category.objects.create(name='ปัญหาทั่วไป')

        # 4. URL ที่จะใช้ทดสอบ
        self.create_url = reverse('tickets:create_ticket')

    # --- Test Case 1: Access Control ---
    def test_create_ticket_redirects_if_not_logged_in(self):
        """
        ทดสอบว่าถ้ายังไม่ล็อกอินแล้วเข้าหน้า create_ticket จะถูก redirect ไปหน้า login
        """
        response = self.client.get(self.create_url)
        # ตรวจสอบว่า status code เป็น 302 (Redirect)
        self.assertEqual(response.status_code, 302)
        # ตรวจสอบว่า redirect ไปที่หน้า login พร้อม query string 'next'
        # หมายเหตุ: URL หน้า login ของคุณอาจเป็น /authentication/login/
        expected_redirect_url = f'/login/?next={self.create_url}'
        self.assertRedirects(response, expected_redirect_url)

    # --- Test Case 2: GET Request ---
    def test_create_ticket_get_request_as_logged_in_user(self):
        """
        ทดสอบว่าเมื่อล็อกอินแล้ว สามารถเข้าหน้า create_ticket (GET) ได้สำเร็จ
        """
        # ล็อกอิน user ที่เราสร้างไว้
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(self.create_url)

        # ตรวจสอบว่า status code เป็น 200 (OK)
        self.assertEqual(response.status_code, 200)
        # ตรวจสอบว่าใช้ template ที่ถูกต้อง
        self.assertTemplateUsed(response, 'user/create_ticket.html')
        # ตรวจสอบว่าใน context มี form และเป็น instance ของ TicketForm
        self.assertIn('form', response.context)
        self.assertIsInstance(response.context['form'], TicketForm)

    # --- Test Case 3: POST Request (Success) ---
    def test_create_ticket_post_success(self):
        """
        ทดสอบการสร้าง Ticket (POST) สำเร็จเมื่อกรอกข้อมูลครบถ้วน
        """
        self.client.login(username='testuser', password='testpassword123')

        # เตรียมข้อมูลที่จะส่งไปในฟอร์ม
        form_data = {
            'title': 'หลอดไฟห้องประชุมเสีย',
            'description': 'หลอดไฟกระพริบและดับไป',
            'category': self.category.id,
            'urgency_level': 'MEDIUM',
            'address_description': 'อาคาร A ชั้น 2',
            'latitude': '13.736717',
            'longitude': '100.523186',
        }

        # สร้างไฟล์จำลองสำหรับอัปโหลด
        dummy_image = SimpleUploadedFile(
            "test_image.jpg",
            b"file_content_for_image", # เนื้อหาไฟล์ (อะไรก็ได้)
            content_type="image/jpeg"
        )
        files_data = {'before_photo': dummy_image}

        # นับจำนวน object ก่อนทำการ POST
        ticket_count_before = Ticket.objects.count()
        photo_count_before = BeforeAfterPhoto.objects.count()
        history_count_before = TicketStatusHistory.objects.count()

        # ยิง POST request
        response = self.client.post(self.create_url, data={**form_data, **files_data})

        # ตรวจสอบว่ามี object เพิ่มขึ้นในฐานข้อมูล
        self.assertEqual(Ticket.objects.count(), ticket_count_before + 1)
        self.assertEqual(BeforeAfterPhoto.objects.count(), photo_count_before + 1)
        self.assertEqual(TicketStatusHistory.objects.count(), history_count_before + 1)

        # ตรวจสอบข้อมูลของ Ticket ที่สร้างขึ้นใหม่
        new_ticket = Ticket.objects.latest('id')
        self.assertEqual(new_ticket.title, 'หลอดไฟห้องประชุมเสีย')
        self.assertEqual(new_ticket.created_by, self.user)
        self.assertEqual(new_ticket.status, 'PENDING')
        self.assertIsNotNone(new_ticket.latitude)

        # ตรวจสอบว่ามีการ redirect ไปยังหน้าที่ถูกต้อง
        expected_redirect_url = reverse('tickets:ticket_detail', args=[new_ticket.id])
        self.assertRedirects(response, expected_redirect_url)

    # --- Test Case 4: POST Request (Invalid) ---
    def test_create_ticket_post_invalid_data(self):
        """
        ทดสอบการสร้าง Ticket (POST) ไม่สำเร็จเมื่อข้อมูลไม่ครบ (ขาด title)
        """
        self.client.login(username='testuser', password='testpassword123')

        # เตรียมข้อมูลที่ไม่สมบูรณ์ (ไม่มี title)
        form_data = {
            'description': 'ไม่มีหัวข้อ',
            'category': self.category.id,
        }

        # นับจำนวน object ก่อนทำการ POST
        ticket_count_before = Ticket.objects.count()

        # ยิง POST request
        response = self.client.post(self.create_url, data=form_data)

        # ตรวจสอบว่าไม่มี Ticket ใหม่ถูกสร้างขึ้น
        self.assertEqual(Ticket.objects.count(), ticket_count_before)

        # ตรวจสอบว่าระบบไม่ redirect และยังอยู่ที่หน้าเดิม (status code 200)
        self.assertEqual(response.status_code, 200)
        # ตรวจสอบว่ายังใช้ template เดิม
        self.assertTemplateUsed(response, 'user/create_ticket.html')
        # ตรวจสอบว่าฟอร์มที่ส่งกลับมามี error
        self.assertTrue(response.context['form'].errors)
        self.assertIn('title', response.context['form'].errors)
        
class MyTicketsViewTests(TestCase):
    """
    Test suite for the my_tickets view.
    """

    def setUp(self):
        """
        สร้างข้อมูลจำลองที่หลากหลายเพื่อทดสอบการกรองและการค้นหา
        """
        self.client = Client()
        # สร้าง User 2 คน เพื่อทดสอบว่าเห็นเฉพาะ Ticket ของตัวเอง
        self.user1 = User.objects.create_user(username='user1', password='password123')
        self.user2 = User.objects.create_user(username='user2', password='password123')

        # สร้าง Category 2 หมวด
        self.cat1 = Category.objects.create(name='ไฟฟ้า')
        self.cat2 = Category.objects.create(name='ประปา')

        # สร้าง Ticket 3 ใบสำหรับ user1
        # ใบที่ 1: ใหม่สุด, PENDING, ไฟฟ้า, มีคำค้นหาเฉพาะ
        Ticket.objects.create(
            created_by=self.user1, category=self.cat1,
            title='หลอดไฟห้องน้ำเสีย', description='หลอดไฟ T8',
            status='PENDING', urgency_level='LOW',
            created_at=timezone.now() - timedelta(days=1)
        )
        # ใบที่ 2: เก่าลงมา, IN_PROGRESS, ประปา
        Ticket.objects.create(
            created_by=self.user1, category=self.cat2,
            title='ก๊อกน้ำรั่ว', description='น้ำหยดตลอดเวลา',
            status='IN_PROGRESS', urgency_level='HIGH',
            created_at=timezone.now() - timedelta(days=5)
        )
        # ใบที่ 3: เก่าสุด, COMPLETED, ไฟฟ้า
        Ticket.objects.create(
            created_by=self.user1, category=self.cat1,
            title='ปลั๊กไฟหลวม', description='เสียบแล้วไฟไม่เข้า',
            status='COMPLETED', urgency_level='MEDIUM',
            created_at=timezone.now() - timedelta(days=10)
        )

        # สร้าง Ticket 1 ใบสำหรับ user2 (ซึ่ง user1 ต้องมองไม่เห็น)
        Ticket.objects.create(
            created_by=self.user2, category=self.cat1,
            title='แอร์ไม่เย็น', status='PENDING'
        )

        self.my_tickets_url = reverse('tickets:my_tickets')

    # --- Test Case 1: Access & Basic View ---
    def test_my_tickets_redirects_if_not_logged_in(self):
        """ทดสอบว่าถ้ายังไม่ล็อกอิน จะถูก redirect"""
        response = self.client.get(self.my_tickets_url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f'/login/?next={self.my_tickets_url}')

    def test_my_tickets_shows_only_own_tickets(self):
        """ทดสอบว่าหน้านี้แสดงเฉพาะ Ticket ของผู้ใช้ที่ล็อกอินเท่านั้น"""
        self.client.login(username='user1', password='password123')
        response = self.client.get(self.my_tickets_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'user/my_tickets.html')

        # ตรวจสอบว่า context 'tickets' มี 3 ใบ (ไม่ใช่ 4)
        self.assertEqual(len(response.context['tickets']), 3)
        # ตรวจสอบว่า context 'filtered_count' ถูกต้อง
        self.assertEqual(response.context['filtered_count'], 3)
        # ตรวจสอบว่า ticket ทั้งหมดเป็นของ user1 จริงๆ
        for ticket in response.context['tickets']:
            self.assertEqual(ticket.created_by, self.user1)

    def test_my_tickets_context_counts_are_correct(self):
        """ทดสอบว่าจำนวนนับใน context ถูกต้อง"""
        self.client.login(username='user1', password='password123')
        response = self.client.get(self.my_tickets_url)

        self.assertEqual(response.context['pending_count'], 1)
        self.assertEqual(response.context['in_progress_count'], 1)
        self.assertEqual(response.context['completed_count'], 1)

    # --- Test Case 2: Filtering & Searching ---
    def test_my_tickets_search_filter(self):
        """ทดสอบการค้นหาด้วยคำใน title"""
        self.client.login(username='user1', password='password123')
        response = self.client.get(self.my_tickets_url, {'search': 'ห้องน้ำ'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['tickets']), 1)
        self.assertEqual(response.context['tickets'][0].title, 'หลอดไฟห้องน้ำเสีย')

    def test_my_tickets_status_filter(self):
        """ทดสอบการกรองด้วยสถานะ"""
        self.client.login(username='user1', password='password123')
        response = self.client.get(self.my_tickets_url, {'status': 'IN_PROGRESS'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['tickets']), 1)
        self.assertEqual(response.context['tickets'][0].status, 'IN_PROGRESS')

    def test_my_tickets_category_filter(self):
        """ทดสอบการกรองด้วยหมวดหมู่"""
        self.client.login(username='user1', password='password123')
        response = self.client.get(self.my_tickets_url, {'category': self.cat1.id})

        self.assertEqual(response.status_code, 200)
        # มี 2 ใบที่อยู่ในหมวด 'ไฟฟ้า'
        self.assertEqual(len(response.context['tickets']), 2)

    # --- Test Case 3: Sorting ---
    def test_my_tickets_sorting(self):
        """ทดสอบการเรียงลำดับข้อมูล (เก่าสุดไปใหม่สุด)"""
        self.client.login(username='user1', password='password123')
        # ค่า default คือ '-created_at' (ใหม่สุดก่อน)
        # เราจะทดสอบการเรียงแบบ 'created_at' (เก่าสุดก่อน)
        response = self.client.get(self.my_tickets_url, {'sort': 'created_at'})

        self.assertEqual(response.status_code, 200)
        tickets_in_context = response.context['tickets']
        self.assertEqual(len(tickets_in_context), 3)

        # ตรวจสอบว่าใบแรกคือใบที่เก่าที่สุด (ปลั๊กไฟหลวม)
        self.assertEqual(tickets_in_context[0].title, 'ปลั๊กไฟหลวม')
        # ตรวจสอบว่าใบสุดท้ายคือใบที่ใหม่ที่สุด (หลอดไฟห้องน้ำเสีย)
        self.assertEqual(tickets_in_context[2].title, 'หลอดไฟห้องน้ำเสีย')
        
class TicketDetailViewTests(TestCase):
    """
    Test suite for the ticket_detail view.
    """

    def setUp(self):
        self.client = Client()
        # สร้าง User 3 ประเภท: เจ้าของ, ช่าง, และคนอื่น
        self.owner = User.objects.create_user(username='owner', password='password123', role='user')
        self.tech = User.objects.create_user(username='tech', password='password123', role='technician')
        self.other_user = User.objects.create_user(username='other', password='password123', role='user')

        self.category = Category.objects.create(name='Test Category')

        # สร้าง Ticket ที่มอบหมายงานให้ช่างแล้ว
        self.ticket = Ticket.objects.create(
            created_by=self.owner,
            assigned_to=self.tech,
            category=self.category,
            title='Test Ticket for Detail View',
            status='IN_PROGRESS'
        )
        self.detail_url = reverse('tickets:ticket_detail', args=[self.ticket.id])

    # --- Test Case 1: Access Control ---
    def test_detail_view_redirects_if_not_logged_in(self):
        """ทดสอบว่าถ้ายังไม่ล็อกอิน จะถูก redirect"""
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 302)

    def test_other_user_cannot_access_ticket_detail(self):
        """ทดสอบว่าผู้ใช้อื่นที่ไม่ใช่เจ้าของหรือช่าง ไม่สามารถเข้าดูได้"""
        self.client.login(username='other', password='password123')
        response = self.client.get(self.detail_url)
        # ควรจะ redirect ไปหน้า my_tickets พร้อม message error
        self.assertRedirects(response, reverse('tickets:my_tickets'))

    # --- Test Case 2: GET Request ---
    def test_owner_can_access_ticket_detail(self):
        """ทดสอบว่าเจ้าของ Ticket สามารถเข้าดูรายละเอียดได้"""
        self.client.login(username='owner', password='password123')
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'user/ticket_detail.html')
        self.assertEqual(response.context['ticket'], self.ticket)

    def test_assigned_tech_can_access_ticket_detail(self):
        """ทดสอบว่าช่างที่ได้รับมอบหมายงาน สามารถเข้าดูรายละเอียดได้"""
        self.client.login(username='tech', password='password123')
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['ticket'], self.ticket)

    # --- Test Case 3: POST Request (by Technician) ---
    def test_tech_can_update_status(self):
        """ทดสอบว่าช่างสามารถอัปเดตสถานะผ่าน POST request ได้"""
        self.client.login(username='tech', password='password123')
        
        post_data = {
            'action': 'update_status',
            'new_status': 'WORKING',
            'comment': 'กำลังลงมือแก้ไข'
        }
        response = self.client.post(self.detail_url, data=post_data)

        # ตรวจสอบว่า redirect กลับมาที่หน้าเดิม
        self.assertRedirects(response, self.detail_url)

        # ตรวจสอบว่าสถานะของ ticket ใน DB เปลี่ยนไปจริงๆ
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'WORKING')

        # ตรวจสอบว่ามี History record ใหม่ถูกสร้างขึ้น
        self.assertTrue(TicketStatusHistory.objects.filter(ticket=self.ticket, status='WORKING').exists())

    def test_tech_can_upload_after_photo(self):
        """ทดสอบว่าช่างสามารถอัปโหลดรูป AFTER ได้"""
        self.client.login(username='tech', password='password123')
        
        dummy_image = SimpleUploadedFile("after.jpg", b"content", content_type="image/jpeg")
        post_data = {'after_photo': dummy_image}

        response = self.client.post(self.detail_url, data=post_data)
        self.assertRedirects(response, self.detail_url)

        # ตรวจสอบว่ามีรูป AFTER photo ถูกสร้างขึ้นและเชื่อมกับ ticket
        self.assertTrue(
            BeforeAfterPhoto.objects.filter(ticket=self.ticket, photo_type='AFTER').exists()
        )

    def test_tech_cannot_submit_work_without_after_photo(self):
        """ทดสอบว่าช่างไม่สามารถส่งงานได้ถ้ายังไม่มีรูป AFTER"""
        self.client.login(username='tech', password='password123')
        
        post_data = {'action': 'submit_work'}
        self.client.post(self.detail_url, data=post_data)

        # ตรวจสอบว่าสถานะยังไม่เปลี่ยนเป็น COMPLETED
        self.ticket.refresh_from_db()
        self.assertNotEqual(self.ticket.status, 'COMPLETED')

    def test_tech_can_submit_work_with_after_photo(self):
        """ทดสอบว่าช่างสามารถส่งงานได้สำเร็จเมื่อมีรูป AFTER แล้ว"""
        self.client.login(username='tech', password='password123')

        # 1. สร้างรูป AFTER ก่อน
        BeforeAfterPhoto.objects.create(
            ticket=self.ticket, photo_type='AFTER',
            image=SimpleUploadedFile("after.jpg", b"c", "image/jpeg")
        )

        # 2. ส่ง action 'submit_work'
        post_data = {'action': 'submit_work'}
        self.client.post(self.detail_url, data=post_data)

        # ตรวจสอบว่าสถานะเปลี่ยนเป็น COMPLETED
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'COMPLETED')
        self.assertIsNotNone(self.ticket.completed_at)
        
class EditTicketViewTests(TestCase):
    """
    Test suite for the edit_ticket view.
    """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.other_user = User.objects.create_user(username='otheruser', password='password123')
        self.category = Category.objects.create(name='Category for Edit')

        # Ticket ที่สามารถแก้ไขได้ (สถานะ PENDING)
        self.pending_ticket = Ticket.objects.create(
            created_by=self.user, category=self.category,
            title='Original Title', status='PENDING'
        )
        # Ticket ที่ไม่สามารถแก้ไขได้ (สถานะ IN_PROGRESS)
        self.in_progress_ticket = Ticket.objects.create(
            created_by=self.user, category=self.category,
            title='Cannot Edit This', status='IN_PROGRESS'
        )

        self.edit_url = reverse('tickets:edit_ticket', args=[self.pending_ticket.id])
        self.non_editable_url = reverse('tickets:edit_ticket', args=[self.in_progress_ticket.id])

    # --- Test Case 1: Access Control & Conditions ---
    def test_edit_view_redirects_if_not_logged_in(self):
        """ทดสอบว่าถ้ายังไม่ล็อกอิน จะถูก redirect"""
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 302)

    def test_user_cannot_edit_others_ticket(self):
        """ทดสอบว่าไม่สามารถแก้ไข Ticket ของคนอื่นได้ (ควรจะเจอ 404)"""
        self.client.login(username='otheruser', password='password123')
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 404)

    def test_cannot_edit_non_pending_ticket(self):
        """ทดสอบว่าไม่สามารถแก้ไข Ticket ที่ไม่ใช่สถานะ PENDING ได้"""
        self.client.login(username='testuser', password='password123')
        response = self.client.get(self.non_editable_url)
        # ควรจะ redirect กลับไปหน้า detail
        detail_url = reverse('tickets:ticket_detail', args=[self.in_progress_ticket.id])
        self.assertRedirects(response, detail_url)

    # --- Test Case 2: GET & POST Requests ---
    def test_edit_view_get_request_success(self):
        """ทดสอบการเข้าหน้าแก้ไข (GET) สำหรับ Ticket ที่ถูกต้อง"""
        self.client.login(username='testuser', password='password123')
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'user/edit_ticket.html')
        # ตรวจสอบว่า form ใน context มีข้อมูลเดิมของ ticket อยู่
        self.assertEqual(response.context['form'].instance, self.pending_ticket)

    def test_edit_view_post_request_success(self):
        """ทดสอบการส่งข้อมูลแก้ไข (POST) สำเร็จ"""
        self.client.login(username='testuser', password='password123')
        
        updated_data = {
            'title': 'Updated Title',
            'description': 'Updated description.',
            'category': self.category.id,
            'urgency_level': 'HIGH'
        }
        response = self.client.post(self.edit_url, data=updated_data)

        # ตรวจสอบว่า redirect ไปหน้า detail
        detail_url = reverse('tickets:ticket_detail', args=[self.pending_ticket.id])
        self.assertRedirects(response, detail_url)

        # ตรวจสอบว่าข้อมูลใน DB ถูกอัปเดตจริงๆ
        self.pending_ticket.refresh_from_db()
        self.assertEqual(self.pending_ticket.title, 'Updated Title')
        self.assertEqual(self.pending_ticket.urgency_level, 'HIGH')

        # ตรวจสอบว่ามี History record ใหม่ถูกสร้างขึ้น
        self.assertTrue(
            TicketStatusHistory.objects.filter(ticket=self.pending_ticket, note__icontains='แก้ไขข้อมูล').exists()
        )
        
class CancelTicketViewTests(TestCase):
    """
    Test suite for the cancel_ticket view.
    """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.other_user = User.objects.create_user(username='otheruser', password='password123')
        self.tech = User.objects.create_user(username='tech', password='password123', role='technician')
        self.category = Category.objects.create(name='Category for Cancel')

        # Ticket ที่สามารถยกเลิกได้ (สถานะ PENDING และมีช่าง assigned)
        self.cancellable_ticket = Ticket.objects.create(
            created_by=self.user, category=self.category,
            title='Cancellable Ticket', status='PENDING', assigned_to=self.tech
        )
        # Ticket ที่ไม่สามารถยกเลิกได้ (สถานะ COMPLETED)
        self.non_cancellable_ticket = Ticket.objects.create(
            created_by=self.user, category=self.category,
            title='Non-Cancellable Ticket', status='COMPLETED'
        )

        self.cancel_url = reverse('tickets:cancel_ticket', args=[self.cancellable_ticket.id])
        self.non_cancellable_url = reverse('tickets:cancel_ticket', args=[self.non_cancellable_ticket.id])

    # --- Test Case 1: Access Control & Conditions ---
    def test_cancel_view_redirects_if_not_logged_in(self):
        """ทดสอบว่าถ้ายังไม่ล็อกอิน จะถูก redirect"""
        response = self.client.get(self.cancel_url)
        self.assertEqual(response.status_code, 302)

    def test_user_cannot_cancel_others_ticket(self):
        """ทดสอบว่าไม่สามารถยกเลิก Ticket ของคนอื่นได้ (ควรจะเจอ 404)"""
        self.client.login(username='otheruser', password='password123')
        response = self.client.get(self.cancel_url)
        self.assertEqual(response.status_code, 404)

    def test_cannot_cancel_completed_ticket(self):
        """ทดสอบว่าไม่สามารถยกเลิก Ticket ที่มีสถานะ COMPLETED ได้"""
        self.client.login(username='testuser', password='password123')
        response = self.client.get(self.non_cancellable_url)
        # ควรจะ redirect กลับไปหน้า detail
        detail_url = reverse('tickets:ticket_detail', args=[self.non_cancellable_ticket.id])
        self.assertRedirects(response, detail_url)

    # --- Test Case 2: GET & POST Requests ---
    def test_cancel_view_get_request_success(self):
        """ทดสอบการเข้าหน้ายืนยันการยกเลิก (GET)"""
        self.client.login(username='testuser', password='password123')
        response = self.client.get(self.cancel_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'user/cancel_ticket.html')
        self.assertEqual(response.context['ticket'], self.cancellable_ticket)

    def test_cancel_view_post_request_success(self):
        """ทดสอบการยืนยันยกเลิก (POST) สำเร็จ"""
        self.client.login(username='testuser', password='password123')
        
        post_data = {'reason': 'Problem solved'}
        response = self.client.post(self.cancel_url, data=post_data)

        # ตรวจสอบว่า redirect ไปหน้า my_tickets
        self.assertRedirects(response, reverse('tickets:my_tickets'))

        # ตรวจสอบว่าข้อมูลใน DB ถูกอัปเดตอย่างถูกต้อง
        self.cancellable_ticket.refresh_from_db()
        self.assertEqual(self.cancellable_ticket.status, 'REJECTED')
        self.assertIn('Problem solved', self.cancellable_ticket.reject_reason)
        # ตรวจสอบว่า assigned_to ถูกล้างค่า
        self.assertIsNone(self.cancellable_ticket.assigned_to)

        # ตรวจสอบว่ามี History record ใหม่ถูกสร้างขึ้น
        self.assertTrue(
            TicketStatusHistory.objects.filter(ticket=self.cancellable_ticket, status='REJECTED').exists()
        )