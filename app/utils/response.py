from typing import Any, Optional
from fastapi.responses import JSONResponse


def success(data: Any, message: str = "success", status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": True, "message": message, "data": data},
    )


def error(message: str, status_code: int = 400, details: Optional[Any] = None) -> JSONResponse:
    body: dict = {"success": False, "message": message}
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status_code, content=body)
