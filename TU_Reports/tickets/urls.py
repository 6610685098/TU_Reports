from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    path('create/', views.create_ticket, name='create_ticket'),  # Need: GPS + Before Photo
    path('my-tickets/', views.my_tickets, name='my_tickets'),
    path('<int:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path('<int:ticket_id>/edit/', views.edit_ticket, name='edit_ticket'),
    path('<int:ticket_id>/cancel/', views.cancel_ticket, name='cancel_ticket'),
    path('dispatch/<int:ticket_id>/', views.dispatch_ticket, name='dispatch_ticket'),
]
