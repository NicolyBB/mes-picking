import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection

print("Tipos de colunas reais no banco de dados:")

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT table_name, column_name, data_type, column_type 
        FROM information_schema.columns 
        WHERE table_schema = 'mes_picking_kyly' 
          AND table_name IN ('usuario', 'pedido', 'item_pedido');
    """)
    rows = cursor.fetchall()
    for r in rows:
        print(f"{r[0]}.{r[1]}: {r[3]}")
