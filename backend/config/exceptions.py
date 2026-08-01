from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.views import exception_handler


ERROR_BY_EXCEPTION = (
    (ValidationError, ("INVALID_REQUEST", "요청 형식이 올바르지 않습니다.")),
    (NotAuthenticated, ("AUTHENTICATION_REQUIRED", "인증이 필요합니다.")),
    (AuthenticationFailed, ("INVALID_TOKEN", "인증 토큰이 유효하지 않습니다.")),
    (PermissionDenied, ("PERMISSION_DENIED", "요청 권한이 없습니다.")),
    (NotFound, ("NOT_FOUND", "요청한 리소스를 찾을 수 없습니다.")),
    (MethodNotAllowed, ("METHOD_NOT_ALLOWED", "지원하지 않는 요청 방식입니다.")),
    (Throttled, ("TOO_MANY_REQUESTS", "요청 횟수가 너무 많습니다.")),
)


class APIError(APIException):
    def __init__(self, *, status_code, code, message, details=None):
        self.status_code = status_code
        self.api_code = code
        self.api_message = message
        self.api_details = details or {}
        super().__init__(detail=message, code=code.lower())


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(response.data, dict) and "error" in response.data:
        return response

    if isinstance(exc, APIError):
        code = exc.api_code
        message = exc.api_message
        details = exc.api_details
    else:
        code, message = _error_info(exc)
        details = response.data

    response.data = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        }
    }
    return response


def _error_info(exc):
    for exception_type, error_info in ERROR_BY_EXCEPTION:
        if isinstance(exc, exception_type):
            return error_info
    return "API_ERROR", "요청을 처리할 수 없습니다."
