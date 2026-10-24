from django.urls import path

from . import views

# Mounted under /api/auth/.
urlpatterns = [
    path('token/', views.LoginView.as_view(), name='auth-token'),
    path('register/', views.RegisterView.as_view(), name='auth-register'),
    path('logout/', views.LogoutView.as_view(), name='auth-logout'),
    path('me/', views.CurrentUserView.as_view(), name='auth-me'),
]
