from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # ยังไม่ได้ใช้
    path('', views.map_view, name='map'),  # Main Page - All Tickets Map (now at /dashboard/)
    #path('summary/', views.admin_summary, name='admin_summary'),  # Admin Summary (moved from /dashboard/)
    #path('admin/change-status/', views.admin_change_status, name='admin_change_status'),  # Admin change ticket status
    #path('admin/close-ticket/', views.admin_close_ticket, name='admin_close_ticket'),  # Admin close ticket
]
