from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    # -----------------------------------------------------------------
    # Dashboards de Gestão
    # -----------------------------------------------------------------
    path('dashboard/', views.dashboard_kpis, name='dashboard_kpis'),
    path('dashboard/aging-stock/', views.aging_stock, name='aging_stock'),
    path('dashboard/funcionarios/', views.gerir_funcionarios, name='funcionarios'),
    path('dashboard/gerir-kpis/', views.gerir_kpis, name='gerir_kpis'),
    path('dashboard/webhooks/', views.configuracao_webhooks, name='webhooks'),
    path('dashboard/importacao/', views.importacao_pedidos, name='importacao'),
    path('dashboard/painel-operacoes/', views.painel_operacoes_supervisor, name='painel_operacoes'),

    # -----------------------------------------------------------------
    # Fluxo do Coletor Industrial
    # -----------------------------------------------------------------
    path('coletor/supervisor/', views.login_supervisor, name='login_supervisor'),
    path('coletor/operador/', views.login_colaborador, name='login_colaborador'),
    path('coletor/abertura/', views.abertura_caixa, name='abertura_caixa'),
    path('coletor/picking/', views.tela_picking, name='tela_picking'),
    path('coletor/finalizar/', views.finalizacao_pick, name='finalizacao_pick'),
    path('coletor/parcial/', views.encerrar_parcial, name='encerrar_parcial'),

    # -----------------------------------------------------------------
    # API — Picking Engine
    # -----------------------------------------------------------------
    path('api/picking/iniciar/', api_views.iniciar_picking, name='api_iniciar_picking'),
    path('api/picking/validar-bip/', api_views.validar_bip, name='api_validar_bip'),
    path('api/picking/pular-sku/', api_views.pular_sku, name='api_pular_sku'),
    path('api/picking/danificada/', api_views.reportar_danificada, name='api_danificada'),
    path('api/picking/status/', api_views.status_sessao, name='api_status_sessao'),

    # -----------------------------------------------------------------
    # API — Dashboard KPIs (tempo real)
    # -----------------------------------------------------------------
    path('api/kpis/dados/', api_views.api_kpis_tempo_real, name='api_kpis_dados'),

    # -----------------------------------------------------------------
    # API — Webhooks CRUD
    # -----------------------------------------------------------------
    path('api/webhooks/', api_views.api_webhooks, name='api_webhooks'),
    path('api/webhooks/<int:pk>/', api_views.api_webhook_detalhe, name='api_webhook_detalhe'),
    path('api/webhooks/<int:pk>/testar/', api_views.api_webhook_testar, name='api_webhook_testar'),

    # -----------------------------------------------------------------
    # API — KPI Definitions CRUD
    # -----------------------------------------------------------------
    path('api/kpis-config/', api_views.api_kpis_config, name='api_kpis_config'),
    path('api/kpis-config/<int:pk>/', api_views.api_kpi_detalhe, name='api_kpi_detalhe'),

    # -----------------------------------------------------------------
    # API — Funcionários CRUD
    # -----------------------------------------------------------------
    path('api/funcionarios/', api_views.api_funcionarios, name='api_funcionarios'),
    path('api/funcionarios/<int:pk>/', api_views.api_funcionario_detalhe, name='api_funcionario_detalhe'),

    # -----------------------------------------------------------------
    # API — Aging Stock / Historicos
    # -----------------------------------------------------------------
    path('api/aging-stock/resolver/', api_views.api_resolver_aging, name='api_resolver_aging'),
    path('api/aging-stock/historico/', api_views.api_historico_aging, name='api_historico_aging'),

    # -----------------------------------------------------------------
    # API — Funcionário Logs / Equipe Supervisor
    # -----------------------------------------------------------------
    path('api/funcionarios/<int:pk>/logs/', api_views.api_funcionario_logs, name='api_funcionario_logs'),
    path('api/supervisor/equipe/', api_views.api_equipe_supervisor, name='api_equipe_supervisor'),

    # -----------------------------------------------------------------
    # API — Heartbeat / Hardware Monitor
    # -----------------------------------------------------------------
    path('api/heartbeat/', api_views.api_heartbeat, name='api_heartbeat'),
    path('api/heartbeat/status/', api_views.api_heartbeat_status, name='api_heartbeat_status'),
    path('api/heartbeat/manage/', api_views.api_heartbeat_manage, name='api_heartbeat_manage'),
    path('dashboard/heartbeat/', views.heartbeat_monitor, name='heartbeat_monitor'),

    # Raiz
    path('', views.tela_login_coletor, name='login_coletor'),
]