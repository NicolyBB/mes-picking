from django.shortcuts import redirect
from django.http import HttpResponseForbidden

# URLs de dashboard que exigem autenticação
DASHBOARD_PREFIXES = [
    '/dashboard/',
]

# Perfis permitidos por prefixo
PERFIL_DASHBOARD = ['ADM', 'SUPERVISOR']


class RBACMiddleware:
    """
    Middleware de Controle de Acesso por Perfil (RBAC).
    Bloqueia Colaboradores de acessar URLs de gestão.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Verifica se a rota é um dashboard protegido
        is_dashboard = any(path.startswith(prefix) for prefix in DASHBOARD_PREFIXES)

        if is_dashboard:
            perfil = request.session.get('perfil_usuario')

            # Sem sessão → redireciona para o login
            if not perfil:
                return redirect('login_coletor')

            # Colaborador tentando acessar dashboard → bloqueado
            if perfil == 'COLABORADOR':
                return HttpResponseForbidden(
                    '<h1>403 — Acesso Negado</h1>'
                    '<p>Seu perfil de Colaborador não tem permissão para acessar o painel de gestão.</p>'
                    '<a href="/">← Voltar</a>'
                )

        return self.get_response(request)
