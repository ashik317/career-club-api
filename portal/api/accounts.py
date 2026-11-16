"""
Sign-up, login, OTP verification and logout.

Employers and job seekers follow the same steps, so the endpoints are built
once by make_account_views() and registered twice in urls.py.

    POST signup/       -> account created (unverified), OTP e-mailed
    POST verify-otp/   {email, otp}       -> account verified
    POST resend-otp/   {email, password}  -> new OTP e-mailed
    POST login/        {email, password}  -> {"token": ..., "account": ...}
    POST logout/       (token)            -> token deleted
    GET  me/           (token)            -> the logged-in account
"""
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from ..models import AuthToken
from .serializers import LoginSerializer, OTPSerializer


class AuthThrottle(AnonRateThrottle):
    """Slows down password and OTP guessing (per IP address)."""

    scope = "auth"


def public(methods):
    """
    An endpoint that needs no token, with the auth throttle applied.  Any
    Authorization header is ignored, so a stale token cannot block a login.
    """
    def decorator(view):
        view = throttle_classes([AuthThrottle])(view)
        view = authentication_classes([])(view)
        view = permission_classes([AllowAny])(view)
        return api_view(methods)(view)
    return decorator


def error(message, code, http_status=status.HTTP_400_BAD_REQUEST):
    return Response({"detail": message, "code": code}, status=http_status)


def send_otp(account):
    account.issue_otp()
    try:
        send_mail(
            subject="Confirm your email address",
            message=f"Please verify your email with this OTP.\nYour OTP is: {account.otp}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[account.email],
            html_message=("Please verify your email with this given OTP<br>"
                          f"Your OTP is: <b>{account.otp}</b>"),
        )
        return True
    except Exception:
        return False


def check_credentials(model, data):
    """Returns (account, None) or (None, error response)."""
    serializer = LoginSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    account = model.objects.filter(email__iexact=serializer.validated_data["email"]).first()
    if account is None or not account.check_password(serializer.validated_data["password"]):
        return None, error("Login failed. Invalid email or password.", "invalid_credentials",
                           status.HTTP_401_UNAUTHORIZED)
    return account, None


def make_account_views(role, model, signup_serializer, account_serializer, permission):
    label = "Employer" if role == AuthToken.EMPLOYER else "User"

    @public(["POST"])
    def signup(request):
        serializer = signup_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = serializer.save()
        sent = send_otp(account)
        return Response({
            "detail": "Account created. Verify it with the OTP sent to your email."
                      if sent else "Account created, but the OTP email could not be sent. "
                                   "Use resend-otp.",
            "account": account_serializer(account).data,
        }, status=status.HTTP_201_CREATED)

    @public(["POST"])
    def verify_otp(request):
        serializer = OTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = model.objects.filter(
            email__iexact=serializer.validated_data["email"]).first()
        if account is None or account.is_verified:
            return error("Invalid OTP. Please write correctly.", "invalid_otp")
        if account.verify_otp(serializer.validated_data["otp"]):
            return Response({"detail": "Registration Successfully."})
        if account.otp is None:
            return error("Too many wrong attempts. Request a new code with resend-otp.",
                         "otp_voided")
        return error("Invalid OTP. Please write correctly.", "invalid_otp")

    @public(["POST"])
    def resend_otp(request):
        # The password is required so nobody can make us e-mail a stranger.
        account, failure = check_credentials(model, request.data)
        if failure:
            return failure
        if account.is_verified:
            return error("This account is already verified.", "already_verified")
        if not send_otp(account):
            return error("The verification email could not be sent.", "mail_failed",
                         status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"detail": "A new code has been sent."})

    @public(["POST"])
    def login(request):
        account, failure = check_credentials(model, request.data)
        if failure:
            return failure
        if not account.is_verified:
            send_otp(account)
            return error("Account not verified. A new OTP has been sent to your email.",
                         "unverified", status.HTTP_403_FORBIDDEN)
        if account.is_banned():
            until = timezone.localtime(account.bantime).strftime("%Y-%m-%d %H:%M")
            return error(f"{label} account is banned until {until}.", "banned",
                         status.HTTP_403_FORBIDDEN)
        return Response({"token": AuthToken.issue(role, account),
                         "account": account_serializer(account).data})

    @api_view(["GET"])
    @permission_classes([permission])
    def me(request):
        return Response(account_serializer(request.user, context={"request": request}).data)

    return {"signup": signup, "verify_otp": verify_otp, "resend_otp": resend_otp,
            "login": login, "me": me}


@api_view(["POST"])
@permission_classes([AllowAny])
def logout(request):
    """Deletes the token that was sent with the request (any role)."""
    if request.auth:
        request.auth.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
