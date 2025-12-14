from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from notify.models import Notification, NotificationSettings


User = get_user_model()


class NotificationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pass1234")

    def test_notification_str(self):
        n = Notification.objects.create(
            recipient=self.user,
            notification_type="STATUS_CHANGE",
            title="T",
            message="M",
        )
        self.assertEqual(str(n), "u1: T")

    def test_mark_as_read_sets_flags_and_timestamp(self):
        n = Notification.objects.create(
            recipient=self.user,
            notification_type="STATUS_CHANGE",
            title="Hello",
            message="World",
            is_read=False,
        )
        self.assertFalse(n.is_read)
        self.assertIsNone(n.read_at)

        before = timezone.now()
        n.mark_as_read()
        n.refresh_from_db()

        self.assertTrue(n.is_read)
        self.assertIsNotNone(n.read_at)
        self.assertGreaterEqual(n.read_at, before)

    def test_mark_as_read_is_idempotent(self):
        n = Notification.objects.create(
            recipient=self.user,
            notification_type="STATUS_CHANGE",
            title="A",
            message="B",
            is_read=True,
            read_at=timezone.now(),
        )
        old_read_at = n.read_at
        n.mark_as_read()
        n.refresh_from_db()
        self.assertTrue(n.is_read)
        self.assertEqual(n.read_at, old_read_at)


class NotificationSettingsModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u2", password="pass1234")

    def test_notification_settings_str(self):
        s = NotificationSettings.objects.create(user=self.user)
        self.assertEqual(str(s), "u2's notification settings")
