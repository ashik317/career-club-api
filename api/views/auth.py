from datetime import timedelta
import logging
from django.db import transaction
from django.utils import timezone
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from dj_rest_auth.registration.views import SocialLoginView
from dj_rest_auth.views import LoginView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from urllib.parse import urlencode
from django.http import HttpResponseRedirect
from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import (
    CreateAPIView,
    RetrieveUpdateAPIView
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from authentication.models import EmailVerification, User
from common.throttles import RegisterRateThrottle, EmailRateThrottle, LoginRateThrottle
from organisations.models import Organisation, OrganisationUser
from api.serializers.auth import (
    EmailVerifySerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
)
from utils import send_password_reset_email, send_verification_email

logger = logging.getLogger(__name__)


class AccountRegistrationView(CreateAPIView):
    serializer_class = UserRegistrationSerializer
    throttle_classes = [RegisterRateThrottle]
    permission_classes = [AllowAny]

    def get_queryset(self):
        return User.objects.all()


class EmailVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmailVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Email verified successfully. You can now log in."},
            status=status.HTTP_200_OK,
        )


class ResendVerificationView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [EmailRateThrottle]

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response(
                {"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email, is_active=False)
        except User.DoesNotExist:
            return Response(
                {"detail": "No unverified user found with this email."},
                status=status.HTTP_404_NOT_FOUND,
            )

        code = EmailVerification.make_code()

        try:
            verification = EmailVerification.objects.get(user=user)
            verification.code = code
            verification.is_verified = False
            verification.expires_at = timezone.now() + timedelta(minutes=2)
            verification.save()
        except EmailVerification.DoesNotExist:
            EmailVerification.objects.create(
                user=user,
                code=code,
            )
        send_verification_email(user, code)
        return Response(
            {"detail": "Verification code resent."}, status=status.HTTP_200_OK
        )


class CustomLoginView(LoginView):
    throttle_classes = [LoginRateThrottle]
    permission_classes = [AllowAny]


def get_user_type_label(user):
    organisation_user = user.organisation_users.first()
    return organisation_user.role if organisation_user else None


class GoogleLoginView(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    callback_url = settings.GOOGLE_CALLBACK_URL
    client_class = OAuth2Client

    def post(self, request, *args, **kwargs):
        self.request = request

        data = (
            request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        )

        access_token = data.get("access_token")

        # Support either a Google access token or authorization code.
        if not access_token:
            code = data.get("code")

            if not code:
                return Response(
                    {"detail": "access_token or code is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                access_token = self._exchange_code_for_access_token(code)
            except Exception:
                logger.exception("Google authorization-code exchange failed.")
                return Response(
                    {"detail": "Unable to authenticate with Google."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            data["access_token"] = access_token
            data.pop("code", None)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        self.serializer = serializer
        self.login()

        user = self.user

        self._create_default_organisation(user)

        return self.get_response()

    def _create_default_organisation(self, user):
        with transaction.atomic():
            locked_user = User.objects.select_for_update().get(pk=user.pk)

            if locked_user.get_organisation():
                return

            organisation = Organisation.objects.create(
                name=(
                    f"{locked_user.first_name or locked_user.email}" "'s Organisation"
                )
            )

            OrganisationUser.objects.create(
                user=locked_user,
                organisation=organisation,
            )

    def _exchange_code_for_access_token(self, code):
        adapter = self.adapter_class(self.request)
        provider = adapter.get_provider()
        app = provider.get_app(self.request)

        client = self.client_class(
            self.request,
            app.client_id,
            app.secret,
            adapter.access_token_method,
            adapter.access_token_url,
            self.callback_url,
            scope_delimiter=adapter.scope_delimiter,
            headers=adapter.headers,
            basic_auth=adapter.basic_auth,
        )

        token = client.get_access_token(code)
        return token["access_token"]

    def get_response(self):
        response = super().get_response()
        response.data["user"]["user_type"] = get_user_type_label(self.user)
        return response


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [EmailRateThrottle]

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response(
                {"email": "This field is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError

        try:
            validate_email(email)
        except ValidationError:
            return Response(
                {"email": "Enter a valid email address."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(email__iexact=email).first()

        if not user:
            return Response(
                {"email": "No account found with this email address."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user.is_active:
            return Response(
                {"email": "This account is inactive. Please contact support."},
                status=status.HTTP_403_FORBIDDEN,
            )

        send_password_reset_email(user)
        return Response(
            {"detail": "Password reset link has been sent to your email."},
            status=status.HTTP_200_OK,
        )


class SetForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (
            TypeError,
            ValueError,
            OverflowError,
            User.DoesNotExist,
        ):
            params = urlencode({"error": "invalid_link"})
            return HttpResponseRedirect(
                f"{settings.FRONTEND_URL}/auth/password-error?{params}"
            )

        if not default_token_generator.check_token(user, token):
            params = urlencode({"error": "expired_or_invalid"})
            return HttpResponseRedirect(
                f"{settings.FRONTEND_URL}/auth/password-error?{params}"
            )

        params = urlencode({"uid": uidb64, "token": token})
        return HttpResponseRedirect(
            f"{settings.FRONTEND_URL}/auth/set-password?{params}"
        )

    def post(self, request, uidb64, token):
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        if not new_password or not confirm_password:
            return Response(
                {"detail": "Both password fields are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != confirm_password:
            return Response(
                {"detail": "Passwords do not match."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (
            TypeError,
            ValueError,
            OverflowError,
            User.DoesNotExist,
        ):
            return Response(
                {"detail": "Invalid reset link."}, status=status.HTTP_400_BAD_REQUEST
            )

        if not default_token_generator.check_token(user, token):
            return Response(
                {"detail": "Reset link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)

        user.save()
        return Response(
            {"detail": "Password has been reset successfully."},
            status=status.HTTP_200_OK,
        )


class UpdatePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        if not new_password or not confirm_password:
            return Response(
                {"detail": "New password and confirm password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != confirm_password:
            return Response(
                {"detail": "Passwords do not match."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_has_password = request.user.has_usable_password()

        if user_has_password:
            old_password = request.data.get("old_password")
            if not old_password:
                return Response(
                    {"detail": "Old password is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not request.user.check_password(old_password):
                return Response(
                    {"detail": "Old password is incorrect."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if old_password == new_password:
                return Response(
                    {"detail": "New password must be different from old password."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        request.user.set_password(new_password)
        request.user.save()

        detail = (
            "Password changed successfully."
            if user_has_password
            else "Password set successfully. You can now log in with your email and password."
        )
        return Response({"detail": detail}, status=status.HTTP_200_OK)


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh_token")

            if not refresh_token:
                return Response(
                    {"error": "Refresh token is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {"detail": "Logged out successfully."},
                status=status.HTTP_200_OK,
            )

        except TokenError:
            return Response(
                {"error": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class UserProfileView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user