"""Root URLconf: the admin, the REST API under /api/ and its OpenAPI docs."""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework import routers

from rentals.urls import router as rentals_router

# One API root listing every viewset.
router = routers.DefaultRouter()
router.registry.extend(rentals_router.registry)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/', include('rentals.urls')),
    path('api/auth/', include('accounts.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
