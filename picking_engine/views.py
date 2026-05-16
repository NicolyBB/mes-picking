from django.shortcuts import render

# Telas de Login Industrial (Regra de Autenticação de 2 Níveis)
def login_supervisor(request):
    return render(request, 'aguardandoSupervisor.html')

def login_colaborador(request):
    return render(request, 'Passo2colaborador.html')

# Tela de Início do Fluxo de Coleta
def abertura_caixa(request):
    return render(request, 'aberturaDeCaixa.html')

# Tela de Encerramento
def finalizacao_pick(request):
    return render(request, 'FinalizacaoPICK.html')

# Tela do Dashboard Comercial (Smart TVs)
def aging_stock(request):
    return render(request, 'aging-stock.html')

def tela_picking(request):
    return render(request, 'enderecoDePicking.html') 

# Tela de Encerramento
def finalizacao_pick(request):
    return render(request, 'FinalizacaoPICK.html')

# Tela do Dashboard Comercial (Smart TVs)
def aging_stock(request):
    return render(request, 'aging-stock.html')
