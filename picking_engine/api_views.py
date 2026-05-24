from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from datetime import timedelta
from .models import Pedido, ItemPedido, SessaoPicking, WebhookConfig, KPIDefinicao, HeartbeatLog, LogAgingStock, ExcecaoPicking, MetaGlobal
from authentication.models import Usuario
import threading
import requests as req_lib
import json
import time


# ═══════════════════════════════════════════════════════════════
#  HELPERS E SEGURANÇA
# ═══════════════════════════════════════════════════════════════

def _check_api_permission(request, allowed_profiles):
    """Garante que apenas perfis autorizados possam manipular a API (Prevenção de Escalada de Privilégio)"""
    perfil = request.session.get('perfil_usuario')
    if not perfil or perfil not in allowed_profiles:
        return False
    return True

def _calcular_kpis(sessao):
    segundos_passados = max((timezone.now() - sessao.inicio).total_seconds(), 0)
    minutos = int(segundos_passados // 60)
    segundos = int(segundos_passados % 60)
    tempo = f"{minutos:02d}:{segundos:02d}"
    horas_passadas = segundos_passados / 3600
    pph = int(sessao.pecas_bipadas / max(horas_passadas, 0.001))
    return {"tempo": tempo, "pph": pph, "streak": sessao.pecas_bipadas, "erros": sessao.erros}


def _serializar_item(item):
    if not item:
        return None
    return {
        "id": item.id,
        "referencia": item.referencia,
        "cor": item.cor,
        "tamanho": item.tamanho,
        "endereco": item.endereco,
        "codigo_barras": item.codigo_barras,
    }


def _disparar_webhook_async(webhook, payload):
    """Dispara webhook em thread separada para não bloquear o operador (<200ms)."""
    def _fire():
        try:
            req_lib.post(webhook.url_destino, json=payload, timeout=5)
            webhook.ultimo_disparo = timezone.now()
            webhook.save(update_fields=['ultimo_disparo'])
        except Exception as e:
            print(f"Webhook {webhook.id} falhou: {e}")
    t = threading.Thread(target=_fire, daemon=True)
    t.start()


# ═══════════════════════════════════════════════════════════════
#  PICKING — ABERTURA DE CAIXA
# ═══════════════════════════════════════════════════════════════

@csrf_exempt
@api_view(['POST'])
@transaction.atomic
def iniciar_picking(request):
    numero_pedido = request.data.get('numero_pedido', '').strip()
    colaborador_id = request.session.get('colaborador_id')

    try:
        # Bloqueio em nível de linha (Prevenção de Condição de Corrida)
        pedido = Pedido.objects.select_for_update().get(numero_pedido=numero_pedido, status__in=['ABERTO', 'PARCIAL', 'EM_PICKING'])
    except Pedido.DoesNotExist:
        return Response({"status": "erro", "mensagem": f"Pedido '{numero_pedido}' não encontrado ou já finalizado."}, status=404)

    if colaborador_id:
        SessaoPicking.objects.filter(colaborador_id=colaborador_id, ativa=True).update(ativa=False)

    primeiro_item = pedido.itens.filter(status='PENDENTE').order_by('ordem').first()
    colaborador = Usuario.objects.filter(id=colaborador_id).first() if colaborador_id else None

    sessao = SessaoPicking.objects.create(pedido=pedido, colaborador=colaborador, item_atual=primeiro_item)
    pedido.status = 'EM_PICKING'
    pedido.save()
    request.session['sessao_picking_id'] = sessao.id

    total_itens = pedido.itens.count()
    bipados = pedido.itens.filter(status='BIPADO').count()
    itens_pendentes = pedido.itens.filter(status='PENDENTE').order_by('ordem')
    itens_pendentes_serializados = [_serializar_item(it) for it in itens_pendentes]

    return Response({
        "status": "sucesso",
        "sessao_id": sessao.id,
        "pedido": {
            "id": pedido.id, "numero": pedido.numero_pedido, "cliente": pedido.cliente,
            "total_pecas": total_itens, "pecas_bipadas": bipados, "peso_bruto": str(pedido.peso_bruto),
        },
        "proximo_item": _serializar_item(primeiro_item),
        "itens_pendentes": itens_pendentes_serializados,
    })


# ═══════════════════════════════════════════════════════════════
#  PICKING — VALIDAR BIP
# ═══════════════════════════════════════════════════════════════

@csrf_exempt
@api_view(['POST'])
@transaction.atomic
def validar_bip(request):
    codigo = request.data.get('codigo', '').strip()
    sessao_id = request.session.get('sessao_picking_id') or request.data.get('sessao_id')

    if not sessao_id:
        return Response({"status": "erro", "mensagem": "Sessão não encontrada. Reinicie o picking."}, status=400)

    try:
        # Trava a sessão atual no banco para evitar multi-bips concorrentes
        sessao = SessaoPicking.objects.select_for_update().select_related('pedido', 'item_atual').get(id=sessao_id, ativa=True)
    except SessaoPicking.DoesNotExist:
        return Response({"status": "erro", "mensagem": "Sessão inválida ou encerrada."}, status=404)

    item_esperado = sessao.item_atual
    if not item_esperado:
        return Response({"status": "finalizado", "mensagem": "Todos os itens desta caixa foram bipados!"})

    # CORREÇÃO: normaliza ambos os lados para evitar falhas por case/espaço do laser
    codigo_normalizado = codigo.strip().upper()
    barras_normalizado = item_esperado.codigo_barras.strip().upper()
    ref_normalizado = item_esperado.referencia.strip().upper()

    if codigo_normalizado == barras_normalizado or codigo_normalizado == ref_normalizado:
        item_esperado.status = 'BIPADO'
        item_esperado.save()
        
        # Evitando race conditions na contagem matemática com F()
        sessao.pecas_bipadas = F('pecas_bipadas') + 1
        sessao.save(update_fields=['pecas_bipadas'])
        sessao.refresh_from_db(fields=['pecas_bipadas'])

        proximo = sessao.pedido.itens.filter(status='PENDENTE').order_by('ordem').first()
        sessao.item_atual = proximo
        sessao.save()

        total = sessao.pedido.itens.count()
        bipados = sessao.pecas_bipadas

        if not proximo:
            sessao.pedido.status = 'FINALIZADO'
            sessao.pedido.save()
            sessao.ativa = False
            sessao.fim = timezone.now()
            sessao.save()
            return Response({
                "status": "finalizado",
                "mensagem": "✅ Caixa completa! Todos os itens bipados.",
                "progresso": {"atual": bipados, "total": total},
            })

        return Response({
            "status": "sucesso",
            "mensagem": "✅ Peça validada!",
            "progresso": {"atual": bipados, "total": total},
            "proximo_item": _serializar_item(proximo),
            "kpis": _calcular_kpis(sessao)
        })
    else:
        sessao.erros = F('erros') + 1
        sessao.save(update_fields=['erros'])
        sessao.refresh_from_db(fields=['erros'])
        
        return Response({
            "status": "erro",
            "mensagem": f"❌ Código incorreto. Esperado: {item_esperado.referencia} no endereço {item_esperado.endereco}",
            "item_esperado": _serializar_item(item_esperado),
        }, status=400)


# ═══════════════════════════════════════════════════════════════
#  PICKING — PULAR SKU
# ═══════════════════════════════════════════════════════════════

@csrf_exempt
@api_view(['POST'])
def pular_sku(request):
    sessao_id = request.session.get('sessao_picking_id') or request.data.get('sessao_id')
    motivo = request.data.get('motivo', '').strip()
    try:
        sessao = SessaoPicking.objects.get(id=sessao_id, ativa=True)
    except SessaoPicking.DoesNotExist:
        return Response({"status": "erro", "mensagem": "Sessão inválida."}, status=404)

    item_pulado = sessao.item_atual
    if item_pulado:
        item_pulado.status = 'PULADO'
        item_pulado.save()

        # Incrementar peças bipadas para progresso da barra
        sessao.pecas_bipadas = F('pecas_bipadas') + 1
        sessao.save(update_fields=['pecas_bipadas'])
        sessao.refresh_from_db(fields=['pecas_bipadas'])

        # Registra a exceção no banco com o motivo do operador
        if motivo:
            ExcecaoPicking.objects.create(
                sessao=sessao,
                item=item_pulado,
                motivo_operador=motivo,
                status='PENDENTE'
            )

        # Dispara webhook FALTA_PECA se houver configurado
        webhooks_falta = WebhookConfig.objects.filter(evento_gatilho='FALTA_PECA', ativo=True)
        for wh in webhooks_falta:
            _disparar_webhook_async(wh, {
                "event": "FALTA_PECA",
                "sku": item_pulado.referencia,
                "endereco": item_pulado.endereco,
                "motivo": motivo,
                "sessao_id": sessao.id,
            })

    proximo = sessao.pedido.itens.filter(status='PENDENTE').order_by('ordem').first()
    sessao.item_atual = proximo
    sessao.save()

    total_pecas = sessao.pedido.itens.count()

    if not proximo:
        sessao.pedido.status = 'FINALIZADO'
        sessao.pedido.save()
        sessao.ativa = False
        sessao.fim = timezone.now()
        sessao.save()

    return Response({
        "status": "sucesso",
        "mensagem": "Item pulado. Indo para o próximo.",
        "proximo_item": _serializar_item(proximo) if proximo else None,
        "kpis": _calcular_kpis(sessao),
        "progresso": {"atual": sessao.pecas_bipadas, "total": total_pecas}
    })


# ═══════════════════════════════════════════════════════════════
#  PICKING — PEÇA DANIFICADA
# ═══════════════════════════════════════════════════════════════

@csrf_exempt
@api_view(['POST'])
def reportar_danificada(request):
    sessao_id = request.session.get('sessao_picking_id') or request.data.get('sessao_id')
    motivo = request.data.get('motivo', '').strip()
    try:
        sessao = SessaoPicking.objects.get(id=sessao_id, ativa=True)
    except SessaoPicking.DoesNotExist:
        return Response({"status": "erro", "mensagem": "Sessão inválida."}, status=404)

    item_danificado = sessao.item_atual
    if item_danificado:
        item_danificado.status = 'DANIFICADO'
        item_danificado.save()

        # Incrementar peças bipadas para progresso da barra
        sessao.pecas_bipadas = F('pecas_bipadas') + 1
        sessao.save(update_fields=['pecas_bipadas'])
        sessao.refresh_from_db(fields=['pecas_bipadas'])

        # Registra a exceção no banco com o motivo do operador
        if motivo:
            ExcecaoPicking.objects.create(
                sessao=sessao,
                item=item_danificado,
                motivo_operador=motivo,
                status='PENDENTE'
            )

    proximo = sessao.pedido.itens.filter(status='PENDENTE').order_by('ordem').first()
    sessao.item_atual = proximo
    sessao.save()

    total_pecas = sessao.pedido.itens.count()

    if not proximo:
        sessao.pedido.status = 'FINALIZADO'
        sessao.pedido.save()
        sessao.ativa = False
        sessao.fim = timezone.now()
        sessao.save()

    return Response({
        "status": "sucesso",
        "mensagem": "Peça marcada como DANIFICADA. Direcione ao cesto de divergência.",
        "proximo_item": _serializar_item(proximo) if proximo else None,
        "kpis": _calcular_kpis(sessao),
        "progresso": {"atual": sessao.pecas_bipadas, "total": total_pecas}
    })


# ═══════════════════════════════════════════════════════════════
#  PICKING — STATUS SESSÃO
# ═══════════════════════════════════════════════════════════════

@api_view(['GET'])
def status_sessao(request):
    sessao_id = request.session.get('sessao_picking_id')
    if not sessao_id:
        return Response({"status": "sem_sessao"}, status=404)

    try:
        sessao = SessaoPicking.objects.select_related('pedido', 'item_atual').get(id=sessao_id, ativa=True)
    except SessaoPicking.DoesNotExist:
        return Response({"status": "sem_sessao"}, status=404)

    total = sessao.pedido.itens.count()
    itens_pendentes = sessao.pedido.itens.filter(status='PENDENTE').order_by('ordem')
    itens_pendentes_serializados = [_serializar_item(it) for it in itens_pendentes]

    return Response({
        "status": "ativa",
        "sessao_id": sessao.id,
        "pedido": {
            "numero": sessao.pedido.numero_pedido,
            "cliente": sessao.pedido.cliente,
            "total_pecas": total,
            "pecas_bipadas": sessao.pecas_bipadas,
        },
        "item_atual": _serializar_item(sessao.item_atual) if sessao.item_atual else None,
        "itens_pendentes": itens_pendentes_serializados,
        "erros": sessao.erros,
        "kpis": _calcular_kpis(sessao)
    })


# ═══════════════════════════════════════════════════════════════
#  EXCEÇÕES DE PICKING — LISTAGEM, AUTORIZAÇÃO E NEGAÇÃO
# ═══════════════════════════════════════════════════════════════

@api_view(['GET'])
def api_listar_excecoes(request):
    """Lista exceções de picking pendentes para supervisor/ADM."""
    if not _check_api_permission(request, ['ADM', 'SUPERVISOR']):
        return Response({"status": "erro", "mensagem": "Acesso negado."}, status=403)

    perfil = request.session.get('perfil_usuario')
    usuario_id = request.session.get('usuario_id')

    qs = ExcecaoPicking.objects.select_related(
        'sessao__colaborador', 'item', 'supervisor_resp'
    ).order_by('-data_criacao')

    # Supervisor só vê exceções dos operadores da sua equipe
    if perfil == 'SUPERVISOR':
        qs = qs.filter(sessao__colaborador__supervisor_resp_id=usuario_id)

    def _tipo_excecao(exc):
        if exc.item.status == 'PULADO':
            return 'PULAR_SKU'
        elif exc.item.status == 'DANIFICADO':
            return 'PECA_DANIFICADA'
        return 'OUTRO'

    pendentes = qs.filter(status='PENDENTE')
    historico = qs.filter(status__in=['AUTORIZADO', 'NEGADO'])[:50]

    def _serializar_exc(exc):
        return {
            "id": exc.id,
            "operador": exc.sessao.colaborador.nome if exc.sessao.colaborador else "Desconhecido",
            "cracha_operador": exc.sessao.colaborador.cracha if exc.sessao.colaborador else "",
            "tipo": _tipo_excecao(exc),
            "motivo": exc.motivo_operador,
            "referencia": exc.item.referencia,
            "endereco": exc.item.endereco,
            "status": exc.status,
            "justificativa_supervisor": exc.justificativa_supervisor,
            "supervisor": exc.supervisor_resp.nome if exc.supervisor_resp else None,
            "data_criacao": exc.data_criacao.strftime('%d/%m/%Y %H:%M'),
            "data_resolucao": exc.data_resolucao.strftime('%d/%m/%Y %H:%M') if exc.data_resolucao else None,
        }

    return Response({
        "pendentes": [_serializar_exc(e) for e in pendentes],
        "historico": [_serializar_exc(e) for e in historico],
        "total_pendentes": pendentes.count(),
    })


@csrf_exempt
@api_view(['POST'])
def api_autorizar_excecao(request, pk):
    """Autoriza uma exceção de picking após validação do cachá do supervisor."""
    if not _check_api_permission(request, ['ADM', 'SUPERVISOR']):
        return Response({"status": "erro", "mensagem": "Acesso negado."}, status=403)

    try:
        excecao = ExcecaoPicking.objects.select_related('sessao', 'item').get(pk=pk)
    except ExcecaoPicking.DoesNotExist:
        return Response({"status": "erro", "mensagem": "Exceção não encontrada."}, status=404)

    if excecao.status != 'PENDENTE':
        return Response({"status": "erro", "mensagem": "Esta exceção já foi tratada."}, status=400)

    # Valida o cachá informado como Master Code
    cracha_informado = request.data.get('cracha', '').strip()
    if not cracha_informado:
        return Response({"status": "erro", "mensagem": "Informe o cachá para autorizar."}, status=400)

    try:
        supervisor = Usuario.objects.get(
            cracha=cracha_informado,
            perfil__in=['SUPERVISOR', 'ADM'],
            ativo=True
        )
    except Usuario.DoesNotExist:
        return Response({"status": "erro", "mensagem": "Cachá inválido ou sem permissão."}, status=403)

    excecao.status = 'AUTORIZADO'
    excecao.supervisor_resp = supervisor
    excecao.data_resolucao = timezone.now()
    excecao.justificativa_supervisor = request.data.get('justificativa', 'Autorizado via Master Code')
    excecao.save()

    return Response({
        "status": "sucesso",
        "mensagem": f"Exceção autorizada por {supervisor.nome}.",
        "autorizado_por": supervisor.nome,
    })


@csrf_exempt
@api_view(['POST'])
def api_negar_excecao(request, pk):
    """Nega uma exceção de picking com motivo do supervisor."""
    if not _check_api_permission(request, ['ADM', 'SUPERVISOR']):
        return Response({"status": "erro", "mensagem": "Acesso negado."}, status=403)

    try:
        excecao = ExcecaoPicking.objects.select_related('sessao', 'item').get(pk=pk)
    except ExcecaoPicking.DoesNotExist:
        return Response({"status": "erro", "mensagem": "Exceção não encontrada."}, status=404)

    if excecao.status != 'PENDENTE':
        return Response({"status": "erro", "mensagem": "Esta exceção já foi tratada."}, status=400)

    cracha_informado = request.data.get('cracha', '').strip()
    motivo_negacao = request.data.get('motivo', '').strip()

    if not motivo_negacao:
        return Response({"status": "erro", "mensagem": "Informe o motivo da negação."}, status=400)

    supervisor = None
    if cracha_informado:
        supervisor = Usuario.objects.filter(
            cracha=cracha_informado,
            perfil__in=['SUPERVISOR', 'ADM'],
            ativo=True
        ).first()

    if not supervisor:
        usuario_id = request.session.get('usuario_id')
        if usuario_id:
            supervisor = Usuario.objects.filter(id=usuario_id).first()

    excecao.status = 'NEGADO'
    excecao.supervisor_resp = supervisor
    excecao.data_resolucao = timezone.now()
    excecao.justificativa_supervisor = motivo_negacao
    excecao.save()

    return Response({
        "status": "sucesso",
        "mensagem": f"Exceção negada. Motivo: {motivo_negacao}.",
    })


# ═══════════════════════════════════════════════════════════════
#  DASHBOARD — KPIs EM TEMPO REAL
# ═══════════════════════════════════════════════════════════════

@api_view(['GET'])
def api_kpis_tempo_real(request):
    from django.db.models import Sum, Count, Avg
    from datetime import date, datetime, timedelta

    from django.utils.timezone import make_aware
    
    # ── Resolver período ─────────────────────────────────────
    periodo = request.GET.get('periodo', 'hoje')
    hoje = timezone.localtime(timezone.now()).date()

    if periodo == 'ontem':
        data_ini = hoje - timedelta(days=1)
        data_fim = hoje - timedelta(days=1)
    elif periodo == '7dias':
        data_ini = hoje - timedelta(days=6)
        data_fim = hoje
    elif periodo == '30dias':
        data_ini = hoje - timedelta(days=29)
        data_fim = hoje
    elif periodo == 'personalizado':
        try:
            data_ini = date.fromisoformat(request.GET.get('inicio', str(hoje)))
            data_fim = date.fromisoformat(request.GET.get('fim', str(hoje)))
        except ValueError:
            data_ini = data_fim = hoje
    else:  # hoje (padrão)
        data_ini = data_fim = hoje

    # ── Query base otimizada com faixas de tempo ───────────────
    dt_ini = make_aware(datetime.combine(data_ini, datetime.min.time()))
    dt_fim = make_aware(datetime.combine(data_fim, datetime.max.time()))
    
    sessoes = SessaoPicking.objects.filter(inicio__gte=dt_ini, inicio__lte=dt_fim)
    sessoes_ativas = sessoes.filter(ativa=True)
    # PARCIAL e FINALIZADO contam como sessões encerradas no dashboard
    sessoes_finalizadas = sessoes.filter(ativa=False)

    caixas_finalizadas = sessoes_finalizadas.count()
    total_pecas = sessoes.aggregate(s=Sum('pecas_bipadas'))['s'] or 0
    total_erros = sessoes.aggregate(s=Sum('erros'))['s'] or 0

    # PPH global e Tempo Total
    pph_global = 0
    total_horas = 0
    tempo_total_str = "0:00"
    if sessoes.exists():
        total_segundos = sum(
            max(((s.fim or timezone.now()) - s.inicio).total_seconds(), 1)
            for s in sessoes
        )
        total_horas = total_segundos / 3600
        pph_global = int(total_pecas / max(total_horas, 0.001))
        
        h = int(total_segundos // 3600)
        m = int((total_segundos % 3600) // 60)
        tempo_total_str = f"{h}:{m:02d}"

    taxa_acerto = max(0, round(100 - (total_erros * 1.5), 1))

    # Lead time médio
    tempo_medio_min = "—"
    fin_com_fim = sessoes_finalizadas.filter(fim__isnull=False)
    if fin_com_fim.exists():
        duracoes = [(s.fim - s.inicio).total_seconds() / 60 for s in fin_com_fim]
        if duracoes:
            media = sum(duracoes) / len(duracoes)
            tempo_medio_min = f"{int(media)}:{int((media % 1) * 60):02d}"

    # Streak (maior sequência sem erros entre sessões finalizadas)
    streak = 0
    atual_streak = 0
    for s in sessoes_finalizadas.order_by('inicio'):
        if s.erros == 0:
            atual_streak += 1
            streak = max(streak, atual_streak)
        else:
            atual_streak = 0

    # Operadores ativos agora
    operadores_ativos = []
    for sessao in sessoes_ativas.select_related('colaborador'):
        if sessao.colaborador:
            kpis = _calcular_kpis(sessao)
            operadores_ativos.append({
                "nome": sessao.colaborador.nome,
                "cracha": sessao.colaborador.cracha,
                "pph": kpis['pph'],
                "erros": sessao.erros,
                "pecas": sessao.pecas_bipadas,
                "pedido": sessao.pedido.numero_pedido if sessao.pedido else "—",
                "tempo": kpis['tempo'],
            })

    # Ranking e KPIs Diários por Operador (Mesmo inativos)
    ranking = []
    colaboradores_ids = [cid for cid in sessoes.values_list('colaborador_id', flat=True).distinct() if cid]
    usuarios_cache = {u.id: u for u in Usuario.objects.filter(id__in=colaboradores_ids)}
    
    for cid in colaboradores_ids:
        sess_colab = sessoes.filter(colaborador_id=cid)
        total_p = sess_colab.aggregate(s=Sum('pecas_bipadas'))['s'] or 0
        total_c = sess_colab.filter(ativa=False).count()
        total_h = sum(
            max((s.fim or timezone.now()) - s.inicio, timedelta(seconds=1)).total_seconds() / 3600
            for s in sess_colab
        )
        pph_colab = int(total_p / max(total_h, 0.001))
        
        # Tempo médio
        tempo_str = "—"
        sess_fin = sess_colab.filter(ativa=False, fim__isnull=False)
        if sess_fin.exists():
            dur = [(s.fim - s.inicio).total_seconds() / 60 for s in sess_fin]
            media = sum(dur) / len(dur)
            tempo_str = f"{int(media)}:{int((media % 1) * 60):02d}"
        
        u = usuarios_cache.get(cid)
        if u:
            ranking.append({
                "nome": u.nome, 
                "cracha": u.cracha, 
                "pph": pph_colab, 
                "pecas": total_p,
                "caixas": total_c,
                "tempo": tempo_str
            })
            
    ranking.sort(key=lambda x: x['pph'], reverse=True)

    # PPH por turno (com base nos horários reais de início das sessões)
    sessoes_manha = []
    sessoes_tarde = []
    sessoes_noite = []
    for s in sessoes:
        dt_local = timezone.localtime(s.inicio)
        hour = dt_local.hour
        if 6 <= hour < 14:
            sessoes_manha.append(s)
        elif 14 <= hour < 22:
            sessoes_tarde.append(s)
        else:
            sessoes_noite.append(s)

    def _calc_pph_sessoes(lista_sessoes):
        if not lista_sessoes:
            return 0
        total_p = sum(s.pecas_bipadas for s in lista_sessoes)
        total_h = sum(
            max(((s.fim or timezone.now()) - s.inicio).total_seconds(), 1) / 3600
            for s in lista_sessoes
        )
        return int(total_p / max(total_h, 0.001))

    pph_turnos = {
        "manha": _calc_pph_sessoes(sessoes_manha),
        "tarde": _calc_pph_sessoes(sessoes_tarde),
        "noite": _calc_pph_sessoes(sessoes_noite),
        "atual": pph_global
    }

    return Response({
        "pph_global": pph_global,
        "caixas_finalizadas": caixas_finalizadas,
        "total_pecas_bipadas": total_pecas,
        "total_erros": total_erros,
        "taxa_acerto": taxa_acerto,
        "tempo_medio": tempo_medio_min,
        "tempo_total": tempo_total_str,
        "streak": streak,
        "operadores_ativos": operadores_ativos,
        "ranking": ranking[:10],
        "pph_turnos": pph_turnos,
        "operadores_count": sessoes_ativas.values('colaborador').distinct().count(),
    })


# ═══════════════════════════════════════════════════════════════
#  WEBHOOKS — CRUD
# ═══════════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
def api_webhooks(request):
    if not _check_api_permission(request, ['ADM']):
        return Response({"status": "erro", "mensagem": "Acesso negado. Apenas ADM."}, status=403)

    if request.method == 'GET':
        whs = WebhookConfig.objects.all().order_by('-criado_em')
        data = [{
            "id": w.id,
            "nome": w.nome,
            "url_destino": w.url_destino,
            "evento_gatilho": w.evento_gatilho,
            "threshold": w.threshold,
            "ativo": w.ativo,
            "ultimo_disparo": w.ultimo_disparo.strftime('%d/%m/%Y %H:%M') if w.ultimo_disparo else None,
        } for w in whs]
        return Response({"webhooks": data, "total": len(data)})

    # POST — criar
    nome = request.data.get('nome', '').strip()
    url = request.data.get('url_destino', '').strip()
    evento = request.data.get('evento_gatilho', '')
    threshold = int(request.data.get('threshold', 3))

    if not nome or not url or not evento:
        return Response({"status": "erro", "mensagem": "Preencha nome, URL e evento."}, status=400)

    wh = WebhookConfig.objects.create(nome=nome, url_destino=url, evento_gatilho=evento, threshold=threshold)
    return Response({"status": "sucesso", "id": wh.id, "mensagem": f"Webhook '{nome}' criado com sucesso."})


@api_view(['PUT', 'PATCH', 'DELETE'])
def api_webhook_detalhe(request, pk):
    if not _check_api_permission(request, ['ADM']):
        return Response({"status": "erro", "mensagem": "Acesso negado. Apenas ADM."}, status=403)

    try:
        wh = WebhookConfig.objects.get(pk=pk)
    except WebhookConfig.DoesNotExist:
        return Response({"status": "erro", "mensagem": "Webhook não encontrado."}, status=404)

    if request.method == 'DELETE':
        wh.delete()
        return Response({"status": "sucesso", "mensagem": "Webhook removido."})

    # PUT/PATCH — atualizar
    wh.nome = request.data.get('nome', wh.nome)
    wh.url_destino = request.data.get('url_destino', wh.url_destino)
    wh.evento_gatilho = request.data.get('evento_gatilho', wh.evento_gatilho)
    wh.threshold = int(request.data.get('threshold', wh.threshold))
    wh.ativo = request.data.get('ativo', wh.ativo)
    wh.save()
    return Response({"status": "sucesso", "mensagem": "Webhook atualizado."})


@csrf_exempt
@api_view(['POST'])
def api_webhook_testar(request, pk):
    """Dispara um teste imediato do webhook."""
    if not _check_api_permission(request, ['ADM']):
        return Response({"status": "erro", "mensagem": "Acesso negado. Apenas ADM."}, status=403)

    try:
        wh = WebhookConfig.objects.get(pk=pk)
    except WebhookConfig.DoesNotExist:
        return Response({"status": "erro", "mensagem": "Webhook não encontrado."}, status=404)

    payload = {
        "event_type": wh.evento_gatilho,
        "test": True,
        "message": f"Teste do webhook '{wh.nome}' — MES Picking Kyly",
        "timestamp": timezone.now().isoformat(),
    }
    try:
        r = req_lib.post(wh.url_destino, json=payload, timeout=5)
        wh.ultimo_disparo = timezone.now()
        wh.save(update_fields=['ultimo_disparo'])
        return Response({"status": "sucesso", "http_status": r.status_code, "mensagem": f"Webhook disparado. Resposta: {r.status_code}"})
    except Exception as e:
        return Response({"status": "erro", "mensagem": f"Falha ao disparar: {str(e)}"}, status=500)


# ═══════════════════════════════════════════════════════════════
#  KPI DEFINITIONS — CRUD COMPLETO (com permissão, emoji-safe, favorito)
# ═══════════════════════════════════════════════════════════════

import re as _re

@csrf_exempt
@api_view(['GET', 'POST'])
def api_kpis_config(request):
    """Lista todos os KPIs (GET) ou cria um novo (POST)."""
    if not _check_api_permission(request, ['ADM']):
        return Response({"status": "erro", "mensagem": "Acesso negado. Apenas ADM."}, status=403)

    if request.method == 'GET':
        kpis = KPIDefinicao.objects.all().order_by('-favorito', 'nome')
        data = [{
            'id': k.id, 'nome': k.nome, 'icone': k.icone,
            'formula': k.formula, 'meta': k.meta,
            'tom_cor': k.tom_cor, 'ativo': k.ativo,
            'favorito': k.favorito,
            'supervisor_resp': k.supervisor_resp_id,
            'criado_em': k.criado_em.strftime('%d/%m/%Y %H:%M') if k.criado_em else '',
        } for k in kpis]
        return Response({'status': 'sucesso', 'kpis': data, 'total': len(data)})

    # POST — criar
    nome = request.data.get('nome', '').strip()
    if not nome:
        return Response({'status': 'erro', 'mensagem': 'Nome é obrigatório.'}, status=400)

    icone_raw = request.data.get('icone', '📊')
    # Sanitiza emojis de 4 bytes (incompatíveis com MySQL utf8)
    icone_seguro = _re.sub(r'[^\x00-\xFFFF]', '', icone_raw).strip() or 'K'

    supervisor_id = request.data.get('supervisor_resp')
    supervisor = None
    if supervisor_id:
        try:
            supervisor = Usuario.objects.get(id=supervisor_id)
        except Usuario.DoesNotExist:
            pass

    try:
        kpi = KPIDefinicao.objects.create(
            nome=nome,
            icone=icone_seguro,
            formula=request.data.get('formula', ''),
            meta=request.data.get('meta', ''),
            tom_cor=request.data.get('tom_cor', 'GREEN'),
            supervisor_resp=supervisor,
        )
        return Response({'status': 'sucesso', 'id': kpi.id, 'mensagem': f"KPI '{nome}' criado com sucesso."}, status=201)
    except Exception as e:
        err = str(e)
        if 'Incorrect string value' in err:
            return Response({'status': 'erro', 'mensagem': 'Banco não suporta esse ícone. Use texto simples.'}, status=400)
        return Response({'status': 'erro', 'mensagem': f'Erro interno: {err}'}, status=500)


@csrf_exempt
@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def api_kpi_detalhe(request, pk):
    """Detalhe, edição ou exclusão de um KPI."""
    if not _check_api_permission(request, ['ADM']):
        return Response({'status': 'erro', 'mensagem': 'Acesso negado. Apenas ADM.'}, status=403)

    try:
        kpi = KPIDefinicao.objects.get(pk=pk)
    except KPIDefinicao.DoesNotExist:
        return Response({'status': 'erro', 'mensagem': 'KPI não encontrado.'}, status=404)

    if request.method == 'GET':
        return Response({
            'id': kpi.id, 'nome': kpi.nome, 'icone': kpi.icone,
            'formula': kpi.formula, 'meta': kpi.meta,
            'tom_cor': kpi.tom_cor, 'favorito': kpi.favorito,
            'ativo': kpi.ativo, 'supervisor_resp': kpi.supervisor_resp_id,
        })

    if request.method == 'DELETE':
        kpi.delete()
        return Response({'status': 'sucesso', 'mensagem': 'KPI removido.'})

    # PUT/PATCH — atualizar
    kpi.nome    = request.data.get('nome', kpi.nome).strip()
    kpi.icone   = request.data.get('icone', kpi.icone)
    kpi.formula = request.data.get('formula', kpi.formula)
    kpi.meta    = request.data.get('meta', kpi.meta)
    kpi.tom_cor = request.data.get('tom_cor', kpi.tom_cor)
    kpi.ativo   = request.data.get('ativo', kpi.ativo)

    sup_id = request.data.get('supervisor_resp')
    if sup_id is not None:
        kpi.supervisor_resp = Usuario.objects.filter(id=sup_id).first() if sup_id else None

    kpi.save()
    return Response({'status': 'sucesso', 'mensagem': 'KPI atualizado.'})


@api_view(['POST'])
def api_kpi_favorito(request, pk):
    """Alterna o favorito de um KPI."""
    if not _check_api_permission(request, ['ADM']):
        return Response({'status': 'erro', 'mensagem': 'Acesso negado. Apenas ADM.'}, status=403)
    try:
        kpi = KPIDefinicao.objects.get(pk=pk)
    except KPIDefinicao.DoesNotExist:
        return Response({'status': 'erro', 'mensagem': 'KPI não encontrado.'}, status=404)
    kpi.favorito = not kpi.favorito
    kpi.save()
    return Response({'status': 'sucesso', 'favorito': kpi.favorito})


# ═══════════════════════════════════════════════════════════════
#  META GLOBAL — singleton com metas de produção
# ═══════════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
def api_meta_global(request):
    """Retorna (GET) ou salva (POST) as metas globais de produção."""
    # GET is permitido para ADM e SUPERVISOR para exibir no dashboard
    if request.method == 'POST' and not _check_api_permission(request, ['ADM']):
        return Response({'status': 'erro', 'mensagem': 'Acesso negado. Apenas ADM pode alterar metas.'}, status=403)

    meta, _ = MetaGlobal.objects.get_or_create(id=1)

    if request.method == 'GET':
        return Response({
            'status': 'sucesso',
            'meta_pph':      meta.meta_pph,
            'meta_caixas':   meta.meta_caixas,
            'meta_acuracia': meta.meta_acuracia,
            'meta_streak':   meta.meta_streak,
        })

    # POST — salvar
    try:
        meta.meta_pph      = int(request.data.get('meta_pph',      meta.meta_pph))
        meta.meta_caixas   = int(request.data.get('meta_caixas',   meta.meta_caixas))
        meta.meta_acuracia = int(request.data.get('meta_acuracia', meta.meta_acuracia))
        meta.meta_streak   = int(request.data.get('meta_streak',   meta.meta_streak))
        meta.save()
    except (ValueError, TypeError):
        return Response({'status': 'erro', 'mensagem': 'Valores inválidos.'}, status=400)

    return Response({'status': 'sucesso', 'mensagem': 'Metas globais atualizadas com sucesso.'})


# ═══════════════════════════════════════════════════════════════
#  AGING STOCK — RESOLUÇÃO
# ═══════════════════════════════════════════════════════════════

@csrf_exempt
@api_view(['POST'])
def api_resolver_aging(request):
    if not _check_api_permission(request, ['ADM', 'SUPERVISOR']):
        return Response({"status": "erro", "mensagem": "Acesso negado. Apenas ADM ou SUPERVISOR."}, status=403)

    sku = request.data.get('sku', '')
    acao = request.data.get('acao', '')
    motivo = request.data.get('motivo', '')
    sup_id = request.data.get('supervisor_id')
    autor_id = request.session.get('usuario_id')

    if not sku or not acao or not motivo:
        return Response({"status": "erro", "mensagem": "SKU, Ação e Motivo são obrigatórios."}, status=400)

    sup_obj = None
    if sup_id:
        try:
            sup_obj = Usuario.objects.get(id=sup_id)
        except Usuario.DoesNotExist:
            pass

    autor_obj = None
    if autor_id:
        try:
            autor_obj = Usuario.objects.get(id=autor_id)
        except Usuario.DoesNotExist:
            pass

    LogAgingStock.objects.create(
        sku=sku,
        endereco='',
        acao=acao.upper(),
        motivo=motivo,
        supervisor_resp=sup_obj,
        autor=autor_obj
    )
    return Response({"status": "sucesso", "mensagem": "Resolução registrada."})


# ═══════════════════════════════════════════════════════════════
#  AGING STOCK — HISTÓRICO
# ═══════════════════════════════════════════════════════════════

@api_view(['GET'])
def api_historico_aging(request):
    """Retorna histórico de resoluções do aging stock (ADM e SUPERVISOR)."""
    if not _check_api_permission(request, ['ADM', 'SUPERVISOR']):
        return Response({"status": "erro", "mensagem": "Acesso negado."}, status=403)

    perfil = request.session.get('perfil_usuario')
    usuario_id = request.session.get('usuario_id')
    
    qs = LogAgingStock.objects.all().select_related('autor', 'supervisor_resp')
    
    # Supervisor só vê os atribuídos a ele
    if perfil == 'SUPERVISOR':
        qs = qs.filter(supervisor_resp_id=usuario_id)
    
    data = [{
        "id": log.id,
        "sku": log.sku,
        "acao": log.acao,
        "motivo": log.motivo,
        "autor": log.autor.nome if log.autor else "Sistema",
        "supervisor": log.supervisor_resp.nome if log.supervisor_resp else None,
        "data_hora": log.data_hora.strftime('%d/%m/%Y %H:%M'),
    } for log in qs[:100]]
    
    return Response({"historico": data, "total": len(data)})


# ═══════════════════════════════════════════════════════════════
#  FUNCIONÁRIOS — EQUIPE DO SUPERVISOR
# ═══════════════════════════════════════════════════════════════

@api_view(['GET'])
def api_equipe_supervisor(request):
    """Supervisor vê apenas os colaboradores vinculados a ele."""
    if not _check_api_permission(request, ['ADM', 'SUPERVISOR']):
        return Response({"status": "erro", "mensagem": "Acesso negado."}, status=403)
    
    perfil = request.session.get('perfil_usuario')
    usuario_id = request.session.get('usuario_id')
    
    if perfil == 'SUPERVISOR':
        equipe = Usuario.objects.filter(
            supervisor_resp_id=usuario_id,
            perfil='COLABORADOR',
            ativo=True
        ).order_by('nome')
    else:
        # ADM vê todos os colaboradores com seu supervisor vinculado
        equipe = Usuario.objects.filter(perfil='COLABORADOR', ativo=True).order_by('nome')
    
    agora = timezone.now()
    limite = agora - timedelta(minutes=5)

    from django.db.models import Sum
    from datetime import datetime
    from django.utils.timezone import make_aware

    hoje = timezone.localtime(timezone.now()).date()
    dt_ini = make_aware(datetime.combine(hoje, datetime.min.time()))
    dt_fim = make_aware(datetime.combine(hoje, datetime.max.time()))

    data = []
    for u in equipe:
        # CORREÇÃO: campo correto é 'usuario', não 'usuario_vinculado'
        hb = HeartbeatLog.objects.filter(usuario=u).order_by('-ultimo_sinal').first()
        status_disp = 'OFFLINE'
        if hb:
            if hb.ultimo_sinal >= limite:
                status_disp = 'ONLINE'
            else:
                status_disp = 'TIMEOUT'
                
        # KPIs do Operador
        sessoes = SessaoPicking.objects.filter(colaborador=u, inicio__gte=dt_ini, inicio__lte=dt_fim)
        total_p = sessoes.aggregate(s=Sum('pecas_bipadas'))['s'] or 0
        total_h = sum(
            max((s.fim or timezone.now()) - s.inicio, timedelta(seconds=1)).total_seconds() / 3600
            for s in sessoes
        )
        pph = int(total_p / max(total_h, 0.001))

        sessao_ativa = sessoes.filter(ativa=True).select_related('pedido').first()
        caixa_atual = sessao_ativa.pedido.numero_pedido if sessao_ativa and sessao_ativa.pedido else '-'

        data.append({
            "id": u.id,
            "nome": u.nome,
            "cracha": u.cracha,
            "setor": u.setor,
            "turno": u.turno,
            "ativo": u.ativo,
            "login_status": u.login_status,
            "dispositivo_status": status_disp,
            "supervisor": u.supervisor_resp.nome if u.supervisor_resp else None,
            "supervisor_id": u.supervisor_resp_id,
            "pph": pph,
            "caixa": caixa_atual
        })
    
    ativos_logados = sum(1 for u in data if u['login_status'])
    
    return Response({
        "equipe": data,
        "total": len(data),
        "ativos_logados": ativos_logados,
        "status": "sucesso",
    })


# ═══════════════════════════════════════════════════════════════
#  FUNCIONÁRIOS — LOGS INDIVIDUAIS
# ═══════════════════════════════════════════════════════════════

@api_view(['GET'])
def api_funcionario_logs(request, pk):
    """Retorna o histórico completo de auditoria de um funcionário (ADM e SUPERVISOR da equipe)."""
    if not _check_api_permission(request, ['ADM', 'SUPERVISOR']):
        return Response({"status": "erro", "mensagem": "Acesso negado."}, status=403)
    
    try:
        u = Usuario.objects.get(pk=pk)
    except Usuario.DoesNotExist:
        return Response({"status": "erro", "mensagem": "Funcionário não encontrado."}, status=404)
    
    # Supervisor só pode ver logs da sua equipe
    perfil = request.session.get('perfil_usuario')
    usuario_id = request.session.get('usuario_id')
    if perfil == 'SUPERVISOR' and str(u.supervisor_resp_id) != str(usuario_id):
        return Response({"status": "erro", "mensagem": "Acesso negado."}, status=403)
    
    from authentication.models import LogAuditoriaUsuario
    logs = LogAuditoriaUsuario.objects.filter(usuario_alvo=u).select_related('autor')
    
    data = [{
        "acao": log.acao,
        "autor": log.autor.nome if log.autor else "Sistema",
        "detalhes": log.detalhes,
        "data_hora": log.data_hora.strftime('%d/%m/%Y %H:%M'),
    } for log in logs]
    
    return Response({
        "funcionario": {"id": u.id, "nome": u.nome, "cracha": u.cracha},
        "logs": data,
        "total": len(data)
    })


# ═══════════════════════════════════════════════════════════════
#  FUNCIONÁRIOS — CRUD
# ═══════════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
def api_funcionarios(request):
    if not _check_api_permission(request, ['ADM']):
        return Response({"status": "erro", "mensagem": "Acesso negado. Apenas ADM."}, status=403)

    if request.method == 'GET':
        q = request.GET.get('q', '')
        qs = Usuario.objects.all().order_by('nome')
        if q:
            qs = qs.filter(nome__icontains=q) | qs.filter(cracha__icontains=q)
        data = [{
            "id": u.id, "nome": u.nome, "cracha": u.cracha,
            "perfil": u.perfil, "setor": u.setor, "turno": u.turno,
            "ativo": u.ativo, "data_admissao": str(u.data_admissao) if u.data_admissao else None,
            "login_status": u.login_status,
        } for u in qs]
        return Response({"funcionarios": data, "total": len(data)})

    # POST — criar
    nome = request.data.get('nome', '').strip()
    cracha = request.data.get('cracha', '').strip()
    perfil = request.data.get('perfil', 'COLABORADOR')

    if not nome or not cracha:
        return Response({"status": "erro", "mensagem": "Nome e crachá são obrigatórios."}, status=400)

    if Usuario.objects.filter(cracha=cracha).exists():
        return Response({"status": "erro", "mensagem": f"Crachá '{cracha}' já cadastrado."}, status=400)

    sup_id = request.data.get('supervisor_resp')
    try:
        sup_obj = Usuario.objects.get(id=sup_id) if sup_id else None
    except:
        sup_obj = None

    u = Usuario.objects.create(
        nome=nome, cracha=cracha, perfil=perfil,
        setor=request.data.get('setor', ''),
        turno=request.data.get('turno', ''),
        data_admissao=request.data.get('data_admissao') or None,
        supervisor_resp=sup_obj,
        ativo=request.data.get('ativo', True),
    )

    # Audit log
    from authentication.models import LogAuditoriaUsuario
    autor_id = request.session.get('usuario_id')
    autor_obj = Usuario.objects.filter(id=autor_id).first()
    LogAuditoriaUsuario.objects.create(
        usuario_alvo=u,
        acao='CRIADO',
        autor=autor_obj,
        detalhes=f'Perfil: {perfil}, Setor: {u.setor}, Turno: {u.turno}'
    )

    return Response({"status": "sucesso", "id": u.id, "mensagem": f"Funcionário '{nome}' cadastrado."})


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def api_funcionario_detalhe(request, pk):
    if not _check_api_permission(request, ['ADM']):
        return Response({"status": "erro", "mensagem": "Acesso negado. Apenas ADM."}, status=403)

    try:
        u = Usuario.objects.get(pk=pk)
    except Usuario.DoesNotExist:
        return Response({"status": "erro", "mensagem": "Funcionário não encontrado."}, status=404)

    if request.method == 'GET':
        return Response({
            "id": u.id, "nome": u.nome, "cracha": u.cracha,
            "perfil": u.perfil, "setor": u.setor, "turno": u.turno,
            "ativo": u.ativo, "data_admissao": str(u.data_admissao) if u.data_admissao else None,
        })

    if request.method == 'DELETE':
        from authentication.models import LogAuditoriaUsuario
        autor_id = request.session.get('usuario_id')
        autor_obj = Usuario.objects.filter(id=autor_id).first()
        nome_salvo = u.nome
        # Marcar como inativo ao invés de deletar definitivamente
        u.ativo = False
        u.save()
        LogAuditoriaUsuario.objects.create(
            usuario_alvo=u,
            acao='EXCLUIDO',
            autor=autor_obj,
            detalhes=f'Funcionário {nome_salvo} marcado como inativo'
        )
        return Response({"status": "sucesso", "mensagem": f"Funcionário '{nome_salvo}' desativado."})

    u.nome = request.data.get('nome', u.nome)
    u.cracha = request.data.get('cracha', u.cracha)
    u.perfil = request.data.get('perfil', u.perfil)
    u.setor = request.data.get('setor', u.setor)
    u.turno = request.data.get('turno', u.turno)
    u.ativo = request.data.get('ativo', u.ativo)
    u.data_admissao = request.data.get('data_admissao') or u.data_admissao
    
    sup_id = request.data.get('supervisor_resp')
    if sup_id is not None:
        try:
            u.supervisor_resp = Usuario.objects.get(id=sup_id) if sup_id else None
        except Usuario.DoesNotExist:
            pass

    alteracoes = f'Nome: {u.nome}, Perfil: {u.perfil}, Ativo: {u.ativo}'
    u.save()

    # Audit log
    from authentication.models import LogAuditoriaUsuario
    autor_id = request.session.get('usuario_id')
    autor_obj = Usuario.objects.filter(id=autor_id).first()
    LogAuditoriaUsuario.objects.create(
        usuario_alvo=u,
        acao='MODIFICADO',
        autor=autor_obj,
        detalhes=alteracoes
    )

    return Response({"status": "sucesso", "mensagem": "Funcionário atualizado."})


# ═══════════════════════════════════════════════════════════════
#  HEARTBEAT — MONITORAMENTO DE COLETORES
# ═══════════════════════════════════════════════════════════════

@csrf_exempt
@api_view(['POST'])
def api_heartbeat(request):
    """Recebe sinal de vida do coletor/dashboard."""
    dispositivo_id = request.data.get('dispositivo_id') or request.session.get('dispositivo_id') or request.session.session_key or 'dispositivo_desconhecido'
    usuario_id = request.session.get('usuario_id') or request.data.get('usuario_id')
    ip = request.META.get('REMOTE_ADDR', '')

    usuario = None
    if usuario_id:
        try:
            usuario = Usuario.objects.get(id=usuario_id)
        except Usuario.DoesNotExist:
            pass

    heartbeat, created = HeartbeatLog.objects.get_or_create(
        dispositivo_id=dispositivo_id,
        defaults={'usuario': usuario, 'ip_address': ip, 'status': 'ONLINE'}
    )
    if not created:
        heartbeat.status = 'ONLINE'
        heartbeat.ip_address = ip
        if usuario:
            heartbeat.usuario = usuario
        heartbeat.save()  # auto_now=True atualiza ultimo_sinal

    return Response({"status": "ok", "dispositivo": dispositivo_id})


@api_view(['GET'])
def api_heartbeat_status(request):
    """Retorna o status de todos os coletores."""
    if not _check_api_permission(request, ['ADM', 'SUPERVISOR']):
        return Response({"status": "erro", "mensagem": "Acesso negado."}, status=403)

    agora = timezone.now()
    timeout_limite = agora - timedelta(minutes=1)
    offline_limite = agora - timedelta(minutes=5)

    coletores = HeartbeatLog.objects.all().select_related('usuario').order_by('-ultimo_sinal')
    data = []
    for c in coletores:
        # Atualiza status baseado no tempo de inatividade
        if c.ultimo_sinal < offline_limite:
            if c.status != 'OFFLINE':
                c.status = 'OFFLINE'
                c.save(update_fields=['status'])

                # Dispara webhooks de DEVICE_OFFLINE
                for wh in WebhookConfig.objects.filter(evento_gatilho='DEVICE_OFFLINE', ativo=True):
                    _disparar_webhook_async(wh, {
                        "event": "DEVICE_OFFLINE",
                        "dispositivo": c.dispositivo_id,
                        "usuario": c.usuario.nome if c.usuario else "Desconhecido",
                        "ultimo_sinal": c.ultimo_sinal.isoformat(),
                    })
        elif c.ultimo_sinal < timeout_limite:
            if c.status != 'TIMEOUT':
                c.status = 'TIMEOUT'
                c.save(update_fields=['status'])

        from django.utils.timezone import localtime
        local_sinal = localtime(c.ultimo_sinal) if c.ultimo_sinal else agora

        minutos_atras = int((agora - c.ultimo_sinal).total_seconds() / 60)
        data.append({
            "id": c.id,
            "dispositivo_id": c.dispositivo_id,
            "status": c.status,
            "usuario": c.usuario.nome if c.usuario else "—",
            "usuario_id": c.usuario.id if c.usuario else None,
            "usuario_perfil": c.usuario.perfil if c.usuario else None,
            "ip": c.ip_address,
            "ultimo_sinal": local_sinal.strftime('%H:%M:%S'),
            "ultimo_sinal_data": local_sinal.strftime('%d/%m/%Y'),
            "minutos_atras": minutos_atras,
        })

    online = sum(1 for d in data if d['status'] == 'ONLINE')
    timeout = sum(1 for d in data if d['status'] == 'TIMEOUT')
    offline = sum(1 for d in data if d['status'] == 'OFFLINE')

    return Response({"coletores": data, "online": online, "timeout": timeout, "offline": offline, "total": len(data)})


@csrf_exempt
@api_view(['POST', 'DELETE'])
def api_heartbeat_manage(request):
    """
    POST  → Adiciona/registra manualmente um dispositivo.
    DELETE → Remove um dispositivo do monitoramento.
    """
    if not _check_api_permission(request, ['ADM']):
        return Response({"status": "erro", "mensagem": "Acesso negado. Apenas ADM."}, status=403)

    if request.method == 'DELETE':
        device_id = request.data.get('dispositivo_id')
        if not device_id:
            return Response({"status": "erro", "mensagem": "dispositivo_id é obrigatório."}, status=400)
        deleted, _ = HeartbeatLog.objects.filter(dispositivo_id=device_id).delete()
        if deleted:
            return Response({"status": "sucesso", "mensagem": f"Dispositivo '{device_id}' removido."})
        return Response({"status": "erro", "mensagem": "Dispositivo não encontrado."}, status=404)

    # POST — adicionar dispositivo manualmente
    dispositivo_id = request.data.get('dispositivo_id', '').strip()
    usuario_id = request.data.get('usuario_id')
    ip = request.data.get('ip', '0.0.0.0')

    if not dispositivo_id:
        return Response({"status": "erro", "mensagem": "dispositivo_id é obrigatório."}, status=400)

    usuario = None
    if usuario_id:
        try:
            usuario = Usuario.objects.get(id=usuario_id)
        except Usuario.DoesNotExist:
            return Response({"status": "erro", "mensagem": "Usuário não encontrado."}, status=404)

    heartbeat, created = HeartbeatLog.objects.get_or_create(
        dispositivo_id=dispositivo_id,
        defaults={'usuario': usuario, 'ip_address': ip, 'status': 'OFFLINE'}
    )
    if not created:
        return Response({"status": "erro", "mensagem": f"Dispositivo '{dispositivo_id}' já existe."}, status=409)

    return Response({
        "status": "sucesso",
        "mensagem": f"Dispositivo '{dispositivo_id}' cadastrado.",
        "id": heartbeat.id,
    })
