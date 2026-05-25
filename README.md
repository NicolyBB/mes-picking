# 📦 MES Picking Engine - Kyly

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-6.x-092E20?logo=django&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-Database-4479A1?logo=mysql&logoColor=white)
![PWA](https://img.shields.io/badge/PWA-Offline%20First-5A0FC8?logo=pwa&logoColor=white)

Sistema de Execução de Manufatura (MES) de missão crítica focado na otimização de processos de **Picking** (separação de pedidos). Desenvolvido com arquitetura **Offline-First (PWA)**, projetado para garantir latência ultrabaixa (< 200ms) via chamadas AJAX e integração IoT utilizando Webhooks, operando de forma nativa com coletores **Datalogic Memor 11**.

---

## 🚀 Funcionalidades Principais

* **Gestão de Pedidos e Itens:** Controlo granular de pedidos, separação por peças, cores, tamanhos e endereçamento estruturado.
* **Sessões de Picking em Tempo Real:** Rastreio do operador, controlando peças registadas ("bipadas"), erros de leitura e cálculo dinâmico de **PPH** (Peças Por Hora).
* **Fluxo de Exceções (Andon):** Sistema de bloqueio e autorização via supervisores para itens não encontrados (Pulados) ou danificados.
* **Monitorização de Hardware (Heartbeat):** Logs automáticos de saúde dos dispositivos Datalogic para identificar quedas de ligação de rede ou inatividade prolongada (> 5 min).
* **Integração Webhooks (IoT):** Disparos automáticos para serviços externos em casos de quebra de fluxo (Falta de Peça, Caixa Parcial, Aging Stock).
* **Dashboard e KPIs:** Gestão de indicadores globais e definição de metas em tempo real (Acurácia, PPH, Streaks).

---

## 🛠️ Tecnologias Utilizadas

* **Backend:** Python 3.x com Django 6.x
* **API:** Django REST Framework (DRF)
* **Base de Dados:** MySQL (via `pymysql`)
* **Frontend:** PWA (Progressive Web App) + HTML/CSS/JS puros e AJAX (para máxima performance no coletor)
* **Autenticação e Permissões:** RBAC Customizado (`RBACMiddleware`) para segmentação entre Operadores e Supervisores.

---

## 🏗️ Arquitetura de Módulos (Apps)

O projeto está dividido em aplicações modulares para facilitar a escalabilidade e a manutenção:

* 📁 **`core`**: Configurações globais do sistema, variáveis de ambiente e roteamento principal.
* 📁 **`authentication`**: Gestão de utilizadores, controlo de permissões de acesso e logs de auditoria.
* 📁 **`picking_engine`**: O coração do sistema. Contém a regra de negócios de Pedidos, Sessões de Picking, KPIs e Webhooks.
* 📁 **`api_v1`**: Endpoints RESTful de alta performance que fazem a ponte entre o PWA do coletor de dados e o servidor central.

---

## ⚙️ Como executar o projeto localmente

### 1. Pré-requisitos
* Python 3.10 ou superior
* Servidor MySQL ativo (Ex: XAMPP, WAMP ou via Docker)

### 2. Configuração da Base de Dados
Certifique-se de que o seu MySQL (Ex: XAMPP) está a correr. Aceda à sua base de dados e execute o script abaixo para criar a base:
```sql
CREATE DATABASE mes_picking_kyly CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. Instalação e Execução
Clone o repositório no seu computador, abra o terminal na pasta do projeto e siga os passos abaixo:

```bash
# 1. Crie o ambiente virtual
python -m venv venv

# 2. Ative o ambiente virtual
# No Windows:
venv\Scripts\activate
# No Linux/Mac:
source venv/bin/activate

# 3. Instale as dependências necessárias
pip install django djangorestframework pymysql

# 4. Execute as migrações para criar as tabelas no MySQL
python manage.py makemigrations
python manage.py migrate

# 5. Crie um superutilizador para aceder ao painel de administração (/admin)
python manage.py createsuperuser

# 6. Inicie o servidor
python manage.py runserver 0.0.0.0:8000
```

> **💡 Dica de Rede:** Correr o servidor com `0.0.0.0:8000` permite que o coletor Datalogic (ou qualquer smartphone), desde que ligado na mesma rede Wi-Fi, consiga aceder ao sistema através do endereço IPv4 da sua máquina (Ex: `http://192.168.0.X:8000`).

---

## 📊 Regras de Negócio e Base de Dados

* **Desacoplamento de Integridade (`db_constraint=False`):** O projeto desativa restrições de chaves estrangeiras ao nível da base de dados em pontos estratégicos. Isto evita estrangulamentos de *locks* no MySQL durante operações massivas e simultâneas de leitura de código de barras. A garantia de integridade referencial é gerida ativamente pela camada da aplicação no Django.
* **Auditoria Contínua:** Toda a ação de quebra de fluxo (exceção, item danificado) ou baixa manual de stock (Aging Stock) fica rigorosamente registada. O log identifica permanentemente qual Operador relatou a anomalia e qual Supervisor autorizou ou resolveu a pendência.
