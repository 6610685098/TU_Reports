from django.contrib import admin
from .models import Notification, NotificationSettings


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'recipient', 'title', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['title', 'message', 'recipient__username']
    readonly_fields = ['created_at', 'read_at']
    list_per_page = 50
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Basic Info', {
            'fields': ('recipient', 'notification_type', 'title', 'message')
        }),
        ('Related Ticket', {
            'fields': ('ticket', 'action_url', 'action_text'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_read', 'read_at')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'enable_in_app', 'enable_browser_push', 'enable_email', 'enable_sound']
    search_fields = ['user__username']
    list_filter = ['enable_in_app', 'enable_browser_push', 'enable_email']

    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Channel Settings', {
            'fields': ('enable_in_app', 'enable_browser_push', 'enable_email', 'enable_sound')
        }),
        ('Type Preferences', {
            'fields': ('notify_new_ticket', 'notify_status_change', 'notify_assigned', 'notify_messages', 'notify_urgent')
        }),
    )
