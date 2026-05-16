from django.urls import path
from . import views

urlpatterns = [
    # Rota consumida pelo motor AJAX para login em milissegundos
    path('api/v1/validar-cracha/', views.validar_cracha, name='api_validar_cracha'),
]