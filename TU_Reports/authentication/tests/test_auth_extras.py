from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from authentication.templatetags.auth_extras import post_login_url_for

User = get_user_model()


class TestPostLoginUrlFor(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _build_context(self, user):
        request = self.factory.get("/")
        request.user = user
        return {"request": request}

    def test_technician_user_redirects_to_job_list(self):
        """ถ้า user เป็น technician → tag ต้องส่ง URL technician:job_list"""
        tech = User.objects.create_user(
            username="techuser",
            password="x",
            role="technician",
        )
        ctx = self._build_context(tech)
        url = post_login_url_for(ctx)
        self.assertEqual(url, reverse("technician:job_list"))

    def test_normal_authenticated_user_redirects_to_my_tickets(self):
        """user ปกติ (role=user) → tag ส่ง URL tickets:my_tickets"""
        u = User.objects.create_user(
            username="normal",
            password="x",
            role="user",
        )
        ctx = self._build_context(u)
        url = post_login_url_for(ctx)
        self.assertEqual(url, reverse("tickets:my_tickets"))

    def test_anonymous_user_redirects_to_my_tickets(self):
        """anonymous user → tag ก็ส่ง URL tickets:my_tickets"""
        anon = AnonymousUser()
        ctx = self._build_context(anon)
        url = post_login_url_for(ctx)
        self.assertEqual(url, reverse("tickets:my_tickets"))
