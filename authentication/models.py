from django.db import models

class Usuario(models.Model):
    PERFIS_CHOICES = [
        ('COLABORADOR', 'Colaborador'),
        ('SUPERVISOR', 'Supervisor'),
        ('ADM', 'Administrador'),
    ]

    nome = models.CharField(max_length=100)
    cracha = models.CharField(max_length=50, unique=True)
    perfil = models.CharField(max_length=20, choices=PERFIS_CHOICES)
    setor = models.CharField(max_length=50, blank=True, default='')
    turno = models.CharField(max_length=20, blank=True, default='')
    supervisor_resp = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        limit_choices_to={'perfil': 'SUPERVISOR'},
        related_name='equipe_supervisionada',
        db_constraint=False
    )
    data_admissao = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)
    login_status = models.BooleanField(default=False)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'usuario'

    def __str__(self):
        return f"{self.nome} ({self.perfil})"

class LogAuditoriaUsuario(models.Model):
    ACAO_CHOICES = [
        ('CRIADO', 'Criado'),
        ('MODIFICADO', 'Modificado'),
        ('EXCLUIDO', 'Excluído/Demitido'),
        ('ATRIBUIDO', 'Atribuído a Equipe'),
    ]

    usuario_alvo = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='logs_recebidos', db_constraint=False)
    acao = models.CharField(max_length=20, choices=ACAO_CHOICES)
    autor = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='logs_gerados', db_constraint=False)
    detalhes = models.TextField(blank=True, default='')
    data_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'log_auditoria_usuario'
        ordering = ['-data_hora']

    def __str__(self):
        return f"{self.usuario_alvo.nome} - {self.acao} em {self.data_hora}"