"""ASGI middlewares for body limits and baseline browser security headers."""

from starlette.responses import JSONResponse

from . import config


class RequestSizeLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            try:
                content_length = int(headers.get(b"content-length", b"0"))
            except ValueError:
                content_length = 0
            if content_length > config.MAX_REQUEST_BYTES:
                response = JSONResponse(
                    {"detail": "Request body is too large"},
                    status_code=413,
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                raw_headers = list(message.get("headers", []))
                security_headers = {
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"referrer-policy": b"no-referrer",
                    b"permissions-policy": b"camera=(self), geolocation=(), microphone=()",
                    b"content-security-policy": (
                        b"default-src 'self'; "
                        b"img-src 'self' data:; "
                        b"style-src 'self' 'unsafe-inline'; "
                        b"script-src 'self' 'unsafe-inline'; "
                        b"connect-src 'self'"
                    ),
                }
                if scope.get("path", "").startswith("/api/"):
                    security_headers[b"cache-control"] = b"no-store"
                existing = {key.lower() for key, _value in raw_headers}
                raw_headers.extend(
                    (key, value) for key, value in security_headers.items() if key not in existing
                )
                message["headers"] = raw_headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
