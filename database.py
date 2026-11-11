import os
import re
import sqlite3
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from pathlib import Path

# Váriavel obrigatória exigida pelo modulo authorization.py
DB_NAME = str(Path(__file__).resolve().with_name("central_comando.db"))

def _load_database_url():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        try:
            database_url = st.secrets["DATABASE_URL"]
        except Exception as error:
            raise RuntimeError(
                "Configure DATABASE_URL nas variáveis de ambiente ou em "
                ".streamlit/secrets.toml."
            ) from error

    url = make_url(database_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    if url.drivername != "postgresql+psycopg":
        raise RuntimeError("DATABASE_URL deve apontar para um PostgreSQL.")

    query = dict(url.query)
    query.setdefault("sslmode", "require")
    return url.set(query=query)


engine = create_engine(
    _load_database_url(),
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={"prepare_threshold": None},
)


def _prepare_query(query, params=()):
    if isinstance(params, dict):
        return text(query), params

    values = tuple(params or ())
    index = 0

    def replace_placeholder(_match):
        nonlocal index
        name = f"param_{index}"
        index += 1
        return f":{name}"

    statement = re.sub(r"\?", replace_placeholder, query)
    return text(statement), {
        f"param_{position}": value for position, value in enumerate(values)
    }


class DatabaseRow(tuple):
    def __new__(cls, values, keys):
        row = super().__new__(cls, values)
        row._keys = tuple(keys)
        return row

    def __getitem__(self, key):
        if isinstance(key, str):
            key = self._keys.index(key)
        return super().__getitem__(key)


class ResultAdapter:
    def __init__(self, result):
        self.result = result
        self.keys = tuple(result.keys())

    def fetchone(self):
        row = self.result.fetchone()
        return DatabaseRow(row, self.keys) if row is not None else None

    def fetchall(self):
        return [DatabaseRow(row, self.keys) for row in self.result.fetchall()]

    @property
    def rowcount(self):
        return self.result.rowcount


class PostgresCursorAdapter:
    """Adapta placeholders e linhas do PostgreSQL para as chamadas existentes."""

    def __init__(self, connection):
        self.connection = connection
        self.result = None

    def execute(self, query, params=()):
        statement, values = _prepare_query(query, params)
        self.result = ResultAdapter(self.connection.execute(statement, values))
        return self

    def executemany(self, query, parameter_rows):
        rows = list(parameter_rows)
        if not rows:
            return self
        statement, _ = _prepare_query(query, rows[0])
        names = [f"param_{index}" for index in range(len(rows[0]))]
        values = [dict(zip(names, row)) for row in rows]
        self.result = ResultAdapter(self.connection.execute(statement, values))
        return self

    def fetchone(self):
        return self.result.fetchone()

    def fetchall(self):
        return self.result.fetchall()


class PostgresConnectionAdapter:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=()):
        if query.strip().upper() in {"BEGIN", "BEGIN IMMEDIATE"}:
            if not self.connection.in_transaction():
                self.connection.begin()
            return None
        return PostgresCursorAdapter(self.connection).execute(query, params).result

    def cursor(self):
        return PostgresCursorAdapter(self.connection)

    def executemany(self, query, parameter_rows):
        return PostgresCursorAdapter(self.connection).executemany(
            query, parameter_rows
        )

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def connect():
    return PostgresConnectionAdapter(engine.connect())


def prepare_query(query, params=()):
    return _prepare_query(query, params)


def migrate_local_database():
    """Importa uma vez os dados do SQLite local sem removê-los da origem."""
    if not Path(DB_NAME).is_file():
        raise FileNotFoundError(f"Banco SQLite local não encontrado: {DB_NAME}")

    with sqlite3.connect(f"file:{DB_NAME}?mode=ro", uri=True) as source:
        source.row_factory = sqlite3.Row
        source_tables = [
            row[0]
            for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        ]

        with engine.begin() as destination:
            destination.execute(text(
                """CREATE TABLE IF NOT EXISTS migration_history (
                       migration_key TEXT PRIMARY KEY,
                       imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                   )"""
            ))
            completed = destination.execute(
                text("SELECT 1 FROM migration_history WHERE migration_key = :key"),
                {"key": "central_comando_sqlite_v1"},
            ).first()
            if completed:
                return {"already_migrated": True}

            destination_tables = {
                row[0]
                for row in destination.execute(text(
                    """SELECT table_name FROM information_schema.tables
                       WHERE table_schema = current_schema()
                         AND table_type = 'BASE TABLE'"""
                ))
            }
            imported = {}

            for table in source_tables:
                if table not in destination_tables:
                    continue

                source_columns = {
                    row[1]
                    for row in source.execute(f'PRAGMA table_info("{table}")')
                }
                destination_columns = {
                    row[0]
                    for row in destination.execute(
                        text("""SELECT column_name FROM information_schema.columns
                               WHERE table_schema = current_schema()
                                 AND table_name = :table"""),
                        {"table": table},
                    )
                }
                columns = sorted(source_columns & destination_columns)
                if not columns:
                    continue

                quote = lambda name: '"' + name.replace('"', '""') + '"'
                rows = source.execute(
                    f"SELECT {', '.join(quote(column) for column in columns)} "
                    f"FROM {quote(table)}"
                ).fetchall()
                if not rows:
                    continue

                placeholders = [f":value_{index}" for index in range(len(columns))]
                insert = text(
                    f"INSERT INTO {quote(table)} "
                    f"({', '.join(quote(column) for column in columns)}) "
                    f"VALUES ({', '.join(placeholders)}) ON CONFLICT DO NOTHING"
                )
                values = [
                    {
                        f"value_{index}": row[column]
                        for index, column in enumerate(columns)
                    }
                    for row in rows
                ]
                result = destination.execute(insert, values)
                imported[table] = result.rowcount

                if "id" in columns:
                    sequence = destination.execute(
                        text("SELECT pg_get_serial_sequence(:table_name, 'id')"),
                        {"table_name": table},
                    ).scalar_one_or_none()
                    if sequence:
                        destination.execute(
                            text(
                                f"SELECT setval(CAST(:sequence AS regclass), "
                                f"COALESCE((SELECT MAX(id) FROM {quote(table)}), 1), "
                                f"EXISTS (SELECT 1 FROM {quote(table)}))"
                            ),
                            {"sequence": sequence},
                        )

            destination.execute(
                text("INSERT INTO migration_history (migration_key) VALUES (:key)"),
                {"key": "central_comando_sqlite_v1"},
            )
            return {"already_migrated": False, "imported": imported}

def add_missing_columns(cursor, table, columns):
    # Consulta as colunas existentes usando a tabela padrão do Postgres
    query = f"""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = '{table.lower()}'
    """
    existing = {
        row[0].lower()
        for row in cursor.execute(query).fetchall()
        if row and row[0]
    }
    
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
