import logging
import os
import time
import hashlib

import jwt
import requests
from django.core.cache import cache
from django.http import JsonResponse


logger = logging.getLogger("gateway")

AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://localhost:8012")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "bookstore-jwt-secret")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_AUDIENCE = os.environ.get("JWT_AUDIENCE", "bookstore-clients")

PUBLIC_PATH_PREFIXES = (
    "/admin/login/",
    "/store/login/",
    "/store/register/",
    "/store/",
    "/store/book/",
    "/health/",
    "/metrics/",
)

PROTECTED_PATH_PREFIXES = (
    "/api/",
    "/store/profile/",
    "/store/cart/",
    "/store/add-to-cart/",
    "/store/remove-from-cart/",
    "/store/checkout/",
    "/store/orders/",
    "/store/review/",
)

ROLE_REQUIRED_PREFIXES = {
    "/admin/": {"admin", "staff"},
    "/store/profile/": {"customer", "admin", "staff"},
    "/store/cart/": {"customer", "admin", "staff"},
    "/store/add-to-cart/": {"customer", "admin", "staff"},
    "/store/remove-from-cart/": {"customer", "admin", "staff"},
    "/store/checkout/": {"customer", "admin", "staff"},
    "/store/orders/": {"customer", "admin", "staff"},
    "/store/review/": {"customer", "admin", "staff"},
}


def _is_public_path(path):
    if any(path.startswith(prefix) for prefix in PROTECTED_PATH_PREFIXES):
        return False
    return any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def _extract_token(request):
    token = request.session.get("access_token")
    if token:
        return token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]
    return None


def _validate_with_auth_service(token):
    token_fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
    cache_key = f"gateway:token:{token_fingerprint}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # Try auth service first
    try:
        response = requests.post(
            f"{AUTH_SERVICE_URL}/auth/validate/",
            json={"token": token},
            timeout=2,
        )
        if response.status_code == 200:
            claims = response.json().get("claims", {})
            if claims:
                # Normalize claims: auth-service uses 'sub' for user_id
                if 'sub' in claims and 'user_id' not in claims:
                    claims['user_id'] = claims['sub']
                cache.set(cache_key, claims, timeout=30)
                return claims
    except Exception:
        pass

    # Fallback: decode JWT token directly
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            options={'verify_aud': True}
        )
        # Normalize claims
        if 'user_id' not in payload and 'sub' in payload:
            payload['user_id'] = payload['sub']
        cache.set(cache_key, payload, timeout=30)
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")

    return None


class JWTValidationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.max_requests = int(os.environ.get("GATEWAY_RATE_LIMIT_MAX", "120"))
        self.window_seconds = int(os.environ.get("GATEWAY_RATE_LIMIT_WINDOW", "60"))

    def __call__(self, request):
        start = time.time()
        path = request.path
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR", "unknown")

        if not _is_public_path(path):
            rate_key = f"gateway:rl:{ip}:{int(time.time() // self.window_seconds)}"
            current = cache.get(rate_key, 0) + 1
            cache.set(rate_key, current, timeout=self.window_seconds)
            if current > self.max_requests:
                return JsonResponse({"error": "Rate limit exceeded"}, status=429)

        claims = None
        if not _is_public_path(path):
            token = _extract_token(request)
            claims = _validate_with_auth_service(token) if token else None

            if any(path.startswith(prefix) for prefix in PROTECTED_PATH_PREFIXES) and not claims:
                return JsonResponse({"error": "Unauthorized"}, status=401)

            for prefix, roles in ROLE_REQUIRED_PREFIXES.items():
                if path.startswith(prefix) and claims:
                    if claims.get("role") not in roles:
                        return JsonResponse({"error": "Forbidden"}, status=403)

        response = self.get_response(request)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%s ip=%s role=%s",
            request.method,
            path,
            getattr(response, "status_code", 0),
            duration_ms,
            ip,
            claims.get("role") if isinstance(claims, dict) else "",
        )
        return response
