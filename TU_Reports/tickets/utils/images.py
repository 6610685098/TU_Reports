# tickets/utils/images.py
from io import BytesIO
from PIL import Image, ImageOps
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys

# ป้องกัน Decompression Bomb (รูปใหญ่มาก)
Image.MAX_IMAGE_PIXELS = 80_000_000  # ปรับได้

def _normalize_mode(img: Image.Image) -> Image.Image:
    """
    แปลง mode ให้เหมาะสมก่อนบันทึก:
    - ถ้า alpha → ใช้ PNG/WebP
    - ถ้าไม่มี alpha → ใช้ RGB
    """
    if img.mode in ("RGBA", "LA"):
        return img
    if img.mode == "P":  # paletted
        return img.convert("RGBA")
    if img.mode not in ("RGB", "L"):
        return img.convert("RGB")
    return img

def _has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA")

def resize_and_compress(
    django_file,
    *,
    max_width: int = 1600,
    max_height: int = 1600,
    quality: int = 80,
    target_format: str | None = None,   # "JPEG", "WEBP", "PNG", หรือ None = ตัดสินใจอัตโนมัติ
    keep_exif: bool = False,
    optimize: bool = True
) -> InMemoryUploadedFile:
    """
    รับไฟล์ที่อัปโหลด แล้วคืนไฟล์ใหม่ที่ถูกย่อ/บีบอัด
    - ย่อแบบรักษาอัตราส่วน (thumbnail)
    - เลือกฟอร์แมตอัตโนมัติ: ถ้ามี alpha → PNG/WEBP, ถ้าไม่มี → JPEG/WEBP
    - strip EXIF (ค่าเริ่มต้น) เพื่อประหยัดขนาดไฟล์
    """
    # เปิดรูป
    img = Image.open(django_file)
    img = _normalize_mode(img)

    # ย่อขนาด (รักษาอัตราส่วน)
    img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

    # ตัดสินใจ format
    has_alpha = _has_alpha(img)
    if target_format is None:
        # แนะนำ: ไม่มี alpha → JPEG, มี alpha → WEBP (หรือ PNG)
        target_format = "WEBP" if has_alpha else "JPEG"

    # สร้างบัฟเฟอร์เพื่อบันทึก
    buf = BytesIO()

    save_kwargs = {}
    if target_format.upper() in ("JPEG", "JPG"):
        # JPEG ไม่รองรับ alpha → แปลงเป็น RGB
        if has_alpha:
            img = img.convert("RGB")
        save_kwargs.update(dict(quality=quality, optimize=optimize, progressive=True))
    elif target_format.upper() == "WEBP":
        # WEBP รองรับ alpha
        save_kwargs.update(dict(quality=quality, method=6))
    elif target_format.upper() == "PNG":
        # PNG เน้น lossless ลดขนาดด้วย optimize
        save_kwargs.update(dict(optimize=optimize))
    else:
        # fallback
        target_format = "JPEG"
        if has_alpha:
            img = img.convert("RGB")
        save_kwargs.update(dict(quality=quality, optimize=optimize, progressive=True))

    # จัดการ EXIF
    if not keep_exif:
        # ลบข้อมูล EXIF/ICC เพื่อช่วยลดขนาด
        img.info.pop("exif", None)
        img = ImageOps.exif_transpose(img)  # คงการหมุนจาก exif แล้วค่อยลบทิ้ง

    # บันทึกลงบัฟเฟอร์
    img.save(buf, format=target_format, **save_kwargs)
    buf.seek(0)

    # ตั้งชื่อไฟล์ใหม่
    base_name = getattr(django_file, "name", "upload")
    ext = target_format.lower()
    if ext == "jpg":
        ext = "jpeg"
    new_name = f"{base_name.rsplit('.', 1)[0]}.{ext}"

    # สร้าง InMemoryUploadedFile ให้ Django ใช้กับ FileField/ImageField ได้ทันที
    out_file = InMemoryUploadedFile(
        file=buf,
        field_name=getattr(django_file, "field_name", None),
        name=new_name,
        content_type=f"image/{ext}",
        size=buf.getbuffer().nbytes,
        charset=None,
    )
    return out_file
