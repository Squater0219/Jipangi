from django.contrib.auth import get_user_model
from django.test import TestCase


class UserModelTests(TestCase):
    def test_email_is_login_identifier_and_normalized(self):
        user = get_user_model().objects.create_user(
            email="USER@Example.COM",
            username="사용자",
            password="safe-password-1234",
        )

        self.assertEqual(user.email, "user@example.com")
        self.assertEqual(get_user_model().USERNAME_FIELD, "email")
        self.assertTrue(user.check_password("safe-password-1234"))

    def test_username_can_be_duplicated(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            email="first@example.com",
            username="같은이름",
            password="safe-password-1234",
        )
        second = user_model.objects.create_user(
            email="second@example.com",
            username="같은이름",
            password="safe-password-1234",
        )

        self.assertEqual(second.username, "같은이름")
