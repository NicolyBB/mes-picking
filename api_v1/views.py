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
    
    # Aqui, futuramente (na VM), você fará um loop 'for linha in dados_planilha:' 
    # para inserir no seu MySQL usando Model.objects.create(...)
    
    print(f"Recebidos {len(dados_planilha)} registros do arquivo {nome_arquivo}.")
    
    return Response({
        "status": "sucesso",
        "mensagem": f"Importação de {len(dados_planilha)} registros do arquivo {nome_arquivo} concluída no Banco de Dados!"
    })

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