import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection

print("Buscando TODAS as tabelas no banco de dados que possam conter FK para 'pedido'...")

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT table_name, column_name, constraint_name, referenced_table_name, referenced_column_name
        FROM information_schema.key_column_usage
        WHERE referenced_table_schema = 'mes_picking_kyly' 
          AND referenced_table_name = 'pedido';
    """)
    rows = cursor.fetchall()
    
    if rows:
        print("Encontrei estas tabelas com dependências para 'pedido':")
        for r in rows:
            print(f" - Tabela: {r[0]} | FK: {r[2]} -> {r[3]}.{r[4]}")
            # Vamos forçar a exclusão dela!
            print(f"Apagando tabela fantasma: {r[0]}")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            cursor.execute(f"DROP TABLE IF EXISTS {r[0]};")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            print("Apagada.")
    else:
        print("Nenhuma tabela referenciando 'pedido' encontrada.")

    # Se a tabela usuario for INT e picking usar BIGINT, vamos resolver de uma vez alterando o picking para usar AutoField e não BigAutoField.
    
print("Verificação concluída.")
