import jwt
import os
import requests
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.core.cache import cache
from django.contrib.auth.models import AnonymousUser
import hashlib

AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://auth-service:8000")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "your_secret_key")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")


class SimpleUser:
    """Simplified user object to replace Django User for JWT authentication"""
    def __init__(self, user_id, role=None):
        self.id = user_id
        self.role = role
        self.is_authenticated = True

    @property
    def is_anonymous(self):
        return False


class JWTAuthentication(BaseAuthentication):
    """JWT Authentication for service-to-service communication"""

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header:
            return None

        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ')[1]
        return self._validate_token(token)

    def _validate_token(self, token):
        """Validate JWT token using auth service or direct JWT verification"""
        token_fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
        cache_key = f"cart:token:{token_fingerprint}"
        cached = cache.get(cache_key)
        if cached is not None:
            user = SimpleUser(cached.get('user_id'), cached.get('role'))
            return (user, token)

        try:
            # First try to validate with auth service
            response = requests.post(
                f"{AUTH_SERVICE_URL}/auth/validate/",
                json={"token": token},
                timeout=2,
            )
            if response.status_code == 200:
                claims = response.json().get("claims", {})
                if claims:
                    user_data = {
                        'user_id': claims.get('user_id'),
                        'role': claims.get('role')
                    }
                    cache.set(cache_key, user_data, timeout=30)
                    user = SimpleUser(claims.get('user_id'), claims.get('role'))
                    return (user, token)
        except Exception:
            pass

        # Fallback: direct JWT validation
        try:
            # Decode with proper audience verification or disable it
            payload = jwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM],
                audience='bookstore-clients',
                options={'verify_aud': True}
            )
            user_data = {
                'user_id': payload.get('user_id'),
                'role': payload.get('role')
            }
            cache.set(cache_key, user_data, timeout=30)
            user = SimpleUser(payload.get('user_id'), payload.get('role'))
            return (user, token)
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid token')

        raise AuthenticationFailed('Authentication failed')


class OptionalJWTAuthentication(JWTAuthentication):
    """Optional JWT Authentication - allows unauthenticated requests to pass through"""

    def authenticate(self, request):
        try:
            result = super().authenticate(request)
            if result is None:
                # Return anonymous user instead of None to allow unauthenticated access
                return (AnonymousUser(), None)
            return result
        except AuthenticationFailed:
            # If token is invalid/expired, allow anonymous access instead of failing
            return (AnonymousUser(), None)