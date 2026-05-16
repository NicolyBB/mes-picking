from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from .models import Usuario

@csrf_exempt
@api_view(['POST'])
def validar_cracha(request):

    codigo_lido = request.data.get('cracha', '').strip()
    perfil_esperado = request.data.get('perfil', '') # 'SUPERVISOR' ou 'COLABORADOR'

    try:
        # Busca o usuário no banco de dados indexado pelo crachá
        usuario = Usuario.objects.get(cracha=codigo_lido)

        # Regra de Segurança: Verifica se o crachá lido pertence ao nível da tela
        if usuario.perfil == perfil_esperado or (perfil_esperado == 'SUPERVISOR' and usuario.perfil == 'ADM'):
            
            # Se for o Colaborador (Passo 2), atualizamos o status para ONLINE
            if perfil_esperado == 'COLABORADOR':
                usuario.login_status = True
                usuario.save()

            return Response({
                "status": "sucesso",
                "mensagem": f"Acesso Liberado: {usuario.nome}",
                "usuario_id": usuario.id,
                "nome": usuario.nome
            })
        else:
            # Trava de Segurança: Bipou crachá errado para a tela
            return Response({
                "status": "erro",
                "mensagem": f"Acesso Negado. Crachá pertence a um {usuario.perfil}, mas a tela exige {perfil_esperado}."
            }, status=403)

    except Usuario.DoesNotExist:
        # Erro de leitura ou crachá inexistente
        return Response({
            "status": "erro",
            "mensagem": "Crachá não encontrado no sistema."
        }, status=404)