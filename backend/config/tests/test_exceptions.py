from django.test import SimpleTestCase
from rest_framework.exceptions import AuthenticationFailed, ValidationError

from config.exceptions import api_exception_handler


class APIExceptionHandlerTests(SimpleTestCase):
    def test_validation_error_uses_common_error_shape(self):
        response = api_exception_handler(
            ValidationError({"email": ["올바른 이메일을 입력하세요."]}),
            {},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "INVALID_REQUEST")
        self.assertIn("email", response.data["error"]["details"])

    def test_authentication_error_does_not_expose_internal_reason_as_code(self):
        response = api_exception_handler(AuthenticationFailed("잘못된 토큰"), {})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "INVALID_TOKEN")
