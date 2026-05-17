from django.urls import path
from . import views

urlpatterns = [
    # Rota que o script.js do Front-end vai chamar via fetch()
    path('validar-bip/', views.validar_leitura_laser, name='api_validar_bip'),
    path('importar-pedidos/', views.importar_pedidos_excel, name='api_importar_excel'),
    path('exportar-pedidos/', views.exportar_pedidos_csv, name='api_exportar_csv'),
    path('exportar-pedido/<int:pedido_id>/', views.exportar_pedido_individual_csv, name='api_exportar_pedido_csv'),
    path('iot-status/', views.status_hardware_iot, name='api_iot_esp32'),
]
