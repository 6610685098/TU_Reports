import asyncio
from asgiref.sync import sync_to_async

from django.test import TransactionTestCase, override_settings
from django.contrib.auth import get_user_model

from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer

from notify.models import Notification
from notify.routing import websocket_urlpatterns


User = get_user_model()

TEST_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class NotificationConsumerTests(TransactionTestCase):

    async def test_connect_and_ping_pong(self):
        user = await sync_to_async(User.objects.create_user)(
            username="u1", password="pass1234"
        )

        application = URLRouter(websocket_urlpatterns)
        communicator = WebsocketCommunicator(application, "/ws/notifications/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        msg = await communicator.receive_json_from()
        self.assertEqual(msg["type"], "connection_established")

        await communicator.send_json_to({"type": "ping", "timestamp": 123})
        pong = await communicator.receive_json_from()
        self.assertEqual(pong["type"], "pong")
        self.assertEqual(pong["timestamp"], 123)

        await communicator.disconnect()

    async def test_notification_message_forwarded_to_socket(self):
        user = await sync_to_async(User.objects.create_user)(
            username="u3", password="pass1234"
        )

        application = URLRouter(websocket_urlpatterns)
        communicator = WebsocketCommunicator(application, "/ws/notifications/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.receive_json_from()  # connection_established

        layer = get_channel_layer()
        await layer.group_send(
            f"notifications_{user.id}",
            {
                "type": "notification_message",
                "notification": {"id": 1, "title": "X"},
                "unread_count": 9,
            },
        )

        msg = await communicator.receive_json_from()
        self.assertEqual(msg["type"], "notification")
        self.assertEqual(msg["notification"]["title"], "X")
        self.assertEqual(msg["unread_count"], 9)

        await communicator.disconnect()

    async def test_rejects_anonymous(self):
        application = URLRouter(websocket_urlpatterns)
        communicator = WebsocketCommunicator(application, "/ws/notifications/")
        communicator.scope["user"] = type("Anon", (), {"is_anonymous": True})()

        connected, _ = await communicator.connect()
        self.assertFalse(connected)

    async def test_receive_invalid_json_does_not_crash(self):
        user = await sync_to_async(User.objects.create_user)(
            username="u_badjson", password="pass1234"
        )

        application = URLRouter(websocket_urlpatterns)
        communicator = WebsocketCommunicator(application, "/ws/notifications/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.receive_json_from()  # connection_established

        # ส่ง text ที่ไม่ใช่ JSON → consumer ต้องไม่ crash
        await communicator.send_to(text_data="NOT_JSON")

        # ถ้ายังทำงานอยู่ จะ ping แล้วได้ pong
        await communicator.send_json_to({"type": "ping", "timestamp": 1})
        pong = await communicator.receive_json_from()
        self.assertEqual(pong["type"], "pong")
        self.assertEqual(pong["timestamp"], 1)

        await communicator.disconnect()

    async def test_mark_read_success(self):
        user = await sync_to_async(User.objects.create_user)(
            username="u_mr1", password="pass1234"
        )
        n = await sync_to_async(Notification.objects.create)(
            recipient=user,
            notification_type="STATUS_CHANGE",
            title="t",
            message="m",
            is_read=False,
        )

        application = URLRouter(websocket_urlpatterns)
        communicator = WebsocketCommunicator(application, "/ws/notifications/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.receive_json_from()  # connection_established

        await communicator.send_json_to(
            {"type": "mark_read", "notification_id": n.id}
        )

        # รอ async consumer ทำงาน (กัน race condition)
        for _ in range(10):
            n_db = await sync_to_async(Notification.objects.get)(id=n.id)
            if n_db.is_read:
                break
            await asyncio.sleep(0.05)

        n_db = await sync_to_async(Notification.objects.get)(id=n.id)
        self.assertTrue(n_db.is_read)

        await communicator.disconnect()

    async def test_mark_read_wrong_user_does_not_change(self):
        owner = await sync_to_async(User.objects.create_user)(
            username="u_owner", password="pass1234"
        )
        other = await sync_to_async(User.objects.create_user)(
            username="u_other", password="pass1234"
        )

        n = await sync_to_async(Notification.objects.create)(
            recipient=owner,
            notification_type="STATUS_CHANGE",
            title="t",
            message="m",
            is_read=False,
        )

        application = URLRouter(websocket_urlpatterns)
        communicator = WebsocketCommunicator(application, "/ws/notifications/")
        communicator.scope["user"] = other

        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.receive_json_from()

        await communicator.send_json_to(
            {"type": "mark_read", "notification_id": n.id}
        )

        n_db = await sync_to_async(Notification.objects.get)(id=n.id)
        self.assertFalse(n_db.is_read)

        await communicator.disconnect()
