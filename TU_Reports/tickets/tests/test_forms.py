from django.test import TestCase
from ..forms import TicketForm
from ..models import Category

class FormUnitTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        """
        สร้าง Category จำลอง 1 อัน เพื่อให้ Form ใช้เลือกได้
        """
        cls.category = Category.objects.create(name="Form Test Category")

    # --- เทส TicketForm ---

    def test_ticket_form_is_invalid_missing_title(self):
        """
        [Unit Test] เทสว่าฟอร์ม "Invalid" เมื่อ "ลืมใส่ Title"
        """
        print("Running: test_ticket_form_is_invalid_missing_title")
        
        # "Arrange" - ข้อมูลจำลอง (จงใจลืม 'title')
        form_data = {
            'description': 'Test description',
            'category': self.category.id,
            'urgency_level': 'LOW',
        }
        
        # "Act"
        form = TicketForm(data=form_data)
        
        # "Assert"
        self.assertFalse(form.is_valid())
        
        self.assertIn('title', form.errors)
        self.assertEqual(form.errors['title'], ['This field is required.'])