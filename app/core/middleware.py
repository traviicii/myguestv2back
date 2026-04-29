import hashlib
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field

from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import _payload

logger = logging.getLogger("myguest.request")


@dataclass
class RateLimitRule:
    name: str
    path: str
    methods: set[str]
    limit: int


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int | None = None
    rule_name: str | None = None


@dataclass
class RequestRateLimiter:
    enabled: bool
    window_seconds: int
    rules: dict[str, RateLimitRule]
    events: dict[tuple[str, str], deque[float]] = field(
        default_factory=lambda: defaultdict(deque)
    )

    def check(self, request: Request) -> RateLimitResult:
        if not self.enabled:
            return RateLimitResult(allowed=True)

        rule = self._match_rule(request)
        if rule is None:
            return RateLimitResult(allowed=True)

        key = (rule.name, self._client_key(request))
        now = time.monotonic()
        cutoff = now - self.window_seconds
        timestamps = self.events[key]

        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()

        if len(timestamps) >= rule.limit:
            retry_after = max(1, int(self.window_seconds - (now - timestamps[0])) + 1)
            return RateLimitResult(
                allowed=False,
                retry_after_seconds=retry_after,
                rule_name=rule.name,
            )

        timestamps.append(now)
        return RateLimitResult(allowed=True, rule_name=rule.name)

    def _match_rule(self, request: Request) -> RateLimitRule | None:
        method = request.method.upper()
        path = request.url.path
        for rule in self.rules.values():
            if path == rule.path and method in rule.methods:
                return rule
        return None

    def _client_key(self, request: Request) -> str:
        auth_header = request.headers.get("authorization", "").strip()
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
            if token:
                digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
                return f"token:{digest}"

        forwarded_for = request.headers.get("x-forwarded-for", "").strip()
        if forwarded_for:
            return f"ip:{forwarded_for.split(',')[0].strip()}"

        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"


def build_rate_limiter(
    *,
    enabled: bool,
    window_seconds: int,
    auth_sync_limit: int,
    exports_limit: int,
    account_delete_limit: int,
) -> RequestRateLimiter:
    rules = {
        "auth_sync": RateLimitRule(
            name="auth_sync",
            path="/api/v1/auth/sync",
            methods={"POST"},
            limit=auth_sync_limit,
        ),
        "exports": RateLimitRule(
            name="exports",
            path="/api/v1/exports/data",
            methods={"GET"},
            limit=exports_limit,
        ),
        "account_delete": RateLimitRule(
            name="account_delete",
            path="/api/v1/account/delete",
            methods={"POST"},
            limit=account_delete_limit,
        ),
    }
    return RequestRateLimiter(
        enabled=enabled,
        window_seconds=window_seconds,
        rules=rules,
    )


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        request_id = request.headers.get("X-Request-ID", "").strip() or uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        start = time.perf_counter()
        status_code: int | None = None

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            logger.exception(
                "unhandled_request request_id=%s method=%s path=%s",
                request_id,
                request.method,
                request.url.path,
            )
            response = JSONResponse(
                status_code=500,
                content=_payload(
                    "internal_server_error",
                    "An unexpected server error occurred.",
                ),
            )
            await response(scope, receive, send_with_request_id)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            client_host = request.client.host if request.client else "unknown"

            if status_code is None:
                logger.error(
                    "request_aborted request_id=%s method=%s path=%s duration_ms=%.2f client=%s",
                    request_id,
                    request.method,
                    request.url.path,
                    duration_ms,
                    client_host,
                )
                return

            level = logging.INFO
            if status_code >= 500:
                level = logging.ERROR
            elif status_code >= 400:
                level = logging.WARNING

            logger.log(
                level,
                "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%.2f client=%s",
                request_id,
                request.method,
                request.url.path,
                status_code,
                duration_ms,
                client_host,
            )


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        limiter: RequestRateLimiter | None = getattr(request.app.state, "rate_limiter", None)
        if limiter is None:
            await self.app(scope, receive, send)
            return

        result = limiter.check(request)
        if result.allowed:
            await self.app(scope, receive, send)
            return

        response = JSONResponse(
            status_code=429,
            content=_payload(
                "rate_limited",
                "Too many requests. Please try again shortly.",
                {
                    "scope": result.rule_name,
                    "retry_after_seconds": result.retry_after_seconds,
                },
            ),
        )
        if result.retry_after_seconds is not None:
            response.headers["Retry-After"] = str(result.retry_after_seconds)
        await response(scope, receive, send)
