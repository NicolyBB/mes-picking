from django.db import models
from authentication.models import Usuario


class Pedido(models.Model):
    STATUS_CHOICES = [
        ('ABERTO', 'Aberto'),
        ('EM_PICKING', 'Em Picking'),
        ('PARCIAL', 'Parcial'),
        ('FINALIZADO', 'Finalizado'),
    ]
    numero_pedido = models.CharField(max_length=50, unique=True)
    cliente = models.CharField(max_length=150)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ABERTO')
    total_pecas = models.IntegerField(default=0)
    peso_bruto = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pedido'

    def __str__(self):
        return f"Pedido {self.numero_pedido} - {self.cliente}"


class ItemPedido(models.Model):
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('BIPADO', 'Bipado'),
        ('PULADO', 'Pulado'),
        ('DANIFICADO', 'Danificado'),
    ]
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='itens', db_constraint=False)
    referencia = models.CharField(max_length=50)
    cor = models.CharField(max_length=50)
    tamanho = models.CharField(max_length=20)
    endereco = models.CharField(max_length=50)
    codigo_barras = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    ordem = models.IntegerField(default=0)

    class Meta:
        db_table = 'item_pedido'
        ordering = ['ordem']

    def __str__(self):
        return f"{self.referencia} - {self.endereco}"


class SessaoPicking(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, db_constraint=False)
    colaborador = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, db_constraint=False)
    item_atual = models.ForeignKey(ItemPedido, on_delete=models.SET_NULL, null=True, blank=True, db_constraint=False)
    pecas_bipadas = models.IntegerField(default=0)
    erros = models.IntegerField(default=0)
    inicio = models.DateTimeField(auto_now_add=True)
    fim = models.DateTimeField(null=True, blank=True)
    ativa = models.BooleanField(default=True)

    class Meta:
        db_table = 'sessao_picking'

    def __str__(self):
        return f"Sessão {self.id} - {self.colaborador}"


# ──────────────────────────────────────────────
# WEBHOOKS
# ──────────────────────────────────────────────
class WebhookConfig(models.Model):
    EVENTO_CHOICES = [
        ('FALTA_PECA', 'Falta de Peça no Endereço'),
        ('DEVICE_OFFLINE', 'Coletor Offline (Heartbeat)'),
        ('AGING_STOCK', 'Aging Stock (> X dias)'),
        ('CAIXA_PARCIAL', 'Caixa Encerrada Parcialmente'),
        ('PPH_BAIXO', 'PPH abaixo da meta'),
    ]

    nome = models.CharField(max_length=100)
    url_destino = models.CharField(max_length=500)
    evento_gatilho = models.CharField(max_length=30, choices=EVENTO_CHOICES)
    threshold = models.IntegerField(default=3)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    ultimo_disparo = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'webhook_config'

    def __str__(self):
        return f"{self.nome} → {self.evento_gatilho}"


# ──────────────────────────────────────────────
# KPI DEFINITIONS
# ──────────────────────────────────────────────
class KPIDefinicao(models.Model):
    COR_CHOICES = [
        ('GREEN', 'Verde'),
        ('YELLOW', 'Amarelo'),
        ('RED', 'Vermelho'),
        ('BLUE', 'Azul'),
    ]

    nome = models.CharField(max_length=100)
    icone = models.CharField(max_length=10, blank=True, default='📊')
    formula = models.TextField(blank=True, default='')
    meta = models.CharField(max_length=50, blank=True, default='')
    tom_cor = models.CharField(max_length=10, choices=COR_CHOICES, default='GREEN')
    supervisor_resp = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={'perfil': 'SUPERVISOR'}, db_constraint=False)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kpi_definicao'

    def __str__(self):
        return self.nome


# ──────────────────────────────────────────────
# HEARTBEAT / HARDWARE MONITORING
# ──────────────────────────────────────────────
class HeartbeatLog(models.Model):
    STATUS_CHOICES = [
        ('ONLINE', 'Online'),
        ('TIMEOUT', 'Timeout (>5min)'),
        ('OFFLINE', 'Offline'),
    ]

    dispositivo_id = models.CharField(max_length=100)
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, db_constraint=False)
    ultimo_sinal = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ONLINE')
    ip_address = models.CharField(max_length=50, blank=True, default='')

    class Meta:
        db_table = 'heartbeat_log'

    def __str__(self):
        return f"{self.dispositivo_id} — {self.status}"

# ──────────────────────────────────────────────
# HISTORICOS (AGING E EXCEÇÕES)
# ──────────────────────────────────────────────
class LogAgingStock(models.Model):
    ACAO_CHOICES = [
        ('REMOVIDO', 'Removido / Baixa Manual'),
        ('ATRIBUIDO', 'Atribuído ao Supervisor'),
        ('RESOLVIDO', 'Resolvido pelo Supervisor'),
    ]
    sku = models.CharField(max_length=100)
    endereco = models.CharField(max_length=100, blank=True)
    acao = models.CharField(max_length=20, choices=ACAO_CHOICES)
    motivo = models.TextField()
    autor = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='aging_resolvidos', db_constraint=False)
    supervisor_resp = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='aging_atribuidos', db_constraint=False)
    data_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'log_aging_stock'
        ordering = ['-data_hora']

    def __str__(self):
        return f"{self.sku} - {self.acao}"

class ExcecaoPicking(models.Model):
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('AUTORIZADO', 'Autorizado'),
        ('NEGADO', 'Negado'),
    ]
    sessao = models.ForeignKey(SessaoPicking, on_delete=models.CASCADE, related_name='excecoes', db_constraint=False)
    item = models.ForeignKey(ItemPedido, on_delete=models.CASCADE, db_constraint=False)
    motivo_operador = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    justificativa_supervisor = models.TextField(blank=True)
    supervisor_resp = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, db_constraint=False)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_resolucao = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'excecao_picking'
        ordering = ['-data_criacao']

    def __str__(self):
        return f"Exceção {self.item.referencia} - {self.status}"
