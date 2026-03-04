from fastapi.responses import JSONResponse


def ok(data=None, message: str = "success", cache_status: str | None = None) -> JSONResponse:
    body = {"code": 200, "message": message, "data": data}
    if cache_status:
        body["cache"] = cache_status
    return JSONResponse(body)


def err(message: str, code: int = 400) -> JSONResponse:
    return JSONResponse({"code": code, "message": message, "data": None}, status_code=code)
