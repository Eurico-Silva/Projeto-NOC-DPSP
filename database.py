import os
import streamlit as st
from sqlalchemy import create_engine, text
from pathlib import Path

# Mantido para compatibilidade com outros arquivos do sistema que importam essa variável
DB_NAME = str(Path(__file__).resolve().with_name("central_comando.db"))

# Configuração da Conexão (Nuvem ou Local)
if st.secrets.get("DB_URL"):
    DB_URL = st.secrets["DB_URL"]
else:
    # URL oficial usando o Pooler estável com SSL obrigatório
    DB_URL = "postgresql+psycopg2://postgres.kugjdeaurrthelsksncq:Passagemdeturno@://supabase.com"

# Cria o motor de conexão do SQLAlchemy
engine = create_engine(DB_URL, pool_pre_ping=True)


class PostgresCursorAdapter:
    """Classe adaptadora para imitar o comportamento do cursor do SQLite no PostgreSQL"""
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=None):
        # Substitui placeholders antigos '?' por '%s' caso existam no resto do código
        cleaned_query = query.replace('?', '%s')
        
        # Executa a query
        if params:
            result = self.connection.execute(text(cleaned_query), params)
        else:
            result = self.connection.execute(text(cleaned_query))
        
        self.result = result
        return self

    def fetchall(self):
        # Converte as linhas para tuplas para manter compatibilidade com SQLite
        return [tuple(row) for row in self.result.fetchall()]

    def fetchone(self):
        row = self.result.fetchone()
        return tuple(row) if row else None


def add_missing_columns(cursor, table, columns):
    # Consulta as colunas existentes usando a tabela padrão do Postgres
    query = f"""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = '{table.lower()}'
    """
    existing = {row.lower() for row in cursor.execute(query).fetchall()}
    
    for column, definition in columns.items():
        if column.lower() not in existing:
            # Remove comandos exclusivos do SQLite que não funcionam no Postgres
            postgres_def = definition.replace("AUTOINCREMENT", "")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {postgres_def}")


def init_db():
    """Inicializa todas as tabelas e roda as migrations no Supabase"""
    with engine.begin() as conn:
        cursor = PostgresCursorAdapter(conn)

        # 1. Conectividade & Links
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conectividade (
                id SERIAL PRIMARY KEY,
                unidade TEXT,
                nome_unidade TEXT,
                rua TEXT,
                bairro TEXT,
                estado TEXT,
                email_loja TEXT,
                tipo_unidade TEXT,
                tipo_link TEXT,
                operadora TEXT,
                circuito_afetado TEXT,
                impacto TEXT,
                protocolo TEXT,
                status TEXT,
                solicitacao_4g TEXT,
                protocolo_4g TEXT,
                status_chamado_4g TEXT,
                observacao_4g TEXT,
                observacoes_encerramento TEXT,
                turno TEXT,
                data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_atualizacao TIMESTAMP,
                data_resolucao TIMESTAMP
            )
        """)

        # 2. Lojas em GNET
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lojas_gnet (
                id SERIAL PRIMARY KEY,
                unidade TEXT,
                nome_unidade TEXT,
                estado TEXT,
                motivo TEXT,
                modelo_fortinet TEXT,
                ip_balcao TEXT,
                porta_switch TEXT,
                chamado_redes TEXT,
                observacao_dano TEXT,
                status TEXT,
                observacoes_encerramento TEXT,
                turno TEXT,
                data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_atualizacao TIMESTAMP,
                data_resolucao TIMESTAMP
            )
        """)

        # 3. Infraestrutura Local & Field
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS infra_local (
                id SERIAL PRIMARY KEY,
                tipo_problema TEXT,
                unidade TEXT,
                detalhes TEXT,
                protocolo TEXT,
                status TEXT,
                observacoes_encerramento TEXT,
                subtipo_field_service TEXT,
                modelo_equipamento TEXT,
                tratativa TEXT,
                turno TEXT,
                data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_atualizacao TIMESTAMP,
                data_resolucao TIMESTAMP
            )
        """)

        # 4. Alertas Sistêmicos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alertas_sistemicos (
                id SERIAL PRIMARY KEY,
                sistema TEXT,
                descricao_erro TEXT,
                chamado_glpi TEXT,
                vinculado_glpi TEXT,
                problema_glpi_id INTEGER,
                equipe_acionada TEXT,
                status TEXT,
                observacoes_encerramento TEXT,
                turno TEXT,
                data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_atualizacao TIMESTAMP,
                data_resolucao TIMESTAMP
            )
        """)

        # 5. Malha de Preços
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS malha_precos (
                id SERIAL PRIMARY KEY,
                fase_malha TEXT,
                acionamento TEXT,
                houve_incidente TEXT,
                houve_chamado TEXT,
                numero_chamado TEXT,
                time_acionado TEXT,
                analista_acionado TEXT,
                descricao_erro TEXT,
                status TEXT,
                observacoes_encerramento TEXT,
                turno TEXT,
                data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_atualizacao TIMESTAMP,
                data_resolucao TIMESTAMP
            )
        """)

        # 6. Lojas Pendentes de Base de Preço
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pendentes_base (
                id SERIAL PRIMARY KEY,
                unidade TEXT,
                motivo_obs TEXT,
                tratativa TEXT,
                status TEXT,
                observacoes_encerramento TEXT,
                turno TEXT,
                data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_atualizacao TIMESTAMP,
                data_resolucao TIMESTAMP
            )
        """)

        # 7. Flash & Gap de Vendas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS indicadores_vendas (
                id SERIAL PRIMARY KEY,
                tipo_indicador TEXT,
                acionamento TEXT,
                analista_acionado TEXT,
                descricao_erro TEXT,
                status TEXT,
                observacoes_encerramento TEXT,
                turno TEXT,
                data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_atualizacao TIMESTAMP,
                data_resolucao TIMESTAMP
            )
        """)

        # 8. Problemas GLPI (PRB)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS problemas_glpi (
                id SERIAL PRIMARY KEY,
                num_problema TEXT,
                titulo_erro TEXT,
                sistema_afetado TEXT,
                orientacao TEXT,
                status TEXT,
                observacoes_encerramento TEXT,
                turno TEXT,
                data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_atualizacao TIMESTAMP,
                time_responsavel TEXT,
                quantidade_chamados INTEGER NOT NULL DEFAULT 0
            )
        """)

        # 9. Métricas da Fila GLPI (Backlog)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fila_glpi_metrics (
                id SERIAL PRIMARY KEY,
                total_fila INTEGER,
                automaticos INTEGER,
                inauguracoes INTEGER,
                link1 INTEGER,
                link2 INTEGER,
                manuais INTEGER,
                turno TEXT,
                data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_atualizacao TIMESTAMP
            )
        """)

        # 10. Passagens de turno
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS passagens_turno (
                id SERIAL PRIMARY KEY,
                turno_origem TEXT NOT NULL,
                operador_origem TEXT NOT NULL,
                turno_destino TEXT NOT NULL,
                operador_destino TEXT NOT NULL,
                observacoes TEXT,
                pendencias_abertas INTEGER NOT NULL,
                data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_atualizacao TIMESTAMP
            )
        """)

        # 11. Status Movimentações
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS status_movimentacoes (
                id SERIAL PRIMARY KEY,
                tabela TEXT NOT NULL,
                registro_id INTEGER NOT NULL,
                status_anterior TEXT NOT NULL,
                status_novo TEXT NOT NULL,
                alterado_por TEXT NOT NULL,
                data_registro TIMESTAMP NOT NULL
            )
        """)

        # 12. Usuários
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('operador', 'admin')),
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                must_change_password INTEGER NOT NULL DEFAULT 1 CHECK (must_change_password IN (0, 1)),
                created_at TEXT NOT NULL
            )
        """)

        # 13. Tentativas de Login
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                email TEXT PRIMARY KEY,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TEXT
            )
        """)

        # Bloco de Migrations dinâmicas adaptadas e devidamente fechado
        migrations = {
            "conectividade": {
                "nome_unidade": "TEXT",
                "rua": "TEXT",
                "bairro": "TEXT",
                "estado": "TEXT",
                "email_loja": "TEXT",
                "tipo_unidade": "TEXT",
                "circuito_afetado": "TEXT",
                "solicitacao_4g": "TEXT",
                "protocolo_4g": "TEXT",
                "status_chamado_4g": "TEXT"
            }
        }

        for table, columns in migrations.items():
            add_missing_columns(cursor, table, columns)
