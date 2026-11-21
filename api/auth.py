"""
Token login for the three kinds of account (admin, employer, job seeker).

The accounts live in three separate tables, as in the PHP version, so
django.contrib.auth is not used.  After a successful request:
    request.user  -> the Admin / Employer / User object
    request.auth  -> the AuthToken (request.auth.role says which kind)
"""
from django.utils import timezone
from rest_framework import authentication, exceptions, permissions

from portal.models import Admin, AuthToken, Employer, User

MODELS = {AuthToken.ADMIN: Admin, AuthToken.EMPLOYER: Employer, AuthToken.USER: User}


class TokenAuthentication(authentication.BaseAuthentication):
    keyword = "Token"

    def authenticate_header(self, request):
        return self.keyword

    def authenticate(self, request):
        parts = authentication.get_authorization_header(request).decode("latin-1").split()
        if not parts or parts[0].lower() != self.keyword.lower():
            return None
        if len(parts) != 2:
            raise exceptions.AuthenticationFailed("Invalid Authorization header.")
        token = AuthToken.objects.filter(
            key_hash=AuthToken.hash(parts[1]), expires__gt=timezone.now()).first()
        if token is None:
            raise exceptions.AuthenticationFailed("Invalid or expired token.")
        account = MODELS[token.role].objects.filter(pk=token.account_id).first()
        if account is None:
            raise exceptions.AuthenticationFailed("Account no longer exists.")
        if token.role != AuthToken.ADMIN and account.is_banned():
            token.delete()
            raise exceptions.AuthenticationFailed("Your account has been deactivated.")
        return account, token


class Deny(permissions.BasePermission):
    """Project default: a view with no explicit permission is closed."""

    def has_permission(self, request, view):
        return False


class _IsRole(permissions.BasePermission):
    role = None

    def has_permission(self, request, view):
        return bool(request.auth and request.auth.role == self.role)


class IsAdmin(_IsRole):
    role = AuthToken.ADMIN


class IsEmployer(_IsRole):
    role = AuthToken.EMPLOYER


class IsJobSeeker(_IsRole):
    role = AuthToken.USER
