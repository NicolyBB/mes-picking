# Gerada manualmente — adiciona modelos WebhookConfig, KPIDefinicao, HeartbeatLog
# e campo fim + campos faltantes em SessaoPicking
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('picking_engine', '0001_initial'),
        ('authentication', '0002_usuario_campos_extras'),
    ]

    operations = [
        # ── Campo fim em SessaoPicking ──────────────────────────
        migrations.AddField(
            model_name='sessaopicking',
            name='fim',
            field=models.DateTimeField(blank=True, null=True),
        ),

        # ── WebhookConfig ───────────────────────────────────────
        migrations.CreateModel(
            name='WebhookConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100)),
                ('url_destino', models.CharField(max_length=500)),
                ('evento_gatilho', models.CharField(
                    choices=[
                        ('FALTA_PECA', 'Falta de Peça no Endereço'),
                        ('DEVICE_OFFLINE', 'Coletor Offline (Heartbeat)'),
                        ('AGING_STOCK', 'Aging Stock (> X dias)'),
                        ('CAIXA_PARCIAL', 'Caixa Encerrada Parcialmente'),
                        ('PPH_BAIXO', 'PPH abaixo da meta'),
                    ],
                    max_length=30,
                )),
                ('threshold', models.IntegerField(default=3)),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('ultimo_disparo', models.DateTimeField(blank=True, null=True)),
            ],
            options={'db_table': 'webhook_config'},
        ),

        # ── KPIDefinicao ────────────────────────────────────────
        migrations.CreateModel(
            name='KPIDefinicao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100)),
                ('icone', models.CharField(blank=True, default='📊', max_length=10)),
                ('formula', models.TextField(blank=True, default='')),
                ('meta', models.CharField(blank=True, default='', max_length=50)),
                ('tom_cor', models.CharField(
                    choices=[
                        ('GREEN', 'Verde'),
                        ('YELLOW', 'Amarelo'),
                        ('RED', 'Vermelho'),
                        ('BLUE', 'Azul'),
                    ],
                    default='GREEN',
                    max_length=10,
                )),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'kpi_definicao'},
        ),

        # ── HeartbeatLog ────────────────────────────────────────
        migrations.CreateModel(
            name='HeartbeatLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dispositivo_id', models.CharField(max_length=100)),
                ('ultimo_sinal', models.DateTimeField(auto_now=True)),
                ('status', models.CharField(
                    choices=[
                        ('ONLINE', 'Online'),
                        ('TIMEOUT', 'Timeout (>5min)'),
                        ('OFFLINE', 'Offline'),
                    ],
                    default='ONLINE',
                    max_length=10,
                )),
                ('ip_address', models.CharField(blank=True, default='', max_length=50)),
                ('usuario', models.ForeignKey(
                    blank=True,
                    db_constraint=False,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='authentication.usuario',
                )),
            ],
            options={'db_table': 'heartbeat_log'},
        ),
    ]
