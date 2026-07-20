from typing import Any


class AppException(Exception):
    """可安全返回给客户端的业务异常。"""

    def __init__(self, code: int, message: str, status_code: int = 400, data: Any = None) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data
        super().__init__(message)


class AuthenticationException(AppException):
    def __init__(self, message: str = "认证失败", code: int = 20002) -> None:
        super().__init__(code, message, 401)


class PermissionDeniedException(AppException):
    def __init__(self, message: str = "没有操作权限") -> None:
        super().__init__(30003, message, 403)


class ResourceNotFoundException(AppException):
    def __init__(self, message: str = "资源不存在", code: int = 10004) -> None:
        super().__init__(code, message, 404)


class ConflictException(AppException):
    def __init__(self, message: str, code: int = 10009) -> None:
        super().__init__(code, message, 409)


class ServiceUnavailableException(AppException):
    def __init__(self, message: str, code: int = 90001) -> None:
        super().__init__(code, message, 503)
