from django.contrib import admin
from .models import Pedido, ItemPedido, SessaoPicking


class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 1
    fields = ('ordem', 'referencia', 'cor', 'tamanho', 'endereco', 'codigo_barras', 'status')


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('numero_pedido', 'cliente', 'status', 'total_pecas', 'peso_bruto', 'data_criacao')
    list_filter = ('status',)
    search_fields = ('numero_pedido', 'cliente')
    inlines = [ItemPedidoInline]


@admin.register(ItemPedido)
class ItemPedidoAdmin(admin.ModelAdmin):
    list_display = ('pedido', 'referencia', 'cor', 'tamanho', 'endereco', 'codigo_barras', 'status', 'ordem')
    list_filter = ('status',)
    search_fields = ('referencia', 'codigo_barras', 'endereco')


@admin.register(SessaoPicking)
class SessaoPickingAdmin(admin.ModelAdmin):
    list_display = ('id', 'pedido', 'colaborador', 'pecas_bipadas', 'erros', 'ativa', 'inicio')
    list_filter = ('ativa',)
