from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.contrib.auth import get_user_model

from notify.models import Notification
from notify.utils import create_notification, send_notification_to_user

from types import SimpleNamespace
from unittest.mock import patch

from notify import utils


User = get_user_model()


class NotifyUtilsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pass1234")

    @patch("notify.utils.send_notification_to_user")
    def test_create_notification_creates_db_row_and_calls_sender(self, mock_send):
        n = create_notification(
            user=self.user,
            title="Hello",
            message="World",
            ticket=None,
            notification_type="STATUS_CHANGE",
        )

        self.assertTrue(Notification.objects.filter(id=n.id).exists())
        mock_send.assert_called_once()
        args, _kwargs = mock_send.call_args
        self.assertEqual(args[0], self.user.id)
        self.assertEqual(args[1].id, n.id)

    @patch("notify.utils.get_channel_layer")
    @patch("notify.utils.async_to_sync")
    def test_send_notification_to_user_sends_group_message_when_channel_layer_exists(self, mock_async_to_sync, mock_get_layer):
        # Prepare notification
        n = Notification.objects.create(
            recipient=self.user,
            notification_type="STATUS_CHANGE",
            title="T",
            message="M",
            is_read=False,
        )

        layer = MagicMock()
        mock_get_layer.return_value = layer

        # async_to_sync returns callable wrapper
        sender_callable = MagicMock()
        mock_async_to_sync.return_value = sender_callable

        send_notification_to_user(self.user.id, n)

        # Ensure async_to_sync called with group_send
        mock_async_to_sync.assert_called_once_with(layer.group_send)

        # Ensure group_send called with correct group and payload
        sender_callable.assert_called_once()
        group_name, payload = sender_callable.call_args.args
        self.assertEqual(group_name, f"notifications_{self.user.id}")
        self.assertEqual(payload["type"], "notification_message")
        self.assertIn("notification", payload)
        self.assertIn("unread_count", payload)

    @patch("notify.utils.get_channel_layer", return_value=None)
    def test_send_notification_to_user_noop_when_no_channel_layer(self, _mock_get_layer):
        n = Notification.objects.create(
            recipient=self.user,
            notification_type="STATUS_CHANGE",
            title="T",
            message="M",
        )
        # Should not raise
        send_notification_to_user(self.user.id, n)

class NotifyTicketHelperTests(TestCase):
    @patch("notify.utils.create_notification")
    def test_notify_ticket_assigned_calls_create_notification_when_assigned_to(self, mock_create):
        assignee = SimpleNamespace(id=1)
        ticket = SimpleNamespace(title="T1", assigned_to=assignee)

        utils.notify_ticket_assigned(ticket)

        mock_create.assert_called_once()
        _kwargs = mock_create.call_args.kwargs
        self.assertEqual(_kwargs["user"], assignee)
        self.assertEqual(_kwargs["notification_type"], "ASSIGNED")

    @patch("notify.utils.create_notification")
    def test_notify_ticket_assigned_noop_when_no_assigned_to(self, mock_create):
        ticket = SimpleNamespace(title="T1", assigned_to=None)
        utils.notify_ticket_assigned(ticket)
        mock_create.assert_not_called()

    @patch("notify.utils.create_notification")
    def test_notify_ticket_accepted(self, mock_create):
        tech = SimpleNamespace(get_display_name=lambda: "Tech A")
        creator = SimpleNamespace(id=9)
        ticket = SimpleNamespace(title="T2", assigned_to=tech, created_by=creator)

        utils.notify_ticket_accepted(ticket)

        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs["user"], creator)
        self.assertEqual(mock_create.call_args.kwargs["notification_type"], "STATUS_CHANGE")

    @patch("notify.utils.create_notification")
    def test_notify_ticket_rejected(self, mock_create):
        creator = SimpleNamespace(id=9)
        technician = SimpleNamespace(get_display_name=lambda: "Tech B")
        ticket = SimpleNamespace(title="T3", created_by=creator)

        utils.notify_ticket_rejected(ticket, technician)

        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs["user"], creator)
        self.assertEqual(mock_create.call_args.kwargs["notification_type"], "REASSIGNED")

    @patch("notify.utils.create_notification")
    def test_notify_ticket_completed(self, mock_create):
        creator = SimpleNamespace(id=9)
        ticket = SimpleNamespace(title="T4", created_by=creator)

        utils.notify_ticket_completed(ticket)

        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs["notification_type"], "COMPLETED")

    @patch("notify.utils.create_notification")
    def test_notify_status_changed(self, mock_create):
        creator = SimpleNamespace(id=9)
        ticket = SimpleNamespace(
            title="T5",
            created_by=creator,
            get_status_display=lambda: "เสร็จสิ้น",
        )

        utils.notify_status_changed(ticket, old_status="x", new_status="y")

        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs["notification_type"], "STATUS_CHANGE")