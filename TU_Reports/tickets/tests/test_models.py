from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from django.contrib.auth import get_user_model

from ..models import Category, Ticket 

User = get_user_model()


class ModelUnitTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        """
        สร้างข้อมูลจำลองสำหรับใช้ในเทสโมเดล
        """
        cls.category = Category.objects.create(name="Hardware Test", color="#FF0000")
        
        cls.user = User.objects.create_user(username='model_tester', password='123')

        cls.ticket = Ticket.objects.create(
            title="Test Ticket for Str",
            category=cls.category,
            created_by=cls.user
        )

    # --- เทส Category Model ---
    
    def test_category_str_method(self):
        """
        [Unit Test] เทสว่า __str__ ของ Category คืนค่า "name" ถูกต้อง
        """
        print("Running: test_category_str_method")
        self.assertEqual(str(self.category), "Hardware Test")

    # --- เทส Ticket Model ---

    def test_ticket_str_method(self):
        """
        [Unit Test] เทสว่า __str__ ของ Ticket คืนค่า "pk - title" ถูกต้อง
        """
        print("Running: test_ticket_str_method")
        expected_str = f"#{self.ticket.pk} - Test Ticket for Str"
        self.assertEqual(str(self.ticket), expected_str)

    def test_ticket_is_overdue_false_for_new_ticket(self):
        """
        [Unit Test] เทสว่า Ticket ที่เพิ่งสร้าง... is_overdue() ต้องเป็น False
        """
        print("Running: test_ticket_is_overdue_false_for_new_ticket")
        # ใช้ Ticket ที่เพิ่งสร้างจาก setUpTestData
        self.assertFalse(self.ticket.is_overdue(hours=48))

    def test_ticket_is_overdue_true_for_old_ticket(self):
        """
        [Unit Test] เทสว่า Ticket เก่า... is_overdue() ต้องเป็น True
        """
        print("Running: test_ticket_is_overdue_true_for_old_ticket")
        
        # "Arrange" - สร้าง Ticket ที่เวลาในอดีต
        past_time = timezone.now() - timedelta(days=3) 
        old_ticket = Ticket.objects.create(
            title="Old Ticket",
            category=self.category,
            created_by=self.user,
            created_at=past_time 
        )
        
        self.assertTrue(old_ticket.is_overdue(hours=48)) 

    def test_ticket_is_overdue_false_for_completed_ticket(self):
        """
        [Unit Test] เทสว่า Ticket ที่ "เสร็จแล้ว"... is_overdue() ต้องเป็น False เสมอ
        """
        print("Running: test_ticket_is_overdue_false_for_completed_ticket")
        
        # "Arrange" - สร้าง Ticket เก่า ที่ "เสร็จแล้ว"
        past_time = timezone.now() - timedelta(days=10) # 10 วันที่แล้ว
        completed_ticket = Ticket.objects.create(
            title="Old Completed Ticket",
            category=self.category,
            created_by=self.user,
            created_at=past_time,
            status="COMPLETED" # (สถานะเสร็จแล้ว)
        )
        
        # "Act" & "Assert"
        self.assertFalse(completed_ticket.is_overdue(hours=48))