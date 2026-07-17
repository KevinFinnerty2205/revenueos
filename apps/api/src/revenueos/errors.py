import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from revenueos.contracts import ErrorResponse

logger = logging.getLogger("revenueos.errors")


class PublicAPIError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def request_id_for(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def error_response(
    request: Request,
    code: str,
    message: str,
    status_code: int,
    details: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(code=code, message=message, request_id=request_id_for(request), details=details)
    return JSONResponse(status_code=status_code, content=body.model_dump(by_alias=True, exclude_none=True))


async def public_api_error_handler(request: Request, exc: Exception) -> JSONResponse:
    public_error = (
        exc
        if isinstance(exc, PublicAPIError)
        else PublicAPIError("internal_error", "An unexpected error occurred.", 500)
    )
    return error_response(request, public_error.code, public_error.message, public_error.status_code)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    del exc
    return error_response(request, "invalid_request", "The request could not be validated.", 422)


async def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    status_code = int(getattr(exc, "status_code", 500))
    messages = {
        401: "Authentication is required.",
        403: "You do not have permission to perform this action.",
        404: "The requested resource was not found.",
        405: "The requested method is not allowed.",
    }
    message = messages.get(status_code, "The request could not be completed.")
    return error_response(request, "http_error", message, status_code)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_api_error",
        extra={"request_id": request_id_for(request), "error_type": type(exc).__name__},
    )
    return error_response(request, "internal_error", "An unexpected error occurred.", 500)
