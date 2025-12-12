from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.contrib.messages import get_messages

from notify.models import Notification


User = get_user_model()


class NotifyViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pass1234")
        self.client.login(username="u1", password="pass1234")

    def _make_notis(self):
        Notification.objects.create(recipient=self.user, notification_type="ASSIGNED", title="a1", message="m", is_read=False)
        Notification.objects.create(recipient=self.user, notification_type="ASSIGNED", title="a2", message="m", is_read=True)
        Notification.objects.create(recipient=self.user, notification_type="STATUS_CHANGE", title="s1", message="m", is_read=False)

    def test_notification_list_returns_200_and_context(self):
        self._make_notis()
        url = reverse("notify:list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("notifications", resp.context)
        self.assertIn("unread_count", resp.context)
        self.assertEqual(resp.context["unread_count"], 2)

    def test_notification_list_filter_type(self):
        self._make_notis()
        url = reverse("notify:list")
        resp = self.client.get(url, {"type": "ASSIGNED"})
        self.assertEqual(resp.status_code, 200)
        notis = list(resp.context["notifications"])
        self.assertTrue(all(n.notification_type == "ASSIGNED" for n in notis))

    def test_notification_list_filter_unread(self):
        self._make_notis()
        url = reverse("notify:list")
        resp = self.client.get(url, {"read": "unread"})
        self.assertEqual(resp.status_code, 200)
        notis = list(resp.context["notifications"])
        self.assertTrue(all(n.is_read is False for n in notis))

    def test_mark_as_read_ajax_returns_json(self):
        n = Notification.objects.create(
            recipient=self.user, notification_type="STATUS_CHANGE", title="t", message="m", is_read=False
        )
        url = reverse("notify:mark_read", args=[n.id])
        resp = self.client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "success")

        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_mark_as_read_normal_redirects_and_sets_message(self):
        n = Notification.objects.create(
            recipient=self.user, notification_type="STATUS_CHANGE", title="t", message="m", is_read=False
        )
        url = reverse("notify:mark_read", args=[n.id])
        resp = self.client.get(url, follow=True)
        self.assertEqual(resp.status_code, 200)
        n.refresh_from_db()
        self.assertTrue(n.is_read)

        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("ทำเครื่องหมายอ่านแล้ว" in m for m in msgs))

    def test_mark_all_as_read_marks_only_unread(self):
        n1 = Notification.objects.create(recipient=self.user, notification_type="ASSIGNED", title="1", message="m", is_read=False)
        n2 = Notification.objects.create(recipient=self.user, notification_type="ASSIGNED", title="2", message="m", is_read=False)
        n3 = Notification.objects.create(recipient=self.user, notification_type="ASSIGNED", title="3", message="m", is_read=True)

        url = reverse("notify:mark_all_read")
        resp = self.client.get(url, follow=True)
        self.assertEqual(resp.status_code, 200)

        n1.refresh_from_db()
        n2.refresh_from_db()
        n3.refresh_from_db()
        self.assertTrue(n1.is_read)
        self.assertTrue(n2.is_read)
        self.assertTrue(n3.is_read)

        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("ทำเครื่องหมายอ่านแล้ว 2 รายการ" in m for m in msgs))

    def test_notification_list_filter_read(self):
        # 1 unread, 1 read
        Notification.objects.create(recipient=self.user, notification_type="ASSIGNED", title="u", message="m", is_read=False)
        Notification.objects.create(recipient=self.user, notification_type="ASSIGNED", title="r", message="m", is_read=True)

        url = reverse("notify:list")
        resp = self.client.get(url, {"read": "read"})
        self.assertEqual(resp.status_code, 200)

        notis = list(resp.context["notifications"])
        self.assertTrue(len(notis) >= 1)
        self.assertTrue(all(n.is_read is True for n in notis))
