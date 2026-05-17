from django.shortcuts import render, redirect
from django.utils import timezone
from .models import SessaoPicking, WebhookConfig, KPIDefinicao
from django.http import JsonResponse


def _requer_perfil(request, perfis_permitidos):
    """Verifica se o usuário tem um perfil permitido. Retorna redirect se não."""
    perfil = request.session.get('perfil_usuario')
    if not perfil or perfil not in perfis_permitidos:
        return redirect('login_coletor')
    return None


# ───────────────────────────────────────────────────────────────
# TELAS DE LOGIN INDUSTRIAL
# ───────────────────────────────────────────────────────────────

def tela_login_coletor(request):
    return render(request, 'portal_gateway.html', {
        'usuario_nome': request.session.get('usuario_nome'),
        'perfil_usuario': request.session.get('perfil_usuario'),
    })


def login_supervisor(request):
    return render(request, 'aguardandoSupervisor.html')


def login_colaborador(request):
    return render(request, 'Passo2colaborador.html')


def abertura_caixa(request):
    return render(request, 'aberturaDeCaixa.html')


def tela_picking(request):
    return render(request, 'enderecoDoPicking.html')


def encerrar_parcial(request):
    """View chamada pelo botão PARCIAL — encerra a sessão como PARCIAL no banco e redireciona para a tela final."""
    if request.method == 'POST':
        sessao_id = request.session.get('sessao_picking_id')
        if sessao_id:
            try:
                sessao = SessaoPicking.objects.select_related('pedido').get(id=sessao_id, ativa=True)
                # Encerra sessão como PARCIAL
                sessao.ativa = False
                sessao.fim = timezone.now()
                sessao.save()
                # Atualiza o pedido para PARCIAL
                sessao.pedido.status = 'PARCIAL'
                sessao.pedido.save()
            except SessaoPicking.DoesNotExist:
                pass
        return redirect('finalizacao_pick')
    return redirect('tela_picking')


def finalizacao_pick(request):
    sessao_id = request.session.get('sessao_picking_id')
    contexto = {'status_caixa': 'FINALIZADA'}
    if sessao_id:
        try:
            # Busca a sessao - pode ser ativa (se veio da tela diretamente) ou inativa (já encerrada)
            sessao = SessaoPicking.objects.select_related('pedido').filter(id=sessao_id).first()
            if not sessao:
                return render(request, 'FinalizacaoPICK.html', contexto)

            # Determina o status da caixa
            status_caixa = sessao.pedido.status if sessao.pedido else 'FINALIZADA'
            if status_caixa == 'PARCIAL':
                contexto['status_caixa'] = 'PARCIAL'
            elif status_caixa == 'FINALIZADO':
                contexto['status_caixa'] = 'FINALIZADA'

            # Usa fim real se encerrado, ou calcula até agora
            fim_ref = sessao.fim or timezone.now()
            if sessao.inicio:
                segundos_passados = (fim_ref - sessao.inicio).total_seconds()
                minutos = int(segundos_passados // 60)
                segundos = int(segundos_passados % 60)
                tempo = f"{minutos:02d}:{segundos:02d}"
                horas_passadas = segundos_passados / 3600
                pph = int(sessao.pecas_bipadas / max(horas_passadas, 0.001))
            else:
                tempo = "00:00"
                pph = 0

            acertos = 100 if sessao.erros == 0 else max(0, 100 - (sessao.erros * 5))
            # Conta caixas do colaborador hoje (FINALIZADO ou PARCIAL)
            sessoes_hoje = SessaoPicking.objects.filter(
                colaborador=sessao.colaborador,
                pedido__status__in=['FINALIZADO', 'PARCIAL'],
                inicio__date=timezone.now().date()
            )
            caixas_hoje = sessoes_hoje.count() or 1
            total_segundos_hoje = max(segundos_passados, 150) * caixas_hoje
            h = int(total_segundos_hoje // 3600)
            m = int((total_segundos_hoje % 3600) // 60)
            tempo_total = f"{h}:{m:02d}" if h > 0 else f"{m:02d}:00"

            contexto.update({
                'pedido_numero': sessao.pedido.numero_pedido if getattr(sessao, 'pedido', None) else 'Desconhecido',
                'total_pecas': sessao.pedido.total_pecas if getattr(sessao, 'pedido', None) else 0,
                'pecas_bipadas': sessao.pecas_bipadas,
                'pph': pph,
                'tempo': tempo,
                'streak': sessao.pecas_bipadas,
                'acertos': f"{acertos}%",
                'caixas_hoje': caixas_hoje,
                'tempo_total': tempo_total
            })
        except Exception as e:
            print("Erro no finalizacao_pick:", str(e))
    return render(request, 'FinalizacaoPICK.html', contexto)


# ───────────────────────────────────────────────────────────────
# AGING STOCK
# ───────────────────────────────────────────────────────────────

def aging_stock(request):
    redir = _requer_perfil(request, ['ADM', 'SUPERVISOR'])
    if redir:
        return redir

    from authentication.models import Usuario
    from .models import ItemPedido
    from django.db.models import Count, Min
    from django.utils import timezone

    supervisores = Usuario.objects.filter(perfil='SUPERVISOR', ativo=True).order_by('nome')

    # Agrupa itens pendentes por SKU, Cor e Endereço para a visão de Aging
    agrupado = ItemPedido.objects.filter(status='PENDENTE').values(
        'referencia', 'cor', 'endereco'
    ).annotate(
        qtd=Count('id'),
        data_mais_antiga=Min('pedido__data_criacao')
    ).order_by('data_mais_antiga')

    now = timezone.now()
    itens_aging = []
    
    total_skus = len(agrupado)
    criticos = 0
    atencao = 0

    for item in agrupado:
        # Pega a data de criação do pedido mais antigo desse SKU
        dt = item['data_mais_antiga']
        dias = (now - dt).days if dt else 0
        
        nivel = 'normal'
        if dias >= 90:
            nivel = 'critical'
            criticos += 1
        elif dias >= 60:
            nivel = 'warning'
            atencao += 1
            
        itens_aging.append({
            'sku': item['referencia'],
            'cor': item['cor'],
            'endereco': item['endereco'],
            'dias': dias,
            'qtd': item['qtd'],
            'nivel': nivel
        })

    return render(request, 'aging-stock.html', {
        'itens_aging': itens_aging,
        'total_skus': total_skus,
        'criticos': criticos,
        'atencao': atencao,
        'perfil_usuario': request.session.get('perfil_usuario', 'ADM'),
        'usuario_nome': request.session.get('usuario_nome', ''),
        'supervisores': supervisores,
    })


# ───────────────────────────────────────────────────────────────
# DASHBOARD KPIs — com dados reais do banco
# ───────────────────────────────────────────────────────────────

def dashboard_kpis(request):
    redir = _requer_perfil(request, ['ADM', 'SUPERVISOR'])
    if redir:
        return redir

    try:
        from django.db.models import Sum
        hoje = timezone.now().date()
        sessoes_hoje = SessaoPicking.objects.filter(inicio__date=hoje)

        caixas_finalizadas = sessoes_hoje.filter(ativa=False).count()
        total_pecas_bipadas = sessoes_hoje.aggregate(Sum('pecas_bipadas'))['pecas_bipadas__sum'] or 0
        total_erros = sessoes_hoje.aggregate(Sum('erros'))['erros__sum'] or 0

        # PPH global aproximado
        pph_global = 0
        if total_pecas_bipadas > 0 and sessoes_hoje.exists():
            total_horas = sum(
                max((s.fim or timezone.now()) - s.inicio, timezone.timedelta(seconds=1)).total_seconds() / 3600
                for s in sessoes_hoje
            )
            pph_global = int(total_pecas_bipadas / max(total_horas, 0.001))

        taxa_acerto = max(0, round(100 - (total_erros * 1.5), 1))
        operadores_ativos = sessoes_hoje.filter(ativa=True).values('colaborador').distinct().count()

        contexto = {
            'caixas_finalizadas': caixas_finalizadas,
            'total_pecas_bipadas': total_pecas_bipadas,
            'total_erros': total_erros,
            'pph_global': pph_global,
            'taxa_acerto': taxa_acerto,
            'operadores_ativos': operadores_ativos,
            'perfil_usuario': request.session.get('perfil_usuario', 'ADM'),
            'usuario_nome': request.session.get('usuario_nome', ''),
            'data_hoje': timezone.now().strftime('%d/%m/%Y'),
        }
    except Exception as e:
        contexto = {
            'error': str(e),
            'perfil_usuario': request.session.get('perfil_usuario', 'ADM'),
            'usuario_nome': request.session.get('usuario_nome', ''),
            'data_hoje': timezone.now().strftime('%d/%m/%Y'),
        }

    return render(request, 'dashboard_kpis.html', contexto)


# ───────────────────────────────────────────────────────────────
# GESTÃO DE FUNCIONÁRIOS
# ───────────────────────────────────────────────────────────────

def gerir_funcionarios(request):
    redir = _requer_perfil(request, ['ADM'])
    if redir:
        return redir

    from authentication.models import Usuario
    funcionarios = Usuario.objects.all().order_by('nome')
    supervisores = Usuario.objects.filter(perfil__in=['SUPERVISOR', 'ADM'], ativo=True).order_by('nome')
    return render(request, 'funcionarios.html', {
        'funcionarios': funcionarios,
        'supervisores': supervisores,
        'total': funcionarios.count(),
        'perfil_usuario': request.session.get('perfil_usuario', 'ADM'),
        'usuario_nome': request.session.get('usuario_nome', ''),
    })


# ───────────────────────────────────────────────────────────────
# GERIR KPIs
# ───────────────────────────────────────────────────────────────

def gerir_kpis(request):
    redir = _requer_perfil(request, ['ADM'])
    if redir:
        return redir

    from authentication.models import Usuario
    supervisores = Usuario.objects.filter(perfil__in=['SUPERVISOR', 'ADM'], ativo=True).order_by('nome')
    kpis = KPIDefinicao.objects.all().order_by('nome')
    return render(request, 'gerir-kpis.html', {
        'kpis': kpis,
        'supervisores': supervisores,
        'total': kpis.count(),
        'perfil_usuario': request.session.get('perfil_usuario', 'ADM'),
        'usuario_nome': request.session.get('usuario_nome', ''),
    })


# ───────────────────────────────────────────────────────────────
# WEBHOOKS
# ───────────────────────────────────────────────────────────────

def configuracao_webhooks(request):
    redir = _requer_perfil(request, ['ADM'])
    if redir:
        return redir

    webhooks = WebhookConfig.objects.all().order_by('-criado_em')
    return render(request, 'webhooks.html', {
        'webhooks': webhooks,
        'total': webhooks.count(),
        'perfil_usuario': request.session.get('perfil_usuario', 'ADM'),
        'usuario_nome': request.session.get('usuario_nome', ''),
    })


# ───────────────────────────────────────────────────────────────
# IMPORTAÇÃO
# ───────────────────────────────────────────────────────────────

def importacao_pedidos(request):
    redir = _requer_perfil(request, ['ADM'])
    if redir:
        return redir

    from django.db.models import Count, Sum
    from .models import Pedido, ItemPedido
    
    # Contadores reais do banco (Pedidos)
    pendentes = Pedido.objects.filter(status='ABERTO').count()
    processando = Pedido.objects.filter(status__in=['EM_PICKING', 'PARCIAL']).count()
    finalizados = Pedido.objects.filter(status='FINALIZADO').count()
    
    # Contadores de peças
    pecas_pendentes = ItemPedido.objects.filter(status='PENDENTE').count()
    
    # Últimos pedidos importados
    ultimos_pedidos = Pedido.objects.all().order_by('-data_criacao')[:10]

    return render(request, 'importacao.html', {
        'pendentes': pendentes,
        'pecas_pendentes': pecas_pendentes,
        'processando': processando,
        'finalizados': finalizados,
        'erros': 0,
        'ultimos_pedidos': ultimos_pedidos,
        'perfil_usuario': request.session.get('perfil_usuario', 'ADM'),
        'usuario_nome': request.session.get('usuario_nome', ''),
    })

# ───────────────────────────────────────────────────────────────
# PAINEL SUPERVISOR
# ───────────────────────────────────────────────────────────────

def painel_operacoes_supervisor(request):
    redir = _requer_perfil(request, ['ADM', 'SUPERVISOR'])
    if redir:
        return redir

    from authentication.models import Usuario
    sessoes_ativas = SessaoPicking.objects.filter(ativa=True).select_related('colaborador', 'pedido')
    return render(request, 'painel-operacoes.html', {
        'sessoes_ativas': sessoes_ativas,
        'perfil_usuario': request.session.get('perfil_usuario', 'SUPERVISOR'),
        'usuario_nome': request.session.get('usuario_nome', ''),
    })


# ───────────────────────────────────────────────────────────────
# HEARTBEAT MONITOR
# ───────────────────────────────────────────────────────────────

def heartbeat_monitor(request):
    redir = _requer_perfil(request, ['ADM'])
    if redir:
        return redir

    from authentication.models import Usuario
    colaboradores = Usuario.objects.filter(ativo=True).order_by('nome')
    return render(request, 'heartbeat.html', {
        'perfil_usuario': request.session.get('perfil_usuario', 'ADM'),
        'usuario_nome': request.session.get('usuario_nome', ''),
        'colaboradores': colaboradores,
    })