from django.urls import path
from rest_framework import routers

from . import views

router = routers.SimpleRouter()
router.register(r'categories', views.CategoryViewSet)
router.register(r'locations', views.LocationViewSet)
router.register(r'equipment', views.EquipmentViewSet, basename='equipment')
router.register(r'reservations', views.ReservationViewSet, basename='reservation')
router.register(r'students', views.StudentViewSet, basename='student')

# Mounted under /api/ next to the router.
urlpatterns = [
    path('me/history/', views.MyHistoryView.as_view(), name='my-history'),
    path('students/<int:pk>/history/', views.StudentHistoryView.as_view(), name='student-history'),
]
