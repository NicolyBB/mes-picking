from rest_framework.decorators import api_view
from rest_framework.response import Response
from .webhooks import notificar_setor_compras
import json
from django.views.decorators.csrf import csrf_exempt

@api_view(['POST'])
def validar_leitura_laser(request):
    
    # Endpoint que recebe o JSON do frontend via Fetch/AJAX.

    codigo = request.data.get('codigo', '')
    acao = request.data.get('acao', 'BIP') # 'BIP', 'FALTA', 'DANIFICADA'
    
    # ---------------------------------------------------------
    # 1. REGRA: BOTÃO "ITEM EM FALTA" (Gatilho do Webhook)
    # ---------------------------------------------------------
    if acao == 'FALTA':
        # Aqui, faz um COUNT no MySQL para ver se bateu 3 faltas.
        # Vamos simular que o limite de 3 vezes consecutivas foi atingido.
        notificar_setor_compras(sku=codigo, endereco="C37.09.6B", faltas_consecutivas=3)
        
        return Response({
            "status": "aviso",
            "mensagem": "Falta registrada. O setor de compras foi notificado (Webhook disparado)!"
        })

    # ---------------------------------------------------------
    # 2. REGRA: BOTÃO "PEÇA DANIFICADA" (Desvio Físico)
    # ---------------------------------------------------------
    elif acao == 'DANIFICADA':
        # Altera o status_peca para 'DANIFICADA' no MySQL (Integridade do Banco).
        return Response({
            "status": "sucesso",
            "mensagem": "Status alterado para DANIFICADA. Direcione a peça ao cesto de divergência."
        })

    # ---------------------------------------------------------
    # 3. REGRA: LEITURA NORMAL DE PEÇA (Validação do Saldo)
    # ---------------------------------------------------------
    else:
        # Se a peça for correta (Código da documentação Kyly)
        if codigo == "1000017": 
            return Response({
                "status": "sucesso",
                "mensagem": "Peça validada com sucesso!",
                "som": "bipe_curto" # Instrui o Frontend a tocar o som de sucesso
            })
        else:
            # Se errar o SKU (Gera a tela vermelha e bipe longo de 2s) 
            return Response({
                "status": "erro",
                "mensagem": "ERRO: SKU não pertence à caixa solicitada."
            }, status=400) # O 400 ativa o catch de erro no Fetch do JS

# ---------------------------------------------------------
# RECEPÇÃO DO ARQUIVO EXCEL/CSV (PIPELINE DE DADOS)
# ---------------------------------------------------------
@csrf_exempt
@api_view(['POST'])
def importar_pedidos_excel(request):

    nome_arquivo = request.data.get('arquivo', 'Planilha Desconhecida')
    dados_planilha = request.data.get('dados', [])
    
    if not dados_planilha:
        return Response({"status": "erro", "mensagem": "Nenhum dado encontrado na planilha."}, status=400)
    
    try:
        from picking_engine.models import Pedido, ItemPedido
        from django.db import transaction
        
        registros_inseridos = 0
        
        with transaction.atomic():
            pedidos_cache = {}
            itens_to_create = []
            
            for row in dados_planilha:
                num_pedido = str(row.get('pedido') or row.get('Pedido') or row.get('codigo_produto') or '').strip()
                if not num_pedido:
                    continue
                
                cliente = str(row.get('cliente') or row.get('Cliente') or 'Desconhecido')
                referencia = str(row.get('referencia') or row.get('Referencia') or num_pedido)
                cor = str(row.get('cor') or row.get('Cor') or '')
                tamanho = str(row.get('tamanho') or row.get('Tamanho') or '')
                endereco = str(row.get('endereco_picking') or row.get('endereco') or row.get('Endereco') or '')
                codigo_barras = str(row.get('codigo_barras') or row.get('EAN') or referencia)
                
                if num_pedido not in pedidos_cache:
                    pedido_obj, _ = Pedido.objects.get_or_create(
                        numero_pedido=num_pedido,
                        defaults={'cliente': cliente}
                    )
                    from django.utils import timezone
                    pedido_obj.data_criacao = timezone.now()
                    pedidos_cache[num_pedido] = pedido_obj
                else:
                    pedido_obj = pedidos_cache[num_pedido]
                
                pedido_obj.total_pecas += 1
                
                itens_to_create.append(ItemPedido(
                    pedido=pedido_obj,
                    referencia=referencia,
                    cor=cor,
                    tamanho=tamanho,
                    endereco=endereco,
                    codigo_barras=codigo_barras,
                    ordem=pedido_obj.total_pecas
                ))
                registros_inseridos += 1
                
            if itens_to_create:
                ItemPedido.objects.bulk_create(itens_to_create, batch_size=1000)
            if pedidos_cache:
                Pedido.objects.bulk_update(pedidos_cache.values(), ['total_pecas', 'data_criacao'])
                
        if registros_inseridos == 0:
            return Response({
                "status": "erro",
                "mensagem": "Nenhum registro válido foi importado. Verifique se a planilha contém a coluna 'Pedido'."
            }, status=400)
            
        print(f"Recebidos {len(dados_planilha)} registros do arquivo {nome_arquivo}. Inseridos {registros_inseridos}.")
        
        return Response({
            "status": "sucesso",
            "mensagem": f"Importação de {registros_inseridos} registros do arquivo {nome_arquivo} concluída no Banco de Dados!"
        })
        
    except Exception as e:
        print(f"Erro ao importar planilha: {str(e)}")
        return Response({
            "status": "erro",
            "mensagem": f"Erro interno ao salvar no banco de dados: {str(e)}"
        }, status=500)

# ---------------------------------------------------------
# EXPORTAÇÃO (DOWNLOAD) DE DADOS DE ESTOQUE/PEDIDOS
# ---------------------------------------------------------
from django.http import HttpResponse
import csv

def exportar_pedidos_csv(request):
    # Gera um CSV simples com todos os itens do banco para download
    from picking_engine.models import ItemPedido
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="pedidos_kyly_exportacao.csv"'
    
    writer = csv.writer(response)
    # Cabeçalho
    writer.writerow(['Pedido', 'Cliente', 'Referencia', 'Cor', 'Tamanho', 'Endereco', 'EAN', 'Status_Item', 'Status_Pedido'])
    
    itens = ItemPedido.objects.select_related('pedido').all().order_by('pedido__numero_pedido')
    
    for item in itens:
        writer.writerow([
            item.pedido.numero_pedido,
            item.pedido.cliente,
            item.referencia,
            item.cor,
            item.tamanho,
            item.endereco,
            item.codigo_barras,
            item.status,
            item.pedido.status
        ])
        
    return response

def exportar_pedido_individual_csv(request, pedido_id):
    from picking_engine.models import Pedido, ItemPedido
    from django.shortcuts import get_object_or_404
    
    pedido = get_object_or_404(Pedido, id=pedido_id)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="pedido_{pedido.numero_pedido}_export.csv"'
    
    writer = csv.writer(response)
    # Cabeçalho
    writer.writerow(['Pedido', 'Cliente', 'Referencia', 'Cor', 'Tamanho', 'Endereco', 'EAN', 'Status_Item', 'Status_Pedido'])
    
    itens = ItemPedido.objects.filter(pedido=pedido).order_by('id')
    
    for item in itens:
        writer.writerow([
            item.pedido.numero_pedido,
            item.pedido.cliente,
            item.referencia,
            item.cor,
            item.tamanho,
            item.endereco,
            item.codigo_barras,
            item.status,
            item.pedido.status
        ])
        
    return response


# ---------------------------------------------------------
# INTEGRAÇÃO IOT (PROTÓTIPO ESP32 - HARDWARE FÍSICO)
# ---------------------------------------------------------
@api_view(['GET'])
def status_hardware_iot(request):

    comando_esp32 = {
        "led_verde": False,
        "led_vermelho": False,
        "tocar_sirene": False,
        "mensagem_painel": "SISTEMA ONLINE - KYLY MES"
    }
    
    return Response(comando_esp32)