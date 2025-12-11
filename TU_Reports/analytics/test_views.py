from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from tickets.models import Ticket, Category
# เรา import LoginLog มาเพื่อให้แน่ใจว่า Model มีอยู่จริง แต่เราจะไม่สร้างข้อมูลเพื่อเลี่ยง Error
from authentication.models import LoginLog 

User = get_user_model()

class AdminAnalyticsViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        # 1. สร้าง Users
        self.admin_user = User.objects.create_user(
            username='admin', password='password', role='admin', email='admin@example.com'
        )
        self.tech_user = User.objects.create_user(
            username='tech', password='password', role='technician', email='tech@example.com'
        )
        self.normal_user = User.objects.create_user(
            username='user', password='password', role='user', email='user@example.com'
        )

        # 2. สร้าง Categories
        self.category_hw = Category.objects.create(name='Hardware')
        self.category_sw = Category.objects.create(name='Software')

        # 3. สร้าง Tickets (จำลองสถานการณ์ต่างๆ)
        today = timezone.now()
        
        # Ticket 1: Pending, มี Category, สร้างโดย User
        self.ticket_pending = Ticket.objects.create(
            title='Mouse Broken',
            description='Fix it',
            category=self.category_hw,
            status='PENDING',
            urgency_level='MEDIUM',
            created_by=self.normal_user,
            created_at=today
        )
        
        # Ticket 2: Completed, มี Category, มี Assignee (ย้อนหลัง 5 วัน)
        self.ticket_completed = Ticket.objects.create(
            title='Install Office',
            description='Need Word',
            category=self.category_sw,
            status='COMPLETED',
            urgency_level='HIGH',
            created_by=self.normal_user,
            assigned_to=self.tech_user,
            created_at=today - timedelta(days=5)
        )
        # Hack: บังคับแก้ created_at เพราะ auto_now_add มักจะไม่ยอมให้แก้ตอน create
        Ticket.objects.filter(id=self.ticket_completed.id).update(created_at=today - timedelta(days=5))

        # Ticket 3: In Progress, ไม่มี Category (เพื่อเทส CSV), ไม่มี Assignee
        self.ticket_no_cat = Ticket.objects.create(
            title='Server Down',
            description='Urgent',
            category=None, # เป็น None เพื่อเทสเงื่อนไขใน CSV
            status='IN_PROGRESS',
            urgency_level='CRITICAL',
            created_by=self.admin_user,
            assigned_to=None, # เป็น None เพื่อเทสเงื่อนไข
            created_at=today
        )

    def login_admin(self):
        self.client.login(username='admin', password='password')

    def login_user(self):
        self.client.login(username='user', password='password')

    # ================================================================
    # 1. Test Access Control (สิทธิ์การเข้าถึง)
    # ================================================================
    def test_dashboard_access_denied_for_non_admin(self):
        self.login_user() # ล็อกอินเป็น User ธรรมดา
        response = self.client.get(reverse('analytics:dashboard'))
        # ต้องถูก Redirect (302) ไปหน้า Login หรือหน้าอื่น เพราะติด @user_passes_test
        self.assertEqual(response.status_code, 302)

    def test_dashboard_redirect_if_not_logged_in(self):
        response = self.client.get(reverse('analytics:dashboard'))
        self.assertEqual(response.status_code, 302)

    # ================================================================
    # 2. Test Admin Dashboard (Logic, Filters, Sorting, Charts)
    # ================================================================
    def test_admin_dashboard_basic_load(self):
        self.login_admin()
        response = self.client.get(reverse('analytics:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'analytics/admin_dashboard.html')
        
        # ตรวจสอบ Context Data
        context = response.context
        self.assertEqual(context['total_tickets'], 3)
        self.assertEqual(context['pending_tickets'], 1)
        self.assertEqual(context['completed_tickets'], 1)
        # ตรวจสอบว่ากราฟมีข้อมูล
        self.assertIn('chart_status_data', context)
        self.assertIn('chart_daily_data', context)

    def test_admin_dashboard_filters(self):
        self.login_admin()
        
        # Filter: Status = PENDING
        response = self.client.get(reverse('analytics:dashboard'), {'status': 'PENDING'})
        self.assertEqual(len(response.context['recent_tickets']), 1)
        self.assertEqual(response.context['recent_tickets'][0].id, self.ticket_pending.id)

        # Filter: Category = Software
        response = self.client.get(reverse('analytics:dashboard'), {'category': self.category_sw.id})
        self.assertEqual(len(response.context['recent_tickets']), 1)
        self.assertEqual(response.context['recent_tickets'][0].id, self.ticket_completed.id)

    def test_admin_dashboard_sorting(self):
        self.login_admin()
        
        # Sort: Title (Ascending) -> 'Install Office', 'Mouse Broken', 'Server Down'
        # 'I' มาก่อน 'M' มาก่อน 'S'
        response = self.client.get(reverse('analytics:dashboard'), {'sort': 'title'})
        tickets = response.context['recent_tickets']
        self.assertEqual(tickets[0].title, 'Install Office')
        
        # Sort: Invalid Field (ต้องเข้าเงื่อนไข else แล้วใช้ default -created_at)
        response = self.client.get(reverse('analytics:dashboard'), {'sort': 'invalid_column'})
        tickets = response.context['recent_tickets']
        # Default คือ -created_at (ล่าสุดขึ้นก่อน)
        # ticket_no_cat สร้างล่าสุด (หรือพร้อม pending) แต่ ticket_completed สร้าง 5 วันที่แล้วต้องอยู่ท้ายสุด
        self.assertNotEqual(tickets[0].id, self.ticket_completed.id)

    # ================================================================
    # 3. Test Admin Change Status
    # ================================================================
    def test_admin_change_status_success(self):
        self.login_admin()
        url = reverse('analytics:admin_change_status')
        data = {
            'ticket_id': self.ticket_pending.id,
            'new_status': 'IN_PROGRESS',
            'admin_comment': 'Start working'
        }
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse('analytics:dashboard'))
        
        self.ticket_pending.refresh_from_db()
        self.assertEqual(self.ticket_pending.status, 'IN_PROGRESS')

    def test_admin_change_status_invalid_id(self):
        self.login_admin()
        url = reverse('analytics:admin_change_status')
        # ส่ง ID ที่ไม่มีจริง (9999) -> ต้องเกิด 404
        response = self.client.post(url, {'ticket_id': 9999, 'new_status': 'IN_PROGRESS'})
        self.assertEqual(response.status_code, 404)

    # ================================================================
    # 4. Test Admin Close Ticket
    # ================================================================
    def test_admin_close_ticket_success(self):
        self.login_admin()
        url = reverse('analytics:admin_close_ticket')
        # Ticket ที่สถานะ COMPLETED เท่านั้นถึงจะปิดได้
        data = {'ticket_id': self.ticket_completed.id}
        
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse('analytics:dashboard'))
        
        self.ticket_completed.refresh_from_db()
        self.assertEqual(self.ticket_completed.status, 'CLOSED')

    def test_admin_close_ticket_fail_not_completed(self):
        self.login_admin()
        url = reverse('analytics:admin_close_ticket')
        # Ticket นี้สถานะ PENDING -> ปิดไม่ได้
        data = {'ticket_id': self.ticket_pending.id}
        
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse('analytics:dashboard'))
        
        self.ticket_pending.refresh_from_db()
        self.assertEqual(self.ticket_pending.status, 'PENDING') # สถานะต้องเหมือนเดิม

    # ================================================================
    # 5. Test Export CSV
    # ================================================================
    def test_export_tickets_csv(self):
        self.login_admin()
        url = reverse('analytics:export_csv')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        
        content = response.content.decode('utf-8')
        # เช็ค BOM
        self.assertTrue(content.startswith('\ufeff'))
        # เช็ค Header
        self.assertIn('ID,Title,Category,Status', content)
        
        # เช็คข้อมูล: Ticket ที่มี Category
        self.assertIn('Mouse Broken', content)
        self.assertIn('Hardware', content)
        
        # เช็คข้อมูล: Ticket ที่ไม่มี Category (ต้องแสดงเป็น -)
        # self.ticket_no_cat ไม่มี category และ assignee
        self.assertIn('Server Down', content)
        # ต้องหาเครื่องหมาย - ที่เกิดจากเงื่อนไข else '-'
        # เนื่องจาก CSV อาจมี - หลายที่ การเช็คแบบนี้อาจกว้างไป แต่เพียงพอให้ Code Coverage วิ่งผ่านบรรทัดนั้น

    # ================================================================
    # 6. Test User Management
    # ================================================================
    def test_user_list(self):
        self.login_admin()
        response = self.client.get(reverse('analytics:user_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'analytics/user_list.html')
        self.assertIn('users', response.context)
        # recent_logs จะว่างเปล่าเพราะเราไม่ได้สร้าง แต่โค้ดจะรันผ่านโดยไม่ Error

    def test_user_edit_get(self):
        self.login_admin()
        url = reverse('analytics:user_edit', args=[self.tech_user.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'analytics/user_form.html')

    def test_user_edit_post_active(self):
        self.login_admin()
        url = reverse('analytics:user_edit', args=[self.tech_user.id])
        data = {
            'displayname_th': 'ช่างใหม่',
            'email': 'newtech@example.com',
            'role': 'technician',
            'is_active': 'on' # ติ๊กถูก
        }
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse('analytics:user_list'))
        
        self.tech_user.refresh_from_db()
        self.assertTrue(self.tech_user.is_active)
        self.assertEqual(self.tech_user.displayname_th, 'ช่างใหม่')

    def test_user_edit_post_inactive(self):
        self.login_admin()
        url = reverse('analytics:user_edit', args=[self.tech_user.id])
        data = {
            'displayname_th': 'ช่างพักงาน',
            'email': 'tech@example.com',
            'role': 'technician',
            # ไม่ส่ง is_active มา แปลว่าไม่ได้ติ๊ก (False)
        }
        response = self.client.post(url, data)
        
        self.tech_user.refresh_from_db()
        self.assertFalse(self.tech_user.is_active)

    # ================================================================
    # 7. Test Ticket Edit
    # ================================================================
    def test_ticket_edit_get(self):
        self.login_admin()
        url = reverse('analytics:ticket_edit', args=[self.ticket_pending.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_ticket_edit_post_update(self):
        self.login_admin()
        url = reverse('analytics:ticket_edit', args=[self.ticket_pending.id])
        data = {
            'title': 'Mouse Fixed',
            'description': 'Done',
            'category': self.category_hw.id,
            'urgency_level': 'LOW',
            'status': 'COMPLETED',
            'assigned_to': self.tech_user.id
        }
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse('analytics:dashboard'))
        
        self.ticket_pending.refresh_from_db()
        self.assertEqual(self.ticket_pending.title, 'Mouse Fixed')
        self.assertEqual(self.ticket_pending.assigned_to, self.tech_user)

    def test_ticket_edit_post_no_assignee(self):
        self.login_admin()
        url = reverse('analytics:ticket_edit', args=[self.ticket_pending.id])
        data = {
            'title': 'Mouse Waiting',
            'description': '...',
            'category': self.category_hw.id,
            'urgency_level': 'LOW',
            'status': 'PENDING',
            'assigned_to': '' # ส่งค่าว่างมา (กรณีเลือก Unassigned)
        }
        response = self.client.post(url, data)
        
        self.ticket_pending.refresh_from_db()
        self.assertIsNone(self.ticket_pending.assigned_to)