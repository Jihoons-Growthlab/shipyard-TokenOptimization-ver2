class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


def validation(field: str, message: str) -> ApiError:
    return ApiError(400, "VALIDATION_ERROR", message, {"field": field})


def unauthorized() -> ApiError:
    return ApiError(401, "UNAUTHORIZED", "세션이 만료되었거나 유효하지 않습니다.")
