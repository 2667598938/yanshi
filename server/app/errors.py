from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


class ApiError(Exception):
    def __init__(self, status, code, message, detail='', data=None):
        self.status = status
        self.code = code
        self.message = message
        self.detail = detail
        self.data = data


def ok(data=None):
    return {'code': 0, 'message': 'ok', 'data': data}


def install_errors(app):
    @app.exception_handler(ApiError)
    async def api_error(_, exc):
        return JSONResponse(
            status_code=exc.status,
            content={'code': exc.code, 'message': exc.message, 'detail': exc.detail,
                     'data': exc.data},
        )

    @app.exception_handler(RequestValidationError)
    async def invalid(_, exc):
        # 不回显输入值：校验可能涉及密码/令牌
        detail = '; '.join(
            '.'.join(str(x) for x in e['loc']) + ': ' + e['type'] for e in exc.errors()
        )
        return JSONResponse(status_code=400, content={
            'code': 40001, 'message': '参数校验失败', 'detail': detail, 'data': None})

    @app.exception_handler(HTTPException)
    async def http_error(_, exc):
        return JSONResponse(status_code=exc.status_code, content={
            'code': 40401 if exc.status_code == 404 else 40001,
            'message': '资源不存在' if exc.status_code == 404 else '请求不支持',
            'detail': '', 'data': None})


def page(items, total, number, size):
    return {'items': items, 'total': total, 'page': number, 'page_size': size,
            'has_more': number * size < total}
