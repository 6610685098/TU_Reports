from django.urls import path
from . import views

app_name = 'technician'

urlpatterns = [
    path('jobs/', views.job_list, name='job_list'),
    path('jobs/<int:ticket_id>/accept/', views.accept_job, name='accept_job'),  # PRIORITY 
    path('jobs/<int:ticket_id>/reject/', views.reject_job, name='reject_job'),  # PRIORITY 
    path('jobs/<int:ticket_id>/complete/', views.complete_job, name='complete_job'),  # PRIORITY  (After Photo)
    path('update-status/<int:ticket_id>/', views.update_status, name='update_status'),
    path('availability/', views.update_availability, name='update_availability'),
    path('my-tickets/', views.my_tickets, name='my_tickets_tech'),  
]
