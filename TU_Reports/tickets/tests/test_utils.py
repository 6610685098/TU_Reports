import sys
from io import BytesIO
from PIL import Image
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

# (1) Import ฟังก์ชันที่เราจะเทส
from ..utils.images import resize_and_compress

class ImageUtilTests(TestCase):

    def setUp(self):
        """
        สร้าง "ไฟล์รูปจำลอง" 2 แบบ (แบบมี Alpha และ ไม่มี)
        เก็บไว้ใน memory เพื่อใช้ในเทสต่างๆ
        """
        
        # --- สร้างรูป JPEG จำลอง (ไม่มี Alpha) ---
        jpeg_buffer = BytesIO()
        jpeg_image = Image.new('RGB', (2000, 2000), color='blue') # (สร้างรูป 2000x2000)
        jpeg_image.save(jpeg_buffer, format='JPEG')
        jpeg_buffer.seek(0)
        
        self.mock_jpeg_file = SimpleUploadedFile(
            name='test_rgb.jpg',
            content=jpeg_buffer.getvalue(),
            content_type='image/jpeg'
        )

        # --- สร้างรูป PNG จำลอง (มี Alpha/ความใส) ---
        png_buffer = BytesIO()
        png_image = Image.new('RGBA', (2000, 2000), color=(255, 0, 0, 128)) # (สีแดง โปร่งแสง 50%)
        png_image.save(png_buffer, format='PNG')
        png_buffer.seek(0)

        self.mock_png_file = SimpleUploadedFile(
            name='test_rgba.png',
            content=png_buffer.getvalue(),
            content_type='image/png'
        )

    # --- เริ่มเทส ---

    def test_resize_image_dimensions(self):
        """
        [Unit Test] เทสว่าฟังก์ชัน "ย่อขนาด" (resize) รูปได้ถูกต้อง
        (จาก 2000x2000 -> ไม่เกิน 1600x1600)
        """
        print("Running: test_resize_image_dimensions")
        
        # "Act" - เรียกใช้ฟังก์ชัน
        result_file = resize_and_compress(
            self.mock_jpeg_file,
            max_width=1000,
            max_height=1000
        )

        # "Assert" - ตรวจสอบขนาด
        result_image = Image.open(result_file)
        # (thumbnail จะย่อให้ด้านที่ยาวที่สุด = 1000)
        self.assertEqual(result_image.width, 1000)
        self.assertEqual(result_image.height, 1000)

    def test_compress_jpeg_no_alpha(self):
        """
        [Unit Test] เทส Logic (เส้นทาง JPEG):
        เมื่อป้อนรูปที่ "ไม่มี" Alpha (JPEG) ...
        ผลลัพธ์ควรเป็น 'JPEG' (ตาม Logic: target_format = "JPEG")
        """
        print("Running: test_compress_jpeg_no_alpha")
        
        # "Act" - เรียกใช้ฟังก์ชัน (ไม่ระบุ target_format)
        result_file = resize_and_compress(
            self.mock_jpeg_file,
            quality=80
        )

        # "Assert" - ตรวจสอบชนิดไฟล์
        self.assertEqual(result_file.content_type, 'image/jpeg')
        self.assertTrue(result_file.name.endswith('.jpeg'))

        # (ขั้นสูง) เช็คว่ามันถูกแปลงเป็น RGB (เพราะเป็น JPEG)
        result_image = Image.open(result_file)
        self.assertEqual(result_image.mode, 'RGB')

    def test_compress_png_with_alpha(self):
        """
        [Unit Test] เทส Logic (เส้นทาง WEBP/PNG):
        เมื่อป้อนรูปที่ "มี" Alpha (PNG) ...
        ผลลัพธ์ควรเป็น 'WEBP' (ตาม Logic: target_format = "WEBP")
        """
        print("Running: test_compress_png_with_alpha")
        
        # "Act" - เรียกใช้ฟังก์ชัน (ไม่ระบุ target_format)
        result_file = resize_and_compress(
            self.mock_png_file,
            quality=80
        )

        # "Assert" - ตรวจสอบชนิดไฟล์ (โค้ดคุณจะแปลงเป็น WEBP)
        self.assertEqual(result_file.content_type, 'image/webp')
        self.assertTrue(result_file.name.endswith('.webp'))

        # (ขั้นสูง) เช็คว่ามันยังคงมี Alpha
        result_image = Image.open(result_file)
        self.assertIn(result_image.mode, ['RGBA', 'LA']) # (WEBP จะมี Alpha)

    def test_force_format_to_png(self):
        """
        [Unit Test] เทสว่า 'target_format' parameter ทำงาน
        เมื่อป้อน JPEG ... แต่บังคับเป็น PNG
        """
        print("Running: test_force_format_to_png")
        
        # "Act"
        result_file = resize_and_compress(
            self.mock_jpeg_file, # (ป้อน JPEG)
            target_format="PNG" # (บังคับเป็น PNG)
        )

        # "Assert" - ตรวจสอบชนิดไฟล์
        self.assertEqual(result_file.content_type, 'image/png')
        self.assertTrue(result_file.name.endswith('.png'))