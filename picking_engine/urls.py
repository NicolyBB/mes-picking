from django.urls import path
from . import views

urlpatterns = [
    # Fluxo do Coletor Datalogic (Sequência Lógica)
    path('coletor/supervisor/', views.login_supervisor, name='login_supervisor'),
    path('coletor/operador/', views.login_colaborador, name='login_colaborador'),
    path('coletor/abertura/', views.abertura_caixa, name='abertura_caixa'),
    path('coletor/picking/', views.tela_picking, name='tela_picking'), # Tela principal do Laser
    path('coletor/finalizar/', views.finalizacao_pick, name='finalizacao_pick'),
    
    # Dashboards de Gestão
    path('dashboard/aging-stock/', views.aging_stock, name='aging_stock'),
]