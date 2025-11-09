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
