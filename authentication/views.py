from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect, render
from .models import Usuario
from picking_engine.models import HeartbeatLog


@csrf_exempt
@api_view(['POST'])
def validar_cracha(request):
    """API de login via crachá (usado pelo coletor mobile)."""
    codigo_lido = request.data.get('cracha', '').strip()
    perfil_esperado = request.data.get('perfil', '')

    try:
        usuario = Usuario.objects.get(cracha=codigo_lido, ativo=True)

        # ADM pode entrar em qualquer nível
        acesso_ok = (
            usuario.perfil == perfil_esperado
            or (perfil_esperado == 'SUPERVISOR' and usuario.perfil == 'ADM')
            or (perfil_esperado == 'COLABORADOR' and usuario.perfil in ['ADM', 'SUPERVISOR', 'COLABORADOR'])
        )

        if acesso_ok:
            if perfil_esperado == 'COLABORADOR':
                usuario.login_status = True
                usuario.save()
                request.session['colaborador_id'] = usuario.id
                request.session['colaborador_nome'] = usuario.nome

            if perfil_esperado == 'SUPERVISOR':
                request.session['supervisor_id'] = usuario.id
                request.session['supervisor_nome'] = usuario.nome

            request.session['perfil_usuario'] = usuario.perfil
            request.session['usuario_id'] = usuario.id

            # ── Registro Automático de Heartbeat ────────────────────────
            dispositivo_id = request.data.get('dispositivo_id')
            if not dispositivo_id:
                if not request.session.session_key:
                    request.session.create()
                dispositivo_id = request.session.session_key or f"coletor_{usuario.id}"
                
            ip = request.META.get('REMOTE_ADDR', '')
            HeartbeatLog.objects.update_or_create(
                dispositivo_id=dispositivo_id,
                defaults={'usuario': usuario, 'ip_address': ip, 'status': 'ONLINE'}
            )
            
            # Salvar dispositivo_id na sessão para heartbeats futuros
            request.session['dispositivo_id'] = dispositivo_id

            return Response({
                "status": "sucesso",
                "mensagem": f"Acesso Liberado: {usuario.nome}",
                "usuario_id": usuario.id,
                "nome": usuario.nome,
                "perfil": usuario.perfil,
                "dispositivo_id": dispositivo_id,
            })
        else:
            return Response({
                "status": "erro",
                "mensagem": f"Acesso Negado. Perfil {usuario.perfil} não autorizado para esta tela."
            }, status=403)

    except Usuario.DoesNotExist:
        return Response({
            "status": "erro",
            "mensagem": "Crachá não encontrado no sistema."
        }, status=404)


@api_view(['POST'])
def login_desktop(request):
    """
    Login para estação desktop (>768px).
    Recebe crachá escaneado/digitado e retorna redirect URL por perfil.
    O endpoint é chamado via fetch com o CSRF token da página.
    """
    codigo_lido = request.data.get('cracha', '').strip()

    try:
        usuario = Usuario.objects.get(cracha=codigo_lido, ativo=True)

        # Salvar na sessão
        request.session['usuario_id'] = usuario.id
        request.session['usuario_nome'] = usuario.nome
        request.session['perfil_usuario'] = usuario.perfil

        if usuario.perfil == 'COLABORADOR':
            return Response({
                "status": "erro",
                "mensagem": "Operadores devem acessar via Coletor. Solicite ao Supervisor que libere a estação primeiro."
            }, status=403)
            
        elif usuario.perfil == 'SUPERVISOR':
            redirect_url = '/dashboard/painel-operacoes/'
        else:  # ADM
            redirect_url = '/dashboard/'

        # ── Registro Automático de Heartbeat ────────────────────────
        dispositivo_id = request.data.get('dispositivo_id')
        if not dispositivo_id:
            if not request.session.session_key:
                request.session.create()
            dispositivo_id = request.session.session_key or f"desktop_{usuario.id}"
            
        ip = request.META.get('REMOTE_ADDR', '')
        HeartbeatLog.objects.update_or_create(
            dispositivo_id=dispositivo_id,
            defaults={'usuario': usuario, 'ip_address': ip, 'status': 'ONLINE'}
        )
        request.session['dispositivo_id'] = dispositivo_id

        return Response({
            "status": "sucesso",
            "nome": usuario.nome,
            "perfil": usuario.perfil,
            "redirect": redirect_url,
            "opcoes": _get_menu_opcoes(usuario.perfil),
        })

    except Usuario.DoesNotExist:
        return Response({
            "status": "erro",
            "mensagem": "Crachá não encontrado ou inativo."
        }, status=404)


@api_view(['POST'])
def logout_usuario(request):
    """Limpa a sessão e redireciona para o gateway."""
    request.session.flush()
    return Response({"status": "sucesso", "redirect": "/"})


def _get_menu_opcoes(perfil):
    """Retorna as opções de menu disponíveis por perfil."""
    opcoes = []
    if perfil == 'SUPERVISOR':
        opcoes.append({"label": "Chão de Fábrica", "url": "/coletor/operador/", "icon": "🏭"})
    if perfil in ['ADM', 'SUPERVISOR']:
        opcoes.append({"label": "Painel Supervisor", "url": "/dashboard/painel-operacoes/", "icon": "👷"})
    if perfil == 'ADM':
        opcoes.append({"label": "Dashboard KPIs", "url": "/dashboard/", "icon": "📊"})
        opcoes.append({"label": "Funcionários", "url": "/dashboard/funcionarios/", "icon": "👥"})
        opcoes.append({"label": "Gerir KPIs", "url": "/dashboard/gerir-kpis/", "icon": "📈"})
        opcoes.append({"label": "Webhooks", "url": "/dashboard/webhooks/", "icon": "🔔"})
        opcoes.append({"label": "Importação", "url": "/dashboard/importacao/", "icon": "📂"})
    return opcoes