import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection

# Vamos deletar as tabelas velhas que estavam no banco atrapalhando
tables = ['sessao_picking', 'item_pedido', 'pedido']

with connection.cursor() as cursor:
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    for table in tables:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table};")
            print(f"Tabela {table} apagada com sucesso.")
        except Exception as e:
            print(f"Ignorado {table}: {e}")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

print("Pronto! Banco de dados limpo para receber a estrutura correta.")
