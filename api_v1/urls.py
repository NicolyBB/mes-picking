from django.urls import path
from . import views

urlpatterns = [
    # Rota que o script.js do Front-end vai chamar via fetch()
    path('validar-bip/', views.validar_leitura_laser, name='api_validar_bip'),
    path('importar-pedidos/', views.importar_pedidos_excel, name='api_importar_excel'),
    path('iot-status/', views.status_hardware_iot, name='api_iot_esp32'),
]
