from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(url="/api/")),
    path("api/", include("portal.api.urls")),
]

if settings.DEBUG:
    # Profile pictures only.  CVs live in PRIVATE_MEDIA_ROOT and are served
    # through a token-protected endpoint.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
