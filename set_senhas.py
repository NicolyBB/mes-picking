import os, sys, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from authentication.models import Usuario

def set_pw(cracha, senha):
    try:
        u = Usuario.objects.get(cracha=cracha)
        u.senha = hashlib.sha256(senha.encode()).hexdigest()
        u.save()
        print(f'OK: {cracha} -> senha definida')
    except Usuario.DoesNotExist:
        print(f'NAO ENCONTRADO: {cracha}')

set_pw('ADM-1111', 'adm123')
set_pw('SUP-9999', 'sup123')
print('Concluido.')
