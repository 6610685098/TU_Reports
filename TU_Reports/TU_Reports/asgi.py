# TU_Reports/asgi.py

import os
from django.core.asgi import get_asgi_application

# 1. ตั้งค่า Settings ก่อนเป็นอันดับแรก
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TU_Reports.settings')

# 2. สั่งให้ Django เริ่มทำงาน (Initialize) ทันที
# ขั้นตอนนี้จะทำให้ Django โหลด settings และ apps ต่างๆ
django_asgi_app = get_asgi_application()

# 3. ค่อย Import พวก Routing ทีหลัง (หลังจาก Django พร้อมแล้ว)
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import notify.routing

application = ProtocolTypeRouter({
    # ส่ง http request ให้ django_asgi_app ที่เราประกาศไว้ข้างบน
    "http": django_asgi_app,
    
    # ส่ง websocket request ให้ channels
    "websocket": AuthMiddlewareStack(
        URLRouter(
            notify.routing.websocket_urlpatterns
        )
    ),
})