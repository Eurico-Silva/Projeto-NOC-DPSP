import sqlite3
from pathlib import Path

DB_NAME = str(Path(__file__).resolve().with_name("central_comando.db"))


def add_missing_columns(cursor, table, columns):
    existing = {
        row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for column, definition in columns.items():
        if column not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Conectividade & Links
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conectividade (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unidade TEXT,
            nome_unidade TEXT,
            rua TEXT,
            bairro TEXT,
            estado TEXT,
            tipo_unidade TEXT,
            tipo_link TEXT,
            operadora TEXT,
            circuito_afetado TEXT,
            impacto TEXT,
            protocolo TEXT,
            status TEXT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unidade TEXT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            num_problema TEXT,
            titulo_erro TEXT,
            sistema_afetado TEXT,
            orientacao TEXT,
            status TEXT,
            observacoes_encerramento TEXT,
            turno TEXT,
            data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_atualizacao TIMESTAMP,
            data_resolucao TIMESTAMP,
            time_responsavel TEXT,
            quantidade_chamados INTEGER NOT NULL DEFAULT 0
        )
    """)

    # 9. Métricas da Fila GLPI (Backlog)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fila_glpi_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS passagens_turno (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS status_movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tabela TEXT NOT NULL,
            registro_id INTEGER NOT NULL,
            status_anterior TEXT NOT NULL,
            status_novo TEXT NOT NULL,
            alterado_por TEXT NOT NULL,
            data_registro TIMESTAMP NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('operador', 'admin')),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            must_change_password INTEGER NOT NULL DEFAULT 1
                CHECK (must_change_password IN (0, 1)),
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            email TEXT PRIMARY KEY,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            locked_until TEXT
        )
    """)

    migrations = {
        "conectividade": {
            "nome_unidade": "TEXT",
            "rua": "TEXT",
            "bairro": "TEXT",
            "estado": "TEXT",
            "tipo_unidade": "TEXT",
            "circuito_afetado": "TEXT",
            "observacoes_encerramento": "TEXT",
            "data_atualizacao": "TIMESTAMP",
            "data_resolucao": "TIMESTAMP",
        },
        "lojas_gnet": {
            "chamado_redes": "TEXT",
            "observacao_dano": "TEXT",
            "observacoes_encerramento": "TEXT",
            "turno": "TEXT",
            "data_atualizacao": "TIMESTAMP",
            "data_resolucao": "TIMESTAMP",
        },
        "infra_local": {
            "protocolo": "TEXT",
            "observacoes_encerramento": "TEXT",
            "subtipo_field_service": "TEXT",
            "modelo_equipamento": "TEXT",
            "tratativa": "TEXT",
            "data_atualizacao": "TIMESTAMP",
            "data_resolucao": "TIMESTAMP",
        },
        "alertas_sistemicos": {
            "vinculado_glpi": "TEXT",
            "problema_glpi_id": "INTEGER",
            "observacoes_encerramento": "TEXT",
            "data_atualizacao": "TIMESTAMP",
            "data_resolucao": "TIMESTAMP",
        },
        "malha_precos": {
            "houve_incidente": "TEXT",
            "houve_chamado": "TEXT",
            "numero_chamado": "TEXT",
            "time_acionado": "TEXT",
            "observacoes_encerramento": "TEXT",
            "data_atualizacao": "TIMESTAMP",
            "data_resolucao": "TIMESTAMP",
        },
        "pendentes_base": {
            "observacoes_encerramento": "TEXT",
            "data_atualizacao": "TIMESTAMP",
            "data_resolucao": "TIMESTAMP",
        },
        "indicadores_vendas": {
            "observacoes_encerramento": "TEXT",
            "data_atualizacao": "TIMESTAMP",
            "data_resolucao": "TIMESTAMP",
        },
        "problemas_glpi": {
            "observacoes_encerramento": "TEXT",
            "turno": "TEXT",
            "data_atualizacao": "TIMESTAMP",
            "data_resolucao": "TIMESTAMP",
            "time_responsavel": "TEXT",
            "quantidade_chamados": "INTEGER NOT NULL DEFAULT 0",
        },
        "fila_glpi_metrics": {"data_atualizacao": "TIMESTAMP"},
        "passagens_turno": {"data_atualizacao": "TIMESTAMP"},
    }
    for table, columns in migrations.items():
        add_missing_columns(cursor, table, columns)

    for table in (
        "conectividade",
        "lojas_gnet",
        "infra_local",
        "alertas_sistemicos",
        "malha_precos",
        "pendentes_base",
        "indicadores_vendas",
        "problemas_glpi",
        "fila_glpi_metrics",
        "passagens_turno",
    ):
        cursor.execute(
            f"""UPDATE {table}
                SET data_atualizacao = COALESCE(data_atualizacao, data_registro)
                WHERE data_atualizacao IS NULL"""
        )

    cursor.execute(
        """UPDATE pendentes_base SET status = 'Em andamento'
           WHERE status = 'Em Andamento'"""
    )
    cursor.execute(
        """UPDATE problemas_glpi SET status = 'Em andamento'
           WHERE status = 'Ativo / Aberto'"""
    )

    cursor.execute(
        """CREATE INDEX IF NOT EXISTS idx_alertas_problema_glpi_id
           ON alertas_sistemicos (problema_glpi_id)"""
    )
    cursor.execute(
        """CREATE INDEX IF NOT EXISTS idx_status_movimentacoes_registro
           ON status_movimentacoes (tabela, registro_id, data_registro)"""
    )

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Banco de dados SQLite criado com sucesso!")