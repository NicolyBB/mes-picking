from django.urls import path
from . import views

urlpatterns = [
    path('api/v1/validar-cracha/', views.validar_cracha, name='api_validar_cracha'),
    path('api/v1/login-desktop/', views.login_desktop, name='api_login_desktop'),
    path('api/v1/logout/', views.logout_usuario, name='api_logout'),
    path('api/v1/set-senha/', views.api_set_senha, name='api_set_senha'),
]