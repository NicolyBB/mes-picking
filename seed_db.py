import os
import django
from datetime import timedelta
import random

# Inicializa o ambiente Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.utils import timezone
from authentication.models import Usuario
from picking_engine.models import Pedido, ItemPedido, SessaoPicking, HeartbeatLog

def run():
    print("🧹 Limpando dados antigos (Pedidos, Itens e Sessões)...")
    SessaoPicking.objects.all().delete()
    ItemPedido.objects.all().delete()
    Pedido.objects.all().delete()
    # Não vamos deletar os usuários para não quebrar seus logins

    # 1. Criação de Usuários de Teste (Caso não existam)
    print("👤 Garantindo que temos usuários de teste...")
    supervisor, _ = Usuario.objects.get_or_create(
        cracha="SUP-9999",
        defaults={"nome": "Supervisor Teste", "perfil": "SUPERVISOR", "ativo": True}
    )
    
    colabs = []
    for i in range(1, 6):
        colab, _ = Usuario.objects.get_or_create(
            cracha=f"COLAB-00{i}",
            defaults={"nome": f"Operador 00{i}", "perfil": "COLABORADOR", "ativo": True, "supervisor_resp": supervisor, "setor": "Corredor A"}
        )
        colabs.append(colab)

        # Atualiza Heartbeat para parecer que estão ONLINE
        HeartbeatLog.objects.update_or_create(
            usuario=colab,
            defaults={"ultimo_sinal": timezone.now(), "dispositivo_id": "Datalogic-M11"}
        )

    # 2. Geração de Pedidos e Sessões
    print("📦 Gerando Pedidos e Itens massivos...")
    status_opcoes = ['FINALIZADO', 'FINALIZADO', 'FINALIZADO', 'PARCIAL', 'EM_PICKING']
    
    agora = timezone.localtime(timezone.now())
    
    for i in range(1, 51):  # Cria 50 pedidos
        status_pedido = random.choice(status_opcoes)
        total_pecas = random.randint(10, 80)
        
        pedido = Pedido.objects.create(
            numero_pedido=f"PED-MASSIVO-{i:03d}",
            cliente=f"Cliente Fantasia {random.randint(1, 10)}",
            total_pecas=total_pecas,
            status=status_pedido
        )

        itens_para_criar = []
        bipadas = 0
        
        # Define o progresso baseado no status do pedido
        if status_pedido == 'FINALIZADO':
            bipadas = total_pecas
        elif status_pedido == 'PARCIAL' or status_pedido == 'EM_PICKING':
            bipadas = random.randint(1, total_pecas - 1)
            
        erros_sessao = random.randint(0, 3) if bipadas > 0 else 0

        # Cria os itens do pedido
        for j in range(1, total_pecas + 1):
            status_item = 'BIPADO' if j <= bipadas else 'PENDENTE'
            itens_para_criar.append(ItemPedido(
                pedido=pedido,
                referencia=f"REF-{random.randint(1000, 9999)}",
                cor=random.choice(["Azul", "Vermelho", "Preto", "Branco"]),
                tamanho=random.choice(["P", "M", "G", "GG"]),
                endereco=f"C-{random.randint(1, 10):02d}-{random.randint(1, 10):02d}",
                codigo_barras=f"789{random.randint(1000000000, 9999999999)}",
                ordem=j,
                status=status_item
            ))
        
        ItemPedido.objects.bulk_create(itens_para_criar)

        # 3. Criação de Sessões de Picking (Para os KPIs funcionarem)
        if bipadas > 0:
            colab = random.choice(colabs)
            
            # Distribui as sessões ao longo das últimas 8 horas de hoje
            horas_atras = random.uniform(0.1, 8.0)
            inicio_sessao = agora - timedelta(hours=horas_atras)
            
            # PPH fictício realista (entre 100 e 200 peças por hora) -> tempo = pecas / PPH
            pph_simulado = random.randint(100, 200)
            horas_duracao = bipadas / pph_simulado
            fim_sessao = inicio_sessao + timedelta(hours=horas_duracao)

            item_atual = None
            if status_pedido != 'FINALIZADO':
                item_atual = pedido.itens.filter(status='PENDENTE').first()

            sessao = SessaoPicking.objects.create(
                pedido=pedido,
                colaborador=colab,
                item_atual=item_atual,
                inicio=inicio_sessao,
                fim=fim_sessao if status_pedido == 'FINALIZADO' or status_pedido == 'PARCIAL' else None,
                ativa=(status_pedido == 'EM_PICKING'),
                pecas_bipadas=bipadas,
                erros=erros_sessao
            )
            # Como o auto_now_add substitui o 'inicio' na criação, forçamos o update direto no banco
            SessaoPicking.objects.filter(id=sessao.id).update(inicio=inicio_sessao, fim=fim_sessao if status_pedido == 'FINALIZADO' or status_pedido == 'PARCIAL' else None)

    print("✅ Sucesso! 50 caixas criadas com dados perfeitos para os KPIs.")
    print("Agora é só olhar os seus Dashboards! 🎉")

if __name__ == '__main__':
    run()
