"""
Django Management Command: seed_dados
======================================
Popula o banco com dados realistas de teste para o MES Picking Kyly.

Uso:
    python manage.py seed_dados           # cria tudo (idempotente)
    python manage.py seed_dados --flush   # limpa tudo antes de criar
    python manage.py seed_dados --sessoes # cria sessoes historicas extras

Cria:
    - 1 ADM + 3 Supervisores + 12 Colaboradores
    - 6 Pedidos (mix de status)
    - ~120 Itens de Pedido distribuídos entre os pedidos
    - 8 Sessões de Picking (hoje + histórico últimos 7 dias)
    - 5 KPIs definidos
    - 3 Webhooks configurados
    - 4 Heartbeats (coletores)
"""

import random
import hashlib
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from authentication.models import Usuario
from picking_engine.models import (
    Pedido, ItemPedido, SessaoPicking,
    KPIDefinicao, WebhookConfig, HeartbeatLog,
)


# ──────────────────────────────────────────────────────────────
# DADOS MESTRES DE REFERÊNCIA
# ──────────────────────────────────────────────────────────────

USUARIOS = [
    # (nome, cracha, perfil, setor, turno)
    ("Administrador Kyly",   "ADM-001",  "ADM",         "TI",          "MANHA"),
    ("Ricardo Pereira",      "SUP-001",  "SUPERVISOR",  "Expedição",   "MANHA"),
    ("Fernanda Alves",       "SUP-002",  "SUPERVISOR",  "Expedição",   "TARDE"),
    ("Marcos Vinicius",      "SUP-003",  "SUPERVISOR",  "Logística",   "NOITE"),
    # Colaboradores — Turno Manhã
    ("Carla Mendes",         "K-1042",   "COLABORADOR", "Corredor A",  "MANHA"),
    ("Bruno Lima",           "K-1188",   "COLABORADOR", "Corredor B",  "MANHA"),
    ("Patrícia Souza",       "K-0987",   "COLABORADOR", "Corredor C",  "MANHA"),
    ("Diego Antunes",        "K-1230",   "COLABORADOR", "Corredor D",  "MANHA"),
    # Colaboradores — Turno Tarde
    ("Renata Cruz",          "K-1345",   "COLABORADOR", "Corredor A",  "TARDE"),
    ("Felipe Gomes",         "K-1502",   "COLABORADOR", "Corredor E",  "TARDE"),
    ("Aline Rocha",          "K-1611",   "COLABORADOR", "Corredor B",  "TARDE"),
    ("Thiago Barros",        "K-1723",   "COLABORADOR", "Corredor F",  "TARDE"),
    # Colaboradores — Turno Noite
    ("Luciana Martins",      "K-1890",   "COLABORADOR", "Corredor C",  "NOITE"),
    ("Eduardo Costa",        "K-2001",   "COLABORADOR", "Corredor G",  "NOITE"),
    ("Juliana Ferreira",     "K-2115",   "COLABORADOR", "Corredor D",  "NOITE"),
    ("Anderson Silva",       "K-2230",   "COLABORADOR", "Corredor H",  "NOITE"),
]

CLIENTES = [
    "Magazine Luiza - CD Louveira",
    "Riachuelo - CD Natal",
    "Renner - CD Cajamar",
    "Marisa - CD São Paulo",
    "Carrefour Fashion - CD Barueri",
    "Amazon BR - CD Cajamar",
]

# Referências de peças reais de moda infantil
REFERENCIAS = [
    ("1000044", "Branco",     "P"),
    ("1000044", "Branco",     "M"),
    ("1000044", "Branco",     "G"),
    ("1000044", "Rosa",       "P"),
    ("1000044", "Rosa",       "M"),
    ("1000045", "Azul",       "PP"),
    ("1000045", "Azul",       "P"),
    ("1000045", "Azul",       "M"),
    ("1000045", "Azul",       "G"),
    ("1000046", "Verde",      "P"),
    ("1000046", "Verde",      "M"),
    ("1000046", "Amarelo",    "G"),
    ("1000047", "Preto",      "P"),
    ("1000047", "Preto",      "G"),
    ("1000048", "Vermelho",   "M"),
    ("1000048", "Listrado",   "P"),
    ("1000049", "Estampado",  "P"),
    ("1000049", "Estampado",  "M"),
    ("1000050", "Nude",       "M"),
    ("1000051", "Jeans",      "14"),
    ("1000051", "Jeans",      "16"),
    ("1000052", "Xadrez",     "10"),
    ("1000053", "Floral",     "8"),
]

# Endereços do galpão (corredor-rua-coluna-nível)
ENDERECOS = [
    "A01.01.1A", "A01.02.2B", "A01.03.3C", "A02.01.1A", "A02.02.2B",
    "B03.01.1A", "B03.02.2B", "B03.03.3C", "B04.01.1A", "B04.02.2B",
    "C05.01.1A", "C05.02.2B", "C05.03.3C", "C06.01.1A", "C06.02.2B",
    "D07.01.1A", "D07.02.2B", "D07.03.3C", "D08.01.1A", "D08.02.2B",
    "E09.01.1A", "E09.02.2B", "E09.03.3C", "E10.01.1A", "E10.02.2B",
    "F11.01.1A", "F11.02.2B", "F11.03.3C", "G12.01.1A", "G12.02.2B",
]

KPIS_PADRAO = [
    ("PPH Global",         "pecas_bipadas / horas_trabalhadas",          "≥ 130",   "GREEN"),
    ("Caixas/Dia",         "sessoes_finalizadas.count()",                "≥ 300",   "BLUE"),
    ("Taxa de Acerto",     "100 - (erros / total_bipados * 100)",        "≥ 99%",   "GREEN"),
    ("Lead Time Médio",    "avg(fim - inicio) por caixa",                "≤ 12min", "YELLOW"),
    ("Streak Máximo",      "max_sequencia_sem_erros",                    "≥ 50",    "GREEN"),
]

WEBHOOKS_PADRAO = [
    ("Alerta Falta de Peça",     "https://hooks.slack.com/services/KYLY/FALTAPECA",    "FALTA_PECA",    3),
    ("Coletor Offline",          "https://hooks.slack.com/services/KYLY/OFFLINE",      "DEVICE_OFFLINE", 1),
    ("PPH Abaixo da Meta",       "https://hooks.slack.com/services/KYLY/PPHBAIXO",     "PPH_BAIXO",     2),
]


def gerar_codigo_barras(ref, cor, tam):
    """Gera EAN-13 simulado baseado nos atributos do produto."""
    base = f"789{ref}{cor[:2].upper()}{tam}"
    digest = hashlib.md5(base.encode()).hexdigest()[:9]
    return f"789{digest.upper()}"


def gerar_numero_pedido(seq):
    return f"PED-{timezone.now().year}-{seq:05d}"


class Command(BaseCommand):
    help = "Popula o banco com dados de teste realistas para o MES Picking Kyly"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Limpa todos os dados existentes antes de criar os novos",
        )
        parser.add_argument(
            "--sessoes",
            action="store_true",
            help="Cria sessões históricas extras (últimos 7 dias) para KPIs com dados ricos",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("\n🏭  MES Picking — Seed de Dados de Teste\n"))

        if options["flush"]:
            self._flush()

        usuarios    = self._criar_usuarios()
        pedidos     = self._criar_pedidos()
        self._criar_itens(pedidos)
        self._criar_sessoes(pedidos, usuarios, historico=options["sessoes"])
        self._criar_kpis()
        self._criar_webhooks()
        self._criar_heartbeats(usuarios)

        self.stdout.write(self.style.SUCCESS("\n✅  Seed concluído com sucesso!\n"))
        self._imprimir_resumo(usuarios, pedidos)

    # ──────────────────────────────────────────────────────────
    # FLUSH
    # ──────────────────────────────────────────────────────────
    def _flush(self):
        self.stdout.write("⚠️  Limpando dados existentes...")
        HeartbeatLog.objects.all().delete()
        WebhookConfig.objects.all().delete()
        KPIDefinicao.objects.all().delete()
        SessaoPicking.objects.all().delete()
        ItemPedido.objects.all().delete()
        Pedido.objects.all().delete()
        Usuario.objects.all().delete()
        self.stdout.write(self.style.WARNING("   Dados limpos.\n"))

    # ──────────────────────────────────────────────────────────
    # USUÁRIOS
    # ──────────────────────────────────────────────────────────
    def _criar_usuarios(self):
        self.stdout.write("👤  Criando usuários...")
        criados = []
        for i, (nome, cracha, perfil, setor, turno) in enumerate(USUARIOS):
            u, created = Usuario.objects.get_or_create(
                cracha=cracha,
                defaults={
                    "nome": nome,
                    "perfil": perfil,
                    "setor": setor,
                    "turno": turno,
                    "ativo": True,
                    "data_admissao": date(2023, 1, 15) + timedelta(days=i * 30),
                }
            )
            criados.append(u)
            status = "✔ criado" if created else "→ já existe"
            self.stdout.write(f"   [{u.perfil:12}] {u.nome:25} crachá: {u.cracha}  {status}")
        return criados

    # ──────────────────────────────────────────────────────────
    # PEDIDOS
    # ──────────────────────────────────────────────────────────
    def _criar_pedidos(self):
        self.stdout.write("\n📋  Criando pedidos...")
        pedidos_def = [
            # (numero, cliente, status, total_pecas, peso_bruto)
            (gerar_numero_pedido(1),  CLIENTES[0], "ABERTO",      85,  12.500),
            (gerar_numero_pedido(2),  CLIENTES[1], "ABERTO",      120, 18.750),
            (gerar_numero_pedido(3),  CLIENTES[2], "EM_PICKING",  60,  9.200),
            (gerar_numero_pedido(4),  CLIENTES[3], "FINALIZADO",  200, 31.400),
            (gerar_numero_pedido(5),  CLIENTES[4], "PARCIAL",     45,  7.300),
            (gerar_numero_pedido(6),  CLIENTES[5], "ABERTO",      150, 22.800),
        ]

        criados = []
        for numero, cliente, status, total, peso in pedidos_def:
            p, created = Pedido.objects.get_or_create(
                numero_pedido=numero,
                defaults={
                    "cliente": cliente,
                    "status": status,
                    "total_pecas": total,
                    "peso_bruto": peso,
                }
            )
            criados.append(p)
            status_txt = "✔ criado" if created else "→ já existe"
            self.stdout.write(f"   [{p.status:12}] {p.numero_pedido}  {p.cliente[:35]}  {status_txt}")
        return criados

    # ──────────────────────────────────────────────────────────
    # ITENS
    # ──────────────────────────────────────────────────────────
    def _criar_itens(self, pedidos):
        self.stdout.write("\n📦  Criando itens de pedido...")
        total_criados = 0

        for pedido in pedidos:
            if pedido.itens.exists():
                self.stdout.write(f"   {pedido.numero_pedido}: itens já existem, pulando.")
                continue

            # Sorteia entre 5-23 referências para este pedido
            n_refs = random.randint(5, min(len(REFERENCIAS), 23))
            refs_pedido = random.sample(REFERENCIAS, n_refs)
            enderecos_pedido = random.sample(ENDERECOS, n_refs)

            itens = []
            for ordem, ((ref, cor, tam), endereco) in enumerate(zip(refs_pedido, enderecos_pedido)):
                cod = gerar_codigo_barras(ref, cor, tam)

                # Determina status do item com base no status do pedido
                if pedido.status == "FINALIZADO":
                    st = "BIPADO"
                elif pedido.status == "PARCIAL":
                    # 60% bipados, resto pendente
                    st = "BIPADO" if ordem < int(n_refs * 0.6) else "PENDENTE"
                elif pedido.status == "EM_PICKING":
                    # primeiros bipados, resto pendente
                    st = "BIPADO" if ordem < 3 else "PENDENTE"
                else:
                    st = "PENDENTE"

                itens.append(ItemPedido(
                    pedido=pedido,
                    referencia=ref,
                    cor=cor,
                    tamanho=tam,
                    endereco=endereco,
                    codigo_barras=cod,
                    status=st,
                    ordem=ordem + 1,
                ))

            ItemPedido.objects.bulk_create(itens)
            total_criados += len(itens)
            self.stdout.write(f"   {pedido.numero_pedido}: {len(itens)} itens criados")

        self.stdout.write(f"   Total: {total_criados} itens")

    # ──────────────────────────────────────────────────────────
    # SESSÕES DE PICKING
    # ──────────────────────────────────────────────────────────
    def _criar_sessoes(self, pedidos, usuarios, historico=False):
        self.stdout.write("\n🔄  Criando sessões de picking...")

        colaboradores = [u for u in usuarios if u.perfil == "COLABORADOR"]
        if not colaboradores:
            self.stdout.write(self.style.WARNING("   Nenhum colaborador encontrado."))
            return

        agora = timezone.now()
        criadas = 0

        # ─ Sessões de hoje ─────────────────────────────────
        pedidos_pra_picking = [p for p in pedidos if p.status in ("EM_PICKING", "FINALIZADO", "PARCIAL")]

        cenarios_hoje = [
            # (colaborador_idx, pedido_idx, pecas, erros, ativa, min_atras_inicio, min_duracao)
            (0,  2, 35,  0, True,  90,  None),   # Carla — sessão ativa
            (1,  2, 22,  1, True,  60,  None),   # Bruno — ativo
            (2,  3, 45,  0, False, 180, 120),    # Patrícia — finalizou
            (3,  4, 18,  3, False, 240, 95),     # Diego — finalizou c/ erros
            (4,  0, 55,  0, False, 300, 150),    # Renata — finalizou (campeã)
        ]

        for col_idx, ped_idx, pecas, erros, ativa, min_ini, duracao in cenarios_hoje:
            col = colaboradores[col_idx % len(colaboradores)]
            ped = pedidos_pra_picking[ped_idx % len(pedidos_pra_picking)] if pedidos_pra_picking else pedidos[0]

            if SessaoPicking.objects.filter(colaborador=col, pedido=ped).exists():
                continue

            inicio = agora - timedelta(minutes=min_ini)
            fim = (inicio + timedelta(minutes=duracao)) if duracao else None

            # Item atual para sessão ativa
            item_atual = None
            if ativa:
                item_atual = ped.itens.filter(status="PENDENTE").first()

            SessaoPicking.objects.create(
                pedido=ped,
                colaborador=col,
                item_atual=item_atual,
                pecas_bipadas=pecas,
                erros=erros,
                ativa=ativa,
                fim=fim,
            )
            # Ajusta o timestamp de inicio manualmente (auto_now_add não permite)
            SessaoPicking.objects.filter(colaborador=col, pedido=ped).update(inicio=inicio)
            criadas += 1

        # ─ Sessões históricas (últimos 7 dias) ──────────────
        if historico:
            self.stdout.write("   Criando histórico dos últimos 7 dias...")
            for dias_atras in range(1, 8):
                data_dia = agora - timedelta(days=dias_atras)
                n_sessoes = random.randint(8, 16)

                for i in range(n_sessoes):
                    col = random.choice(colaboradores)
                    ped = random.choice(pedidos)
                    pecas = random.randint(20, 180)
                    erros = random.randint(0, max(0, pecas // 30))
                    inicio_dia = data_dia.replace(
                        hour=random.randint(6, 21),
                        minute=random.randint(0, 59),
                        second=0,
                    )
                    duracao_min = random.randint(30, 240)
                    fim_dia = inicio_dia + timedelta(minutes=duracao_min)

                    s = SessaoPicking.objects.create(
                        pedido=ped,
                        colaborador=col,
                        item_atual=None,
                        pecas_bipadas=pecas,
                        erros=erros,
                        ativa=False,
                        fim=fim_dia,
                    )
                    SessaoPicking.objects.filter(pk=s.pk).update(inicio=inicio_dia)
                    criadas += 1

        self.stdout.write(f"   {criadas} sessões criadas.")

    # ──────────────────────────────────────────────────────────
    # KPIs
    # ──────────────────────────────────────────────────────────
    def _criar_kpis(self):
        self.stdout.write("\n📊  Criando KPIs...")
        for nome, formula, meta, cor in KPIS_PADRAO:
            k, created = KPIDefinicao.objects.get_or_create(
                nome=nome,
                defaults={"formula": formula, "meta": meta, "tom_cor": cor, "icone": nome[:2]},
            )
            self.stdout.write(f"   {'✔' if created else '→'} {k.nome}")

    # ──────────────────────────────────────────────────────────
    # WEBHOOKS
    # ──────────────────────────────────────────────────────────
    def _criar_webhooks(self):
        self.stdout.write("\n🔗  Criando webhooks...")
        for nome, url, evento, threshold in WEBHOOKS_PADRAO:
            w, created = WebhookConfig.objects.get_or_create(
                nome=nome,
                defaults={"url_destino": url, "evento_gatilho": evento, "threshold": threshold, "ativo": True},
            )
            self.stdout.write(f"   {'✔' if created else '→'} {w.nome}")

    # ──────────────────────────────────────────────────────────
    # HEARTBEATS
    # ──────────────────────────────────────────────────────────
    def _criar_heartbeats(self, usuarios):
        self.stdout.write("\n💻  Criando heartbeats dos coletores...")
        colaboradores = [u for u in usuarios if u.perfil == "COLABORADOR"]

        coletores = [
            ("MEMOR11-001", colaboradores[0] if len(colaboradores) > 0 else None, "ONLINE",  "192.168.1.101"),
            ("MEMOR11-002", colaboradores[1] if len(colaboradores) > 1 else None, "ONLINE",  "192.168.1.102"),
            ("MEMOR11-003", colaboradores[2] if len(colaboradores) > 2 else None, "TIMEOUT", "192.168.1.103"),
            ("MEMOR11-004", None,                                                  "OFFLINE", "192.168.1.104"),
        ]

        for disp_id, usuario, status, ip in coletores:
            h, created = HeartbeatLog.objects.get_or_create(
                dispositivo_id=disp_id,
                defaults={"usuario": usuario, "status": status, "ip_address": ip},
            )
            if not created:
                h.status = status
                h.ip_address = ip
                h.usuario = usuario
                h.save()
            self.stdout.write(f"   {'✔' if created else '↻'} {disp_id}  [{status:7}]  {ip}")

    # ──────────────────────────────────────────────────────────
    # RESUMO FINAL
    # ──────────────────────────────────────────────────────────
    def _imprimir_resumo(self, usuarios, pedidos):
        self.stdout.write("\n" + "═" * 60)
        self.stdout.write(self.style.MIGRATE_HEADING("  📋  RESUMO DO BANCO DE DADOS"))
        self.stdout.write("═" * 60)
        self.stdout.write(f"  👥 Usuários      : {Usuario.objects.count():>4}  (ADM: {Usuario.objects.filter(perfil='ADM').count()} | SUP: {Usuario.objects.filter(perfil='SUPERVISOR').count()} | COL: {Usuario.objects.filter(perfil='COLABORADOR').count()})")
        self.stdout.write(f"  📋 Pedidos       : {Pedido.objects.count():>4}  (Abertos: {Pedido.objects.filter(status='ABERTO').count()} | Em Picking: {Pedido.objects.filter(status='EM_PICKING').count()} | Finalizados: {Pedido.objects.filter(status='FINALIZADO').count()})")
        self.stdout.write(f"  📦 Itens Pedido  : {ItemPedido.objects.count():>4}")
        self.stdout.write(f"  🔄 Sessões       : {SessaoPicking.objects.count():>4}  (Ativas: {SessaoPicking.objects.filter(ativa=True).count()})")
        self.stdout.write(f"  📊 KPIs          : {KPIDefinicao.objects.count():>4}")
        self.stdout.write(f"  🔗 Webhooks      : {WebhookConfig.objects.count():>4}")
        self.stdout.write(f"  💻 Coletores     : {HeartbeatLog.objects.count():>4}")
        self.stdout.write("═" * 60)
        self.stdout.write(self.style.MIGRATE_HEADING("\n  🔑  CRACHÁS PARA LOGIN"))
        self.stdout.write("─" * 60)
        for u in Usuario.objects.all().order_by("perfil", "nome"):
            self.stdout.write(f"  [{u.perfil:12}] {u.nome:28} → {u.cracha}")
        self.stdout.write("═" * 60 + "\n")
