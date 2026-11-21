from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    # path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    # path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # path("api/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    # path("api/auth/logout/", TokenBlacklistView.as_view(), name="token_blacklist"),
    path("api/", include("portal.api.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)