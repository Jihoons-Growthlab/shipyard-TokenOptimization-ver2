from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .errors import ApiError
from .routers import auth, common, drawings, hulls, me, plans, progress, users, dashboard

app = FastAPI(title="SWP Shipyard")
for module in (auth, common, me, hulls, plans, users, progress, drawings, dashboard):
    app.include_router(module.router)


def _error(status: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    return JSONResponse({"code": code, "message": message, "details": details or {}}, status_code=status)


@app.exception_handler(ApiError)
def handle_api_error(_: Request, exc: ApiError):
    return _error(exc.status, exc.code, exc.message, exc.details)


@app.exception_handler(RequestValidationError)
def handle_invalid_format(_: Request, exc: RequestValidationError):
    fields = [".".join(str(p) for p in e["loc"] if p != "body") for e in exc.errors()]
    return _error(422, "INVALID_FORMAT", "요청 형식이 올바르지 않습니다.", {"fields": fields})


@app.exception_handler(HTTPException)
def handle_http(_: Request, exc: HTTPException):
    code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
    return _error(exc.status_code, code, str(exc.detail))
