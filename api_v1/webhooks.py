import requests
import json
import threading

# Usamos 'threading' para disparar o webhook em segundo plano. 
# Isso garante que a latência para o operador no coletor continue sendo < 200ms!
def disparar_webhook_assincrono(evento, dados_incidente):

    
    payload = {
        "event_type": evento,
        "priority": "HIGH" if evento == "URGENT_REPLENISHMENT" else "MEDIUM",
        "incident_details": dados_incidente
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer TOKEN_DE_SEGURANCA_KYLY"
    }
 
    try:
        # Disparo Real para a internet!
        requests.post(url_destino, json=payload, headers=headers, timeout=3)
        print(f"Webhook {evento} disparado com sucesso!")
    except requests.exceptions.RequestException as e:
        print(f"Erro ao disparar webhook: {e}")

# Função que o Django vai chamar
def notificar_setor_compras(sku, endereco, faltas_consecutivas):
    dados = {
        "sku_referencia": sku,
        "address": endereco,
        "trigger_count": faltas_consecutivas,
        "action_required": "Priorizar reposição no armazém - Operação travada."
    }
    # Inicia a thread para não prender a resposta do AJAX
    thread = threading.Thread(target=disparar_webhook_assincrono, args=("URGENT_REPLENISHMENT", dados))
    thread.start()
