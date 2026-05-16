from django.db import models

class Usuario(models.Model):
    # Definição dos níveis de acesso (RBAC)
    PERFIS_CHOICES = [
        ('COLABORADOR', 'Colaborador'),
        ('SUPERVISOR', 'Supervisor'),
        ('ADM', 'Administrador'),
    ]

    # Campos exigidos pelo Dicionário de Dados
    nome = models.CharField(max_length=100)
    cracha = models.CharField(max_length=50, unique=True) # Login via bipe laser
    perfil = models.CharField(max_length=20, choices=PERFIS_CHOICES)
    login_status = models.BooleanField(default=False) # Monitoramento de sessão
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'usuario' # Força o nome exato da tabela no MySQL

    def __str__(self):
        return f"{self.nome} ({self.perfil})"