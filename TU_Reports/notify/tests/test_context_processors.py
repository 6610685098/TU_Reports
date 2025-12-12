from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from notify.context_processors import unread_notifications
from notify.models import Notification


User = get_user_model()


class UnreadNotificationsContextProcessorTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="u1", password="pass1234")

    def test_returns_0_for_anonymous(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()
        ctx = unread_notifications(request)
        self.assertEqual(ctx["unread_notifications_count"], 0)

    def test_counts_unread_for_authenticated_user(self):
        Notification.objects.create(
            recipient=self.user, notification_type="STATUS_CHANGE", title="t1", message="m1", is_read=False
        )
        Notification.objects.create(
            recipient=self.user, notification_type="STATUS_CHANGE", title="t2", message="m2", is_read=True
        )
        request = self.factory.get("/")
        request.user = self.user
        ctx = unread_notifications(request)
        self.assertEqual(ctx["unread_notifications_count"], 1)
