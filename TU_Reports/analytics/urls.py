from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('dashboard/', views.admin_dashboard, name='dashboard'),
    path('admin/change-status/', views.admin_change_status, name='admin_change_status'),
    path('admin/close-ticket/', views.admin_close_ticket, name='admin_close_ticket'),
    path('admin/export-csv/', views.export_tickets_csv, name='export_csv'),
    
    # User Management
    path('users/', views.user_list, name='user_list'),
    path('users/<int:user_id>/edit/', views.user_edit, name='user_edit'),
    
    # Ticket Edit (Admin)
    path('tickets/<int:ticket_id>/edit/', views.ticket_edit, name='ticket_edit'),
]
