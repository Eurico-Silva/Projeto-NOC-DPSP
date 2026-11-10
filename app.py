import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo
from authorization import (
    authenticate_user,
    change_password,
    create_user,
    get_user_by_id,
    list_users,
    create_initial_admin,
    reset_user_password,
    update_user_access,
    user_count,
)
from database import DB_NAME, init_db
from store_catalog import (
    find_store,
    find_store_catalog_path,
    read_store_catalog,
    save_store_catalog,
)

# Inicializa o banco de dados
init_db()

st.set_page_config(
    page_title="Central de Comando DPSP",
    page_icon="🖥️",
    layout="wide"
)

st.markdown(
    """
    <style>
    .st-key-sidebar-logo {
        background: #FFFFFF;
        border-radius: 8px;
        margin-bottom: 1.1rem;
        padding: 0.45rem;
    }

    .st-key-sidebar-navigation h3 {
        color: #FFFFFF;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        margin: 0 0 0.55rem;
    }

    .st-key-active_module [role="radiogroup"] {
        gap: 0.25rem;
    }

    .st-key-active_module [role="radiogroup"] label {
        box-sizing: border-box;
        width: 100%;
        min-height: 2.45rem;
        margin: 0;
        padding: 0.45rem 0.6rem;
        border: 0;
        border-left: 3px solid transparent;
        border-radius: 6px;
        color: #F4F6FA;
        font-size: 0.84rem;
    }

    .st-key-active_module [role="radiogroup"] label:has(input[type="radio"]:checked) {
        background-color: #405071;
        border-left-color: #8AD5FC;
    }

    .st-key-active_module [role="radiogroup"] label:hover {
        background-color: #394967;
    }

    .st-key-active_module [role="radiogroup"] label:focus-within {
        outline: 2px solid #8AD5FC;
        outline-offset: 1px;
    }

    .st-key-active_module [role="radiogroup"] input[type="radio"] {
        position: absolute;
        width: 1px;
        height: 1px;
        opacity: 0;
    }

    .st-key-active_module [role="radiogroup"] label p {
        color: inherit;
        line-height: 1.25;
    }

    [data-testid="stMain"] {
        background-color: #E6F3FE;
    }

    [data-testid="stMain"] .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    [data-testid="stMain"] h1,
    [data-testid="stMain"] h2,
    [data-testid="stMain"] h3 {
        color: #2E3B5B;
        letter-spacing: -0.02em;
    }

    [data-testid="stMain"] [data-testid="stMetric"],
    [data-testid="stMain"] [data-testid="stForm"],
    [data-testid="stMain"] [data-testid="stExpander"],
    [data-testid="stMain"] [data-testid="stDataFrame"] {
        background-color: #FFFFFF;
        border: 1px solid #D5E4F0;
        border-radius: 12px;
        box-shadow: 0 3px 12px rgba(46, 59, 91, 0.07);
    }

    [data-testid="stMain"] [data-testid="stMetric"] {
        padding: 0.9rem 1rem;
    }

    [data-testid="stMain"] [data-testid="stForm"] {
        padding: 1rem;
    }

    [data-testid="stMain"] [data-testid="stExpander"] {
        overflow: hidden;
    }

    [data-testid="stMain"] button[kind="primary"] {
        font-weight: 600;
    }

    @media (max-width: 640px) {
        [data-testid="stMain"] .block-container {
            padding-top: 1.25rem;
            padding-bottom: 1.25rem;
        }

        [data-testid="stMain"] h1 {
            font-size: 1.8rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")
STATUS_OPTIONS = {
    "conectividade": ["Pendente", "Em andamento", "Resolvido"],
    "lojas_gnet": [
        "Aguardando solução do time de redes",
        "Em avaliação pelo time de redes",
        "Resolvido",
    ],
    "infra_local": ["Pendente", "Em andamento", "Resolvido"],
    "alertas_sistemicos": [
        "Pendente",
        "Em andamento",
        "Resolvido",
        "Relacionado a problema",
    ],
    "malha_precos": [
        "Pendente",
        "Em andamento",
        "Resolvido após acionamento",
    ],
    "pendentes_base": ["Pendente", "Em andamento", "Resolvido"],
    "indicadores_vendas": ["Pendente", "Em andamento", "Resolvido"],
    "problemas_glpi": [
        "Em andamento",
        "Resolvido",
        "Fechado sem solução definitiva",
        "Problema em análise com time/fornecedor",
    ],
}
RESOLVED_STATUSES = {
    "Resolvido",
    "Resolvido após acionamento",
    "Fechado sem solução definitiva",
}
RESOLUTION_NOTES_REQUIRED = {"infra_local"}
CONNECTIVITY_AUTOFILL_KEYS = {
    "name": "connectivity_store_name",
    "address": "connectivity_store_address",
    "district": "connectivity_store_district",
    "state": "connectivity_store_state",
    "email": "connectivity_store_email",
}


@st.cache_data(show_spinner=False)
def load_store_catalog(file_content):
    return read_store_catalog(file_content)


def autofill_connectivity_store(catalog, columns):
    store = find_store(
        catalog,
        columns,
        st.session_state.get("connectivity_unit", ""),
    )
    for field, key in CONNECTIVITY_AUTOFILL_KEYS.items():
        st.session_state[key] = store[field] if store else ""


def autofill_gnet_store(catalog, columns):
    store = find_store(
        catalog,
        columns,
        st.session_state.get("gnet_unit", ""),
    )
    st.session_state["gnet_store_name"] = store["name"] if store else ""
    st.session_state["gnet_store_state"] = store["state"] if store else ""


def render_login():
    st.title("Central de Comando DPSP")
    st.subheader("Entrar")
    with st.form("login_form"):
        login_email = st.text_input("E-mail")
        login_password = st.text_input("Senha", type="password")
        login_submitted = st.form_submit_button("Entrar")
    if login_submitted:
        account = authenticate_user(login_email, login_password)
        if account:
            st.session_state["auth_user_id"] = account["id"]
            st.rerun()
        st.error("E-mail ou senha inválidos, ou conta temporariamente bloqueada.")


if user_count() == 0:
    st.title("Configuração inicial — Administrador")
    st.warning(
        "Crie a primeira conta administradora. Faça esta configuração apenas "
        "em um ambiente privado e confiável."
    )
    with st.form("initial_admin_form"):
        initial_name = st.text_input("Nome completo")
        initial_email = st.text_input("E-mail")
        initial_password = st.text_input("Senha (mínimo 12 caracteres)", type="password")
        initial_password_confirmation = st.text_input(
            "Confirme a senha",
            type="password",
        )
        initial_admin_submitted = st.form_submit_button("Criar administrador")
    if initial_admin_submitted:
        if initial_password != initial_password_confirmation:
            st.error("As senhas não coincidem.")
        else:
            try:
                initial_admin_id = create_initial_admin(
                    initial_email,
                    initial_name,
                    initial_password,
                )
            except ValueError as error:
                st.error(str(error))
            else:
                st.session_state["auth_user_id"] = initial_admin_id
                st.rerun()
    st.stop()

authenticated_user = None
session_user_id = st.session_state.get("auth_user_id")
if session_user_id is not None:
    authenticated_user = get_user_by_id(session_user_id)
    if authenticated_user is None or not authenticated_user["is_active"]:
        st.session_state.pop("auth_user_id", None)
        authenticated_user = None

if authenticated_user is None:
    render_login()
    st.stop()

user_id = authenticated_user["id"]
current_user = authenticated_user["email"]
is_admin = authenticated_user["role"] == "admin"
is_logged_in = True

if authenticated_user["must_change_password"]:
    st.title("Troca obrigatória de senha")
    st.info("Defina uma nova senha antes de continuar para a plataforma.")
    with st.form("first_password_change_form"):
        new_password = st.text_input("Nova senha", type="password")
        confirm_password = st.text_input("Confirme a nova senha", type="password")
        password_submitted = st.form_submit_button("Salvar nova senha")
    if password_submitted:
        if new_password != confirm_password:
            st.error("As senhas não coincidem.")
        else:
            try:
                change_password(user_id, new_password)
            except (PermissionError, ValueError) as error:
                st.error(str(error))
            else:
                st.success("Senha atualizada.")
                st.rerun()
    st.stop()


def now_utc_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def as_brasilia_timestamp(value):
    if value is None or pd.isna(value) or value == "":
        return None
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(BRASILIA_TZ)


def display_timestamp(value):
    timestamp = as_brasilia_timestamp(value)
    return timestamp.strftime("%d/%m/%Y %H:%M:%S") if timestamp else "—"


def display_duration(start_value, end_value=None, is_resolved=False):
    started = as_brasilia_timestamp(start_value)
    if started is None:
        return "Indisponível"
    has_end = (
        end_value is not None
        and not pd.isna(end_value)
        and end_value != ""
    )
    if is_resolved and not has_end:
        return "Indisponível (registro legado)"
    ended = (
        as_brasilia_timestamp(end_value)
        if has_end
        else datetime.now(BRASILIA_TZ)
    )
    elapsed_minutes = max(0, int((ended - started).total_seconds() // 60))
    days, remaining_minutes = divmod(elapsed_minutes, 24 * 60)
    hours, minutes = divmod(remaining_minutes, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}min")
    return " ".join(parts)


def add_temporal_display_columns(records):
    display = records.copy()
    if display.empty:
        return display
    display["Criado (Brasília)"] = display["data_registro"].map(display_timestamp)
    display["Atualizado (Brasília)"] = display["data_atualizacao"].map(
        display_timestamp
    )
    display["Tempo em tratativa"] = display.apply(
        lambda row: display_duration(
            row["data_registro"],
            row.get("data_resolucao"),
            row["status"] in RESOLVED_STATUSES,
        ),
        axis=1,
    )
    return display.drop(
        columns=["data_registro", "data_atualizacao", "data_resolucao"],
        errors="ignore",
    )


def save_status_changes(table, previous, edited):
    allowed_statuses = STATUS_OPTIONS[table]
    changes = []
    actor = get_user_by_id(user_id)
    if actor is None or not actor["is_active"]:
        raise PermissionError("A conta não está ativa.")
    actor_is_admin = actor["role"] == "admin"
    previous_rows = previous.set_index("id")
    edited_rows = edited.set_index("id")
    for record_id, edited_row in edited_rows.iterrows():
        previous_row = previous_rows.loc[record_id]
        old_status = previous_row["status"]
        new_status = edited_row["status"]
        old_notes = (
            previous_row["observacoes_encerramento"]
            if "observacoes_encerramento" in previous_rows.columns
            else ""
        )
        new_notes = (
            edited_row["observacoes_encerramento"]
            if "observacoes_encerramento" in edited_rows.columns
            else old_notes
        )
        old_notes = "" if pd.isna(old_notes) else str(old_notes).strip()
        new_notes = "" if pd.isna(new_notes) else str(new_notes).strip()
        status_changed = old_status != new_status
        notes_changed = (
            table in RESOLUTION_NOTES_REQUIRED and old_notes != new_notes
        )
        if not status_changed and not notes_changed:
            continue
        if new_status not in allowed_statuses:
            raise ValueError("O status selecionado não é válido para esta categoria.")
        if (
            status_changed
            and old_status in RESOLVED_STATUSES
            and new_status not in RESOLVED_STATUSES
            and not actor_is_admin
        ):
            raise PermissionError("Somente um administrador pode reabrir um registro.")
        if (
            status_changed
            and new_status in RESOLVED_STATUSES
            and table in RESOLUTION_NOTES_REQUIRED
            and not new_notes
        ):
            raise ValueError(
                "Informe as notas de resolução antes de concluir o registro."
            )
        changes.append(
            (
                int(record_id),
                old_status,
                new_status,
                new_notes,
                status_changed,
            )
        )

    if not changes:
        return 0

    updated_at = now_utc_iso()
    connection = sqlite3.connect(DB_NAME)
    try:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.cursor()
        actor = cursor.execute(
            "SELECT role, is_active FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if actor is None or not actor[1]:
            raise PermissionError("A conta não está ativa.")
        actor_is_admin = actor[0] == "admin"
        if not actor_is_admin and any(
            status_changed
            and old_status in RESOLVED_STATUSES
            and new_status not in RESOLVED_STATUSES
            for _, old_status, new_status, _, status_changed in changes
        ):
            raise PermissionError("Somente um administrador pode reabrir um registro.")
        for record_id, old_status, new_status, notes, status_changed in changes:
            if status_changed:
                resolution_time = (
                    updated_at if new_status in RESOLVED_STATUSES else None
                )
                if table in RESOLUTION_NOTES_REQUIRED:
                    cursor.execute(
                        f"""UPDATE {table}
                            SET status = ?, observacoes_encerramento = ?,
                                data_atualizacao = ?, data_resolucao = ?
                            WHERE id = ?""",
                        (
                            new_status,
                            notes,
                            updated_at,
                            resolution_time,
                            record_id,
                        ),
                    )
                else:
                    cursor.execute(
                        f"""UPDATE {table}
                            SET status = ?, data_atualizacao = ?, data_resolucao = ?
                            WHERE id = ?""",
                        (new_status, updated_at, resolution_time, record_id),
                    )
                cursor.execute(
                    """INSERT INTO status_movimentacoes
                       (tabela, registro_id, status_anterior, status_novo,
                        alterado_por, data_registro)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        table,
                        record_id,
                        old_status,
                        new_status,
                        current_user,
                        updated_at,
                    ),
                )
            else:
                cursor.execute(
                    f"""UPDATE {table}
                        SET observacoes_encerramento = ?, data_atualizacao = ?
                        WHERE id = ?""",
                    (notes, updated_at, record_id),
                )
        connection.commit()
    finally:
        connection.close()
    return len(changes)


def close_record(table, record_id, notes):
    status = CLOSE_STATUSES[table]
    changed_at = now_utc_iso()
    connection = sqlite3.connect(DB_NAME)
    try:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.cursor()
        actor = cursor.execute(
            "SELECT is_active FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if actor is None or not actor[0]:
            raise PermissionError("A conta não está ativa.")
        current = cursor.execute(
            f"SELECT status FROM {table} WHERE id = ?",
            (record_id,),
        ).fetchone()
        if current is None:
            raise ValueError("O registro selecionado não existe mais.")
        old_status = current[0]
        if old_status in RESOLVED_STATUSES:
            raise ValueError("O registro já está resolvido.")
        cursor.execute(
            f"""UPDATE {table}
                SET status = ?, observacoes_encerramento = ?,
                    data_atualizacao = ?, data_resolucao = ?
                WHERE id = ?""",
            (status, notes.strip(), changed_at, changed_at, record_id),
        )
        cursor.execute(
            """INSERT INTO status_movimentacoes
               (tabela, registro_id, status_anterior, status_novo,
                alterado_por, data_registro)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (table, record_id, old_status, status, current_user, changed_at),
        )
        connection.commit()
    finally:
        connection.close()


@st.fragment(run_every="1m")
def render_status_manager(table, records, alt):
    if records.empty:
        st.info("Nenhum registro encontrado.")
        return

    with st.expander("Histórico de registros e atualização de status", expanded=True):
        st.caption(
            "Horários no fuso de Brasília; o tempo em tratativa é atualizado a cada minuto."
        )
        open_records = records[
            ~records["status"].isin(RESOLVED_STATUSES)
        ].copy()
        closed_records = records[
            records["status"].isin(RESOLVED_STATUSES)
        ].copy()

        editable_records = records.copy() if is_admin else open_records.copy()
        if not editable_records.empty:
            editor_records = add_temporal_display_columns(editable_records)
            disabled_columns = [
                column
                for column in editor_records.columns
                if column != "status"
                and not (
                    table in RESOLUTION_NOTES_REQUIRED
                    and column == "observacoes_encerramento"
                )
            ]
            column_config = {
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    options=STATUS_OPTIONS[table],
                    required=True,
                )
            }
            if table in RESOLUTION_NOTES_REQUIRED:
                column_config["observacoes_encerramento"] = (
                    st.column_config.TextColumn("Notas de resolução")
                )
            edited_records = st.data_editor(
                editor_records,
                key=f"status_editor_{table}",
                num_rows="fixed",
                hide_index=True,
                disabled=disabled_columns,
                column_config=column_config,
                width="stretch",
                alt=alt,
            )
            if st.button(
                "Salvar alterações de status",
                key=f"save_status_{table}",
            ):
                try:
                    changed_count = save_status_changes(
                        table, editable_records, edited_records
                    )
                except (PermissionError, ValueError) as error:
                    st.error(str(error))
                else:
                    if changed_count:
                        rerun_with_success(
                            f"{changed_count} registro(s) atualizado(s); "
                            "movimentação registrada quando houve mudança de status."
                        )
                    st.info("Nenhum status foi alterado.")
        else:
            st.info("Não há registros abertos para atualizar.")

        if not closed_records.empty and not is_admin:
            st.markdown("#### Registros resolvidos (somente leitura)")
            st.dataframe(
                add_temporal_display_columns(closed_records),
                width="stretch",
                hide_index=True,
                alt="Registros resolvidos, bloqueados para reabertura de usuários",
            )

        movements = load_data(
            """SELECT registro_id AS ID, status_anterior AS "Status anterior",
                      status_novo AS "Status novo", alterado_por AS Responsável,
                      data_registro AS data_registro
               FROM status_movimentacoes
               WHERE tabela = ?
               ORDER BY id DESC LIMIT 50""",
            (table,),
        )
        if not movements.empty:
            movements["Data/hora (Brasília)"] = movements["data_registro"].map(
                display_timestamp
            )
            st.markdown("#### Movimentações recentes")
            st.dataframe(
                movements.drop(columns=["data_registro"]),
                width="stretch",
                hide_index=True,
                alt="Histórico recente de alterações de status",
            )


def run_query(query, params=()):
    conn = sqlite3.connect(DB_NAME)
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
    finally:
        conn.close()


def run_many(query, parameter_rows):
    conn = sqlite3.connect(DB_NAME)
    try:
        conn.execute("BEGIN")
        conn.executemany(query, parameter_rows)
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def rerun_with_success(message):
    for key in list(st.session_state):
        if key.startswith("status_editor_"):
            del st.session_state[key]
    st.session_state["save_notice"] = message
    st.rerun()


def load_data(query, params=()):
    conn = sqlite3.connect(DB_NAME)
    try:
        return pd.read_sql(query, conn, params=params)
    finally:
        conn.close()

PENDENCIAS_ABERTAS_QUERY = """
    SELECT 'Conectividade' AS categoria, id,
           CASE WHEN nome_unidade IS NULL OR nome_unidade = ''
                THEN unidade ELSE unidade || ' - ' || nome_unidade END
                || ' — ' || COALESCE(tipo_link, '') || ' / ' || COALESCE(circuito_afetado, '') AS resumo,
           status, turno, data_registro, data_atualizacao, data_resolucao,
           CASE WHEN impacto = 'Link inoperante' OR impacto LIKE '%Inoperância Total%'
                THEN 'CRÍTICO / P1'
                ELSE COALESCE(impacto, '') END AS criticidade,
           'conectividade' AS tabela
    FROM conectividade WHERE status != 'Resolvido'
    UNION ALL
    SELECT 'Lojas em GNET', id, unidade || ' - ' || COALESCE(motivo, ''),
           status, turno, data_registro, data_atualizacao, data_resolucao, '', 'lojas_gnet'
    FROM lojas_gnet WHERE status != 'Resolvido'
    UNION ALL
    SELECT 'Infra / Field', id, unidade || ' - ' || COALESCE(tipo_problema, ''),
           status, turno, data_registro, data_atualizacao, data_resolucao,
           CASE WHEN tipo_problema LIKE 'Loja Isolada%' THEN 'CRÍTICO / P1' ELSE '' END,
           'infra_local'
    FROM infra_local WHERE status != 'Resolvido'
    UNION ALL
    SELECT 'Alertas Sistêmicos', id, sistema || ' - ' || COALESCE(descricao_erro, ''),
           status, turno, data_registro, data_atualizacao, data_resolucao, '', 'alertas_sistemicos'
    FROM alertas_sistemicos WHERE status != 'Resolvido'
    UNION ALL
    SELECT 'Malha de Preços', id, fase_malha || ' - ' || COALESCE(descricao_erro, ''),
           status, turno, data_registro, data_atualizacao, data_resolucao, '', 'malha_precos'
    FROM malha_precos WHERE status NOT IN ('Resolvido', 'Resolvido após acionamento')
    UNION ALL
    SELECT 'Pendentes de Base', id, unidade || ' - ' || COALESCE(motivo_obs, ''),
           status, turno, data_registro, data_atualizacao, data_resolucao, '', 'pendentes_base'
    FROM pendentes_base WHERE status != 'Resolvido'
    UNION ALL
    SELECT 'Flash & Gap', id, tipo_indicador || ' - ' || COALESCE(descricao_erro, ''),
           status, turno, data_registro, data_atualizacao, data_resolucao, '', 'indicadores_vendas'
    FROM indicadores_vendas WHERE status != 'Resolvido'
    ORDER BY data_registro DESC
"""

CLOSE_STATUSES = {
    "conectividade": "Resolvido",
    "lojas_gnet": "Resolvido",
    "infra_local": "Resolvido",
    "alertas_sistemicos": "Resolvido",
    "malha_precos": "Resolvido após acionamento",
    "pendentes_base": "Resolvido",
    "indicadores_vendas": "Resolvido",
    "problemas_glpi": "Encerrado",
}

def load_open_items():
    return load_data(PENDENCIAS_ABERTAS_QUERY)


HISTORICO_QUERY = """
    SELECT data_registro, categoria, unidade, resumo, status, turno,
           protocolo, encerramento, criticidade
    FROM (
        SELECT data_registro, 'Conectividade' AS categoria,
               CASE WHEN nome_unidade IS NULL OR nome_unidade = ''
                    THEN unidade ELSE unidade || ' - ' || nome_unidade END
                   || CASE WHEN rua IS NOT NULL AND rua != '' THEN ' / ' || rua ELSE '' END
                   || CASE WHEN bairro IS NOT NULL AND bairro != '' THEN ' / ' || bairro ELSE '' END
                   || CASE WHEN estado IS NOT NULL AND estado != '' THEN ' / ' || estado ELSE '' END AS unidade,
               COALESCE(tipo_link, '') || ' / ' || COALESCE(operadora, '') || ' / '
                   || COALESCE(circuito_afetado, '') || ' / ' || COALESCE(impacto, '') AS resumo,
               status, turno, protocolo, observacoes_encerramento AS encerramento,
               CASE WHEN impacto = 'Link inoperante' OR impacto LIKE '%Inoperância Total%'
                    THEN 'CRÍTICO / P1' ELSE '' END AS criticidade
        FROM conectividade
        UNION ALL
        SELECT data_registro, 'Lojas em GNET', unidade,
               COALESCE(motivo, '') || ' / Dano: ' || COALESCE(observacao_dano, '')
                   || ' / Fortinet: ' || COALESCE(modelo_fortinet, '')
                   || ' / IP: ' || COALESCE(ip_balcao, '') || ' / Porta: ' || COALESCE(porta_switch, '')
                   || ' / Chamado de redes: ' || COALESCE(chamado_redes, ''),
               status, turno, chamado_redes, observacoes_encerramento, ''
        FROM lojas_gnet
        UNION ALL
        SELECT data_registro, 'Infra / Field', unidade,
               COALESCE(tipo_problema, '')
                   || CASE WHEN subtipo_field_service IS NOT NULL AND subtipo_field_service != ''
                           THEN ' / ' || subtipo_field_service ELSE '' END
                   || CASE WHEN modelo_equipamento IS NOT NULL AND modelo_equipamento != ''
                           THEN ' / Equipamento: ' || modelo_equipamento ELSE '' END
                   || ' / Descrição: ' || COALESCE(detalhes, '')
                   || ' / Tratativa: ' || COALESCE(tratativa, ''),
               status, turno, protocolo, observacoes_encerramento,
               CASE WHEN tipo_problema LIKE 'Loja Isolada%' THEN 'CRÍTICO / P1' ELSE '' END
        FROM infra_local
        UNION ALL
        SELECT a.data_registro, 'Alertas Sistêmicos', a.sistema,
               a.descricao_erro || CASE WHEN p.num_problema IS NOT NULL
                   THEN ' / Problema relacionado: ' || p.num_problema ELSE '' END,
               a.status, a.turno, a.chamado_glpi, a.observacoes_encerramento, ''
        FROM alertas_sistemicos AS a
        LEFT JOIN problemas_glpi AS p ON p.id = a.problema_glpi_id
        UNION ALL
        SELECT data_registro, 'Malha de Preços', fase_malha,
               'Houve incidente: ' || COALESCE(houve_incidente, acionamento, '')
                   || ' / Chamado aberto: ' || COALESCE(houve_chamado, '')
                   || CASE WHEN numero_chamado IS NOT NULL AND numero_chamado != ''
                           THEN ' / Chamado: ' || numero_chamado ELSE '' END
                   || CASE WHEN time_acionado IS NOT NULL AND time_acionado != ''
                           THEN ' / Time: ' || time_acionado ELSE '' END
                   || CASE WHEN analista_acionado IS NOT NULL AND analista_acionado != ''
                           THEN ' / Analista: ' || analista_acionado ELSE '' END
                   || ' / Observação: ' || COALESCE(descricao_erro, ''),
               status, turno, '', observacoes_encerramento, ''
        FROM malha_precos
        UNION ALL
        SELECT data_registro, 'Pendentes de Base', unidade,
               COALESCE(motivo_obs, '') || ' / Tratativa: ' || COALESCE(tratativa, ''),
               status, turno, '', observacoes_encerramento, ''
        FROM pendentes_base
        UNION ALL
        SELECT data_registro, 'Flash & Gap', tipo_indicador,
               'Analista: ' || COALESCE(analista_acionado, '')
                   || ' / ' || COALESCE(descricao_erro, ''),
               status, turno, '', observacoes_encerramento, ''
        FROM indicadores_vendas
        UNION ALL
        SELECT data_registro, 'Problemas GLPI', num_problema,
               COALESCE(titulo_erro, '')
                   || ' / Time: ' || COALESCE(time_responsavel, '')
                   || ' / Sistema: ' || COALESCE(sistema_afetado, '')
                   || ' / Chamados vinculados: ' || COALESCE(quantidade_chamados, 0)
                   || ' / Descrição: ' || COALESCE(orientacao, ''),
               status, turno, num_problema, observacoes_encerramento, ''
        FROM problemas_glpi
        UNION ALL
        SELECT data_registro, 'Passagem de Turno',
               turno_origem || ' → ' || turno_destino,
               'Entregue por ' || operador_origem || ' para ' || operador_destino
                   || ' / Pendências abertas: ' || pendencias_abertas
                   || ' / ' || COALESCE(observacoes, ''),
               'Registrada', turno_origem, '', '', ''
        FROM passagens_turno
        UNION ALL
        SELECT data_registro, 'Fila GLPI', '',
               'Total: ' || total_fila || ' / Automáticos: ' || automaticos
                   || ' / Inaugurações: ' || inauguracoes || ' / Link 1: ' || link1
                   || ' / Link 2: ' || link2 || ' / Manuais: ' || manuais,
               'Snapshot', turno, '', '', ''
        FROM fila_glpi_metrics
    ) AS historico
    WHERE DATE(data_registro, '-3 hours') BETWEEN ? AND ?
      AND (? = 'Todos' OR turno = ?)
    ORDER BY data_registro DESC
"""

STATUS_ENCERRADOS = {*RESOLVED_STATUSES, "Encerrado"}
CATEGORIAS_NAO_OPERACIONAIS = {"Fila GLPI", "Passagem de Turno", "Problemas GLPI"}


def load_history(data_inicio, data_fim, turno="Todos"):
    history = load_data(
        HISTORICO_QUERY,
        (str(data_inicio), str(data_fim), turno, turno),
    )
    if not history.empty:
        history["data_registro"] = history["data_registro"].map(display_timestamp)
    return history


def build_executive_report_html(data_referencia, turno, indicadores, links, gnet, fila, malha, ocorrencias_criticas):
    cards = "".join(
        f"<article><span>{escape(label)}</span><strong>{escape(str(value))}</strong></article>"
        for label, value in indicadores.items()
    )

    def table_or_empty(dataframe, message):
        if dataframe.empty:
            return f"<p>{escape(message)}</p>"
        return dataframe.to_html(index=False, border=0, escape=True, classes="report-table")

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dashboard operacional — {escape(str(data_referencia))}</title>
  <style>
    body {{ font: 14px/1.5 Arial, sans-serif; color: #2E3B5B; background: #E6F3FE; margin: 32px auto; max-width: 1100px; padding: 0 24px; }}
    header {{ border-bottom: 3px solid #387FEF; margin-bottom: 24px; padding-bottom: 16px; }}
    h1 {{ margin: 0 0 6px; font-size: 26px; }} h2 {{ margin-top: 28px; font-size: 17px; }}
    .muted {{ color: #52637a; }} .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }}
    article {{ background: #FFFFFF; border: 1px solid #D5E4F0; border-radius: 12px; box-shadow: 0 3px 12px rgba(46, 59, 91, 0.07); padding: 14px; }}
    article span {{ display: block; color: #52637a; font-size: 12px; }} article strong {{ display: block; font-size: 24px; margin-top: 6px; }}
    .report-table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
    .report-table th {{ background: #E6F3FE; text-align: left; }}
    .report-table th, .report-table td {{ border-bottom: 1px solid #D5E4F0; padding: 8px; vertical-align: top; }}
    @media print {{ body {{ margin: 12mm; max-width: none; }} article {{ break-inside: avoid; }} }}
    @media (max-width: 700px) {{ .cards {{ grid-template-columns: repeat(2, 1fr); }} }}
  </style>
</head>
<body>
  <header>
    <h1>Dashboard operacional — Central de Comando DPSP</h1>
    <div class="muted">Data: {escape(str(data_referencia))} · Turno: {escape(turno)} · Gerado em {escape(str(datetime.now(BRASILIA_TZ).date()))}</div>
  </header>
  <section class="cards">{cards}</section>
  <h2>Incidentes críticos em aberto</h2>
  {table_or_empty(ocorrencias_criticas, "Nenhum incidente crítico em aberto no período.")}
  <h2>Quedas de link por operadora</h2>
  {table_or_empty(links, "Nenhuma ocorrência de conectividade no período.")}
  <h2>Lojas em GNET</h2>
  {table_or_empty(gnet, "Nenhum registro de GNET no período.")}
  <h2>Fila GLPI</h2>
  {table_or_empty(fila, "Nenhuma medição de fila GLPI no período.")}
  <h2>Malha de preços e acionamentos</h2>
  {table_or_empty(malha, "Nenhum registro de malha de preços no período.")}
</body>
</html>"""


# --- NAVEGAÇÃO E BARRA LATERAL ---
tab_titles = [
    "🔄 Passagem de Turno",
    "🔗 Conectividade",
    "🛡️ Lojas em GNET",
    "⚡ Field Service",
    "🚨 Alertas Sistêmicos",
    "💰 Malha de Preços",
    "📦 Lojas Pendente Base de Preço",
    "📊 Flash e Gap de Vendas",
    "📌 Problemas GLPI",
    "📈 Fila GLPI",
    "📊 Dashboard Operacional",
    "🗂️ Relatórios / Histórico",
]
if is_admin:
    tab_titles.append("👥 Gestão de Usuários")
module_icon_names = [
    "swap_horiz",
    "lan",
    "shield",
    "bolt",
    "notifications_active",
    "sell",
    "inventory_2",
    "show_chart",
    "push_pin",
    "trending_up",
    "dashboard",
    "history",
    "manage_accounts",
]


def format_module_label(module_title):
    module_index = tab_titles.index(module_title)
    module_name = module_title.split(maxsplit=1)[1]
    return f":material/{module_icon_names[module_index]}: {module_name}"


with st.sidebar.container(key="sidebar-logo", horizontal_alignment="center"):
    st.image(
        str(Path(__file__).parent / "assets" / "logo-grupo-dpsp.png"),
        width=137,
        alt="Logo do Grupo DPSP",
    )
with st.sidebar.container(key="sidebar-navigation"):
    st.markdown("### Módulos")
    selected_module = st.radio(
        "Navegação",
        tab_titles,
        format_func=format_module_label,
        label_visibility="collapsed",
        key="active_module",
    )
hidden_module_rules = "\n".join(
    f".st-key-module-body-{index} {{ display: none !important; }}"
    for index, title in enumerate(tab_titles)
    if title != selected_module
)
st.markdown(f"<style>{hidden_module_rules}</style>", unsafe_allow_html=True)

turnos = ["Manhã", "Tarde", "Noite", "Madrugada"]
turno_atual = st.sidebar.selectbox("Turno Atual", turnos)
responsavel = st.sidebar.text_input("Operador Responsável")
st.sidebar.caption(
    f"Conta: {authenticated_user['full_name']} · {current_user}"
    + (" · Administrador" if is_admin else " · Operador")
)
with st.sidebar.expander("Alterar minha senha"):
    with st.form("change_password_form"):
        current_password = st.text_input("Senha atual", type="password")
        new_password = st.text_input("Nova senha", type="password")
        confirm_password = st.text_input("Confirme a nova senha", type="password")
        change_password_submitted = st.form_submit_button("Atualizar senha")
    if change_password_submitted:
        if new_password != confirm_password:
            st.error("As senhas não coincidem.")
        else:
            try:
                change_password(user_id, new_password, current_password)
            except (PermissionError, ValueError) as error:
                st.error(str(error))
            else:
                st.success("Senha atualizada.")
                st.rerun()

if st.sidebar.button("Sair da conta"):
    st.session_state.pop("auth_user_id", None)
    st.rerun()

st.title("Central de Comando DPSP")
st.markdown(f"**Turno Selecionado:** {turno_atual} | **Responsável:** {responsavel if responsavel else 'Não informado'}")
mensagem_salva = st.session_state.pop("save_notice", None)
if mensagem_salva:
    st.success(mensagem_salva)

# PASSAGEM DE TURNO
with st.container(key="module-body-0"):
    st.subheader("Resumo operacional e transferência de pendências")
    pendencias = load_open_items()
    total_pendencias = len(pendencias)

    metricas = st.columns(3)
    metricas[0].metric("Pendências abertas", total_pendencias)
    metricas[1].metric("Turno de origem", turno_atual)
    metricas[2].metric("Operador de origem", responsavel or "Não informado")

    st.markdown("### Pendências que precisam ser acompanhadas")
    if pendencias.empty:
        st.success("Nenhuma pendência aberta no momento.")
    else:
        pendencias_formatadas = add_temporal_display_columns(
            pendencias.drop(columns=["tabela"])
        )
        pendencias_stylized = pendencias_formatadas.style.map(
            lambda valor: (
                "background-color: #FCE4E6; color: #A43F47; "
                "border-left: 3px solid #E75E65; font-weight: bold"
                if valor == "CRÍTICO / P1"
                else (
                    "background-color: #FBF4D6; color: #655728; border-left: 3px solid #E2CE76"
                    if valor
                    else ""
                )
            ),
            subset=["criticidade"],
        )
        st.dataframe(
            pendencias_stylized,
            width="stretch",
            hide_index=True,
        )
        st.download_button(
            "Baixar pendências em CSV",
            data=pendencias_formatadas.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"pendencias_turno_{datetime.now(BRASILIA_TZ).date().isoformat()}.csv",
            mime="text/csv",
        )

        if is_logged_in:
            st.markdown("### Encerrar uma ocorrência")
            opcoes_pendencias = [
                f"{row.categoria} #{row.id} — {row.resumo}"
                for row in pendencias.itertuples(index=False)
            ]
            with st.form("form_encerrar_ocorrencia"):
                item_selecionado = st.selectbox("Ocorrência", opcoes_pendencias)
                notas_encerramento = st.text_area(
                    "Notas de encerramento",
                    placeholder="Descreva a normalização, validação ou solução aplicada.",
                )
                encerrar_ocorrencia = st.form_submit_button("Encerrar ocorrência")
                if encerrar_ocorrencia:
                    if not notas_encerramento.strip():
                        st.error("Informe as notas de encerramento antes de concluir.")
                    else:
                        indice = opcoes_pendencias.index(item_selecionado)
                        item = pendencias.iloc[indice]
                        close_record(
                            item["tabela"],
                            int(item["id"]),
                            notas_encerramento,
                        )
                        rerun_with_success(
                            "Ocorrência encerrada e mantida no histórico."
                        )
        else:
            st.info("Entre na plataforma para atualizar o status.")

    st.markdown("### Registrar passagem")
    with st.form("form_passagem_turno"):
        col1, col2 = st.columns(2)
        with col1:
            turno_destino = st.selectbox(
                "Turno de destino",
                turnos,
                index=turnos.index(turno_atual),
            )
            operador_destino = st.text_input("Operador que está recebendo")
        with col2:
            observacoes_passagem = st.text_area(
                "Resumo, prioridades e orientações para o próximo turno",
                placeholder="Registre contexto importante que não aparece nas pendências.",
            )

        registrar_passagem = st.form_submit_button("Registrar passagem de turno")
        if registrar_passagem:
            if not responsavel.strip():
                st.error("Informe o operador responsável no painel lateral.")
            elif not operador_destino.strip():
                st.error("Informe o operador que está recebendo o turno.")
            else:
                run_query(
                    """INSERT INTO passagens_turno
                       (turno_origem, operador_origem, turno_destino, operador_destino,
                        observacoes, pendencias_abertas, data_atualizacao)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        turno_atual,
                        responsavel.strip(),
                        turno_destino,
                        operador_destino.strip(),
                        observacoes_passagem.strip(),
                        total_pendencias,
                        now_utc_iso(),
                    ),
                )
                rerun_with_success("Passagem de turno registrada com sucesso.")

    st.markdown("### Passagens anteriores")
    historico_passagens = load_data(
        """SELECT data_registro, data_atualizacao, turno_origem, operador_origem,
                  turno_destino, operador_destino, pendencias_abertas, observacoes
           FROM passagens_turno ORDER BY id DESC LIMIT 20"""
    )
    historico_passagens["data_registro"] = historico_passagens[
        "data_registro"
    ].map(display_timestamp)
    historico_passagens["data_atualizacao"] = historico_passagens[
        "data_atualizacao"
    ].map(display_timestamp)
    st.dataframe(historico_passagens, width="stretch", hide_index=True)

# 1. CONECTIVIDADE
with st.container(key="module-body-1"):
    st.subheader("Links de operadoras")
    tipos_link = ["MPLS", "Dedicado", "4G"]
    operadoras_por_link = {
        "MPLS": ["Vivo"],
        "Dedicado": [
            "NetGames", "Oxman", "Sumicity", "Transit Brasil", "Mundivox",
            "Century", "Vivo", "WCS", "ITS Telecom", "Embratel", "Infolink",
            "TBNet", "K2 Telecom", "Portal Algar", "America Net", "Telium",
        ],
        "4G": ["Link 4G Próprio da DPSP", "Link 4G TBNet"],
    }
    link_isolation = st.radio(
        "A loja está isolada por link?",
        ["Sim", "Não"],
        index=1,
        horizontal=True,
        key="connectivity_link_isolation",
    )
    is_isolated = link_isolation == "Sim"
    if is_isolated:
        solicitacao_4g = st.radio(
            "Solicitado envio de 4G?",
            ["Sim", "Não"],
            index=1,
            horizontal=True,
            key="solicitacao_envio_4g",
        )
        if solicitacao_4g == "Não":
            st.warning("Favor abrir chamado para solicitação do 4G")
            protocolo_4g = ""
            status_chamado_4g = ""
        else:
            protocolo_4g = st.text_input(
                "Número do Chamado para o 4G",
                key="protocolo_chamado_4g",
            )
            status_chamado_4g = st.selectbox(
                "Status do Chamado",
                ["Pendente", "Em andamento", "Resolvido"],
                key="status_chamado_4g",
            )
        observacao_4g = st.text_area(
            "Observação",
            key="observacao_chamado_4g",
        )
    else:
        solicitacao_4g = ""
        protocolo_4g = ""
        status_chamado_4g = ""
        observacao_4g = ""

    tipo_unidade = st.selectbox(
        "Tipo de unidade",
        [
            "Loja",
            "Loja Polo",
            "Dark Store",
            "Centro de Distribuição (CD)",
            "Matriz",
            "Data Center",
        ],
    )
    circuitos_por_topologia = {
        "Loja": ["Link Primário", "Link Secundário", "Múltiplos Links / Inoperância Total"],
        "Loja Polo": ["Link Primário", "Link Secundário", "Múltiplos Links / Inoperância Total"],
        "Dark Store": ["Link Primário", "Link Secundário", "Múltiplos Links / Inoperância Total"],
        "Centro de Distribuição (CD)": [
            "Link Primário",
            "Link Secundário",
            "Link Terciário / Contingência",
            "Múltiplos Links / Inoperância Total",
        ],
        "Matriz": [
            "Link Primário",
            "Link Secundário",
            "Link Terciário / Contingência",
            "Múltiplos Links / Inoperância Total",
        ],
        "Data Center": [
            "Link Primário",
            "Link Secundário",
            "Link Terciário / Contingência",
            "Múltiplos Links / Inoperância Total",
        ],
    }
    st.caption(
        "Topologia dupla: loja, polo e dark store. "
        "Topologia múltipla: CD, matriz e data center."
    )

    catalog_path = find_store_catalog_path()
    store_catalog = None
    store_columns = None
    if catalog_path is None:
        st.info(
            "A base de lojas ainda não está disponível. "
            "Um administrador pode carregá-la em Gestão de Usuários."
        )
    else:
        try:
            store_catalog, store_columns = load_store_catalog(
                catalog_path.read_bytes()
            )
        except (OSError, ValueError) as error:
            st.warning(f"Não foi possível carregar a base de lojas: {error}")

    unidade = st.text_input(
        "Unidade",
        placeholder="VD043",
        key="connectivity_unit",
        on_change=(
            autofill_connectivity_store
            if store_catalog is not None
            else None
        ),
        args=(store_catalog, store_columns),
    )
    if (
        unidade.strip()
        and store_catalog is not None
        and find_store(store_catalog, store_columns, unidade) is None
    ):
        st.info("Unidade não encontrada na base. Preencha os dados da loja manualmente.")

    col_name, col_email = st.columns(2)
    with col_name:
        nome_unidade = st.text_input(
            "Nome da Loja",
            key=CONNECTIVITY_AUTOFILL_KEYS["name"],
        )
    with col_email:
        email_loja = st.text_input(
            "E-mail da Loja",
            key=CONNECTIVITY_AUTOFILL_KEYS["email"],
        )

    col_rua, col_bairro, col_estado = st.columns(3)
    with col_rua:
        rua = st.text_input(
            "Rua / endereço",
            key=CONNECTIVITY_AUTOFILL_KEYS["address"],
        )
    with col_bairro:
        bairro = st.text_input(
            "Bairro",
            key=CONNECTIVITY_AUTOFILL_KEYS["district"],
        )
    with col_estado:
        estado = st.text_input(
            "Estado (UF)",
            key=CONNECTIVITY_AUTOFILL_KEYS["state"],
        )

    st.markdown("### Dados dos links")
    if is_isolated:
        col_link_1, col_link_2 = st.columns(2)
        with col_link_1:
            tipo_link_1 = st.selectbox(
                "Tipo de Link 1",
                tipos_link,
                key="tipo_link_conectividade_1",
            )
            operadora_1 = st.selectbox(
                "Operadora do Link 1",
                operadoras_por_link[tipo_link_1],
                key=f"operadora_conectividade_1_{tipo_link_1}",
            )
            situacao_1 = st.selectbox(
                "Situação do Link 1",
                ["Link com degradação", "Link inoperante"],
                key="situacao_conectividade_1",
            )
            protocolo_1 = st.text_input(
                "Número do Protocolo/Chamado do Link 1",
                key="protocolo_conectividade_1",
            )
            status_1 = st.selectbox(
                "Status do Link 1",
                STATUS_OPTIONS["conectividade"],
                key="status_conectividade_1",
            )
        with col_link_2:
            tipo_link_2 = st.selectbox(
                "Tipo de Link 2",
                tipos_link,
                key="tipo_link_conectividade_2",
            )
            operadora_2 = st.selectbox(
                "Operadora do Link 2",
                operadoras_por_link[tipo_link_2],
                key=f"operadora_conectividade_2_{tipo_link_2}",
            )
            situacao_2 = st.selectbox(
                "Situação do Link 2",
                ["Link com degradação", "Link inoperante"],
                key="situacao_conectividade_2",
            )
            protocolo_2 = st.text_input(
                "Número do Protocolo/Chamado do Link 2",
                key="protocolo_conectividade_2",
            )
            status_2 = st.selectbox(
                "Status do Link 2",
                STATUS_OPTIONS["conectividade"],
                key="status_conectividade_2",
            )
        link_records = [
            (
                tipo_link_1,
                operadora_1,
                "Link Primário",
                situacao_1,
                protocolo_1,
                status_1,
            ),
            (
                tipo_link_2,
                operadora_2,
                "Link Secundário",
                situacao_2,
                protocolo_2,
                status_2,
            ),
        ]
    else:
        tipo_link_1 = st.selectbox(
            "Tipo de Link",
            tipos_link,
            key="tipo_link_conectividade",
        )
        col_circuito, col_operadora = st.columns(2)
        with col_circuito:
            if tipo_link_1 == "MPLS":
                circuito_1 = "Link Primário"
                st.text_input(
                    "Circuito afetado",
                    value=circuito_1,
                    disabled=True,
                )
            else:
                circuito_1 = st.selectbox(
                    "Circuito afetado",
                    circuitos_por_topologia[tipo_unidade],
                    key=f"circuito_conectividade_{tipo_link_1}",
                )
        with col_operadora:
            operadora_1 = st.selectbox(
                "Operadora",
                operadoras_por_link[tipo_link_1],
                key=f"operadora_conectividade_{tipo_link_1}",
            )
        situacao_1 = st.selectbox(
            "Situação do Link 1",
            ["Link com degradação", "Link inoperante"],
        )
        protocolo_1 = st.text_input(
            "Número do Protocolo/Chamado do Link 1",
            key="protocolo_conectividade_1",
        )
        status_1 = st.selectbox(
            "Status do Link 1",
            ["Pendente", "Em andamento", "Resolvido"],
        )
        link_records = [
            (
                tipo_link_1,
                operadora_1,
                circuito_1,
                situacao_1,
                protocolo_1,
                status_1,
            )
        ]

    submit_conn = st.button("Registrar Incidente de Link")
    if submit_conn:
        if not unidade.strip():
            st.error("Informe o código do local.")
        else:
            inserted_at = now_utc_iso()
            insert_sql = """INSERT INTO conectividade
                   (unidade, nome_unidade, rua, bairro, estado, email_loja,
                   tipo_unidade, tipo_link, operadora, circuito_afetado, impacto,
                   protocolo, status, solicitacao_4g, protocolo_4g,
                   status_chamado_4g, observacao_4g, observacoes_encerramento,
                   turno, data_atualizacao, data_resolucao)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            parameter_rows = [
                (
                    unidade.strip(),
                    nome_unidade.strip(),
                    rua.strip(),
                    bairro.strip(),
                    estado.strip(),
                    email_loja.strip(),
                    tipo_unidade,
                    tipo_link,
                    operadora,
                    circuito_afetado,
                    situacao,
                    protocolo.strip(),
                    status,
                    solicitacao_4g,
                    protocolo_4g.strip(),
                    status_chamado_4g,
                    observacao_4g.strip(),
                    observacao_4g.strip(),
                    turno_atual,
                    inserted_at,
                    now_utc_iso() if status == "Resolvido" else None,
                )
                for (
                    tipo_link,
                    operadora,
                    circuito_afetado,
                    situacao,
                    protocolo,
                    status,
                ) in link_records
            ]
            try:
                run_many(insert_sql, parameter_rows)
            except sqlite3.Error as error:
                st.error(f"Não foi possível registrar o incidente: {error}")
            else:
                rerun_with_success(
                    "Incidentes dos dois links registrados com sucesso!"
                    if is_isolated
                    else "Incidente de conectividade registrado com sucesso!"
                )

    st.markdown("### Histórico de ocorrências de links")
    df_conn = load_data(
        """SELECT id, unidade, nome_unidade, rua, bairro, estado, email_loja,
                  tipo_unidade, tipo_link, operadora, circuito_afetado, impacto,
                  protocolo, status, solicitacao_4g, protocolo_4g,
                  status_chamado_4g, observacao_4g,
                  observacoes_encerramento, turno, data_registro,
                  data_atualizacao, data_resolucao
           FROM conectividade ORDER BY id DESC"""
    )
    df_conn = df_conn.rename(columns={"email_loja": "E-mail da Loja"})
    render_status_manager(
        "conectividade",
        df_conn,
        "Links de operadoras com horários e duração do atendimento",
    )

# 2. LOJAS EM GNET
with st.container(key="module-body-2"):
    st.subheader("Lojas em GNET")
    motivo_gnet = st.selectbox(
        "Motivo",
        ["Fortinet com degradação", "Fortinet danificado"],
        key="motivo_gnet",
    )
    gnet_catalog = None
    gnet_catalog_columns = None
    gnet_catalog_path = find_store_catalog_path()
    if gnet_catalog_path is None:
        st.info(
            "A base de lojas ainda não está disponível. "
            "Um administrador pode carregá-la em Gestão de Usuários."
        )
    else:
        try:
            gnet_catalog, gnet_catalog_columns = load_store_catalog(
                gnet_catalog_path.read_bytes()
            )
        except (OSError, ValueError) as error:
            st.warning(f"Não foi possível carregar a base de lojas: {error}")
    unidade_gnet = st.text_input(
        "Unidade",
        placeholder="VD043",
        key="gnet_unit",
        on_change=autofill_gnet_store if gnet_catalog is not None else None,
        args=(gnet_catalog, gnet_catalog_columns),
    )
    if (
        unidade_gnet.strip()
        and gnet_catalog is not None
        and find_store(gnet_catalog, gnet_catalog_columns, unidade_gnet) is None
    ):
        st.info("Unidade não encontrada na base. Preencha os dados manualmente.")

    with st.form("form_gnet"):
        col1, col2 = st.columns(2)
        with col1:
            nome_unidade_gnet = st.text_input(
                "Nome da Loja",
                key="gnet_store_name",
            )
            estado_gnet = st.text_input(
                "Estado",
                key="gnet_store_state",
            )
            if motivo_gnet == "Fortinet danificado":
                observacao_dano = st.text_area(
                    "Descreva o dano identificado no Fortinet",
                    placeholder="Ex.: fonte danificada, queimado após contato com água.",
                    key="gnet_damage_observation",
                )
            else:
                observacao_dano = ""
            modelo_fortinet = st.text_input(
                "Modelo do Fortinet (Ex: FortiGate 30E / 60D)",
                key="gnet_model",
            )
        with col2:
            ip_balcao = st.text_input("IP do Balcão", key="gnet_ip")
            porta_switch = st.text_input(
                "Número da Porta do Switch",
                key="gnet_switch_port",
            )
            chamado_gnet = st.text_input(
                "Número do Chamado",
                key="gnet_ticket_number",
            )
            status = st.selectbox(
                "Status",
                STATUS_OPTIONS["lojas_gnet"],
                key="status_gnet",
            )
        
        submit_gnet = st.form_submit_button("Salvar GNET")
        if submit_gnet:
            if not unidade_gnet.strip():
                st.error("Informe a unidade.")
            elif not chamado_gnet.strip():
                st.error("Informe o número do chamado aberto para o time de redes.")
            elif motivo_gnet == "Fortinet danificado" and not observacao_dano.strip():
                st.error("Descreva o dano identificado no Fortinet.")
            else:
                run_query(
                    """INSERT INTO lojas_gnet
                       (unidade, nome_unidade, estado, motivo, modelo_fortinet,
                        ip_balcao, porta_switch, chamado_redes, observacao_dano,
                        status, turno, data_atualizacao)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        unidade_gnet.strip(), nome_unidade_gnet.strip(),
                        estado_gnet.strip(), motivo_gnet, modelo_fortinet.strip(),
                        ip_balcao.strip(), porta_switch.strip(), chamado_gnet.strip(),
                        observacao_dano.strip(), status, turno_atual,
                        now_utc_iso(),
                    ),
                )
                rerun_with_success("Loja em GNET registrada!")

    st.markdown("### Histórico de registros GNET")
    df_gnet = load_data(
        """SELECT id, unidade, nome_unidade, estado, motivo, observacao_dano,
                  modelo_fortinet, ip_balcao,
                  porta_switch, chamado_redes, status, turno, data_registro,
                  data_atualizacao, data_resolucao
           FROM lojas_gnet ORDER BY id DESC"""
    )
    render_status_manager(
        "lojas_gnet",
        df_gnet,
        "Registros GNET com status, horários e duração do atendimento",
    )

# 3. INFRAESTRUTURA LOCAL & FIELD
with st.container(key="module-body-3"):
    st.subheader("Field Service")
    categoria_infra = st.selectbox(
        "Categoria",
        ["Switch", "Desk Server", "Serviço de campo"],
        key="categoria_infra",
    )
    subtipo_field_service = ""
    if categoria_infra == "Serviço de campo":
        subtipo_field_service = st.selectbox(
            "Tipo de serviço de campo",
            [
                "Troca / configuração de switch",
                "Envio / instalação / retirada de modem 4G",
                "Apoio operacional na loja",
            ],
            key="subtipo_field_service",
        )
    with st.form("form_infra"):
        col1, col2 = st.columns(2)
        with col1:
            unidade = st.text_input("Loja (número VD/L)")
            protocolo_infra = st.text_input("Número do chamado")
            modelo_equipamento = ""
            if categoria_infra == "Switch":
                modelo_equipamento = st.text_input("Modelo do switch")
            elif (
                categoria_infra == "Serviço de campo"
                and subtipo_field_service == "Envio / instalação / retirada de modem 4G"
            ):
                modelo_equipamento = st.text_input("Modelo do modem 4G")
        with col2:
            detalhes = st.text_area(
                "Descrição",
                placeholder="Descreva o problema encontrado e o contexto para o próximo turno.",
            )
            tratativa = st.text_area(
                "Tratativa",
                placeholder="Informe as ações realizadas e os próximos passos.",
            )
            status = st.selectbox("Status", ["Pendente", "Em andamento", "Resolvido"])
            notas_encerramento = st.text_area(
                "Notas de resolução (obrigatórias quando status for Resolvido)"
            )
        
        submit_infra = st.form_submit_button("Registrar ocorrência")
        if submit_infra:
            if not unidade.strip():
                st.error("Informe o número da loja.")
            elif categoria_infra == "Switch" and not modelo_equipamento.strip():
                st.error("Informe o modelo do switch.")
            elif not detalhes.strip() and not tratativa.strip():
                st.error("Preencha a descrição ou a tratativa.")
            elif status == "Resolvido" and not notas_encerramento.strip():
                st.error("Informe as notas de resolução antes de concluir.")
            else:
                run_query(
                    """INSERT INTO infra_local
                       (tipo_problema, unidade, detalhes, protocolo, status,
                        observacoes_encerramento, subtipo_field_service, modelo_equipamento,
                        tratativa, turno, data_atualizacao, data_resolucao)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        categoria_infra, unidade.strip(), detalhes.strip(),
                        protocolo_infra.strip(), status, notas_encerramento.strip(),
                        subtipo_field_service, modelo_equipamento.strip(),
                        tratativa.strip(), turno_atual,
                        now_utc_iso(),
                        now_utc_iso() if status == "Resolvido" else None,
                    ),
                )
                rerun_with_success("Ocorrência registrada!")

    st.markdown("### Histórico de ocorrências de Field Service")
    df_infra = load_data(
        """SELECT id, tipo_problema, subtipo_field_service, unidade, modelo_equipamento,
                  protocolo, detalhes, tratativa, status, observacoes_encerramento,
                  turno, data_registro,
                  data_atualizacao, data_resolucao
           FROM infra_local ORDER BY id DESC"""
    )
    render_status_manager(
        "infra_local",
        df_infra,
        "Ocorrências de Field Service com horários e duração do atendimento",
    )

# 4. ALERTAS SISTÊMICOS
with st.container(key="module-body-4"):
    st.subheader("Alertas sistêmicos")
    sistemas_alerta = [
        "PeopleSoft / Wipro",
        "Datadog",
        "DataCosmos (OGG)",
        "Farmácia Popular",
        "Outros",
    ]
    status_alerta_options = [
        "Pendente",
        "Em andamento",
        "Resolvido",
        "Relacionado a problema",
    ]
    problemas_ativos = load_data(
        """SELECT id, num_problema, titulo_erro
           FROM problemas_glpi
           WHERE status IN (
               'Em andamento',
               'Problema em análise com time/fornecedor',
               'Ativo / Aberto'
           )
           ORDER BY num_problema"""
    )
    opcoes_problemas = ["Não vincular a um problema"] + [
        f"{row.num_problema} — {row.titulo_erro}"
        for row in problemas_ativos.itertuples(index=False)
    ]
    with st.form("form_alertas"):
        sistema = st.selectbox("Sistema / Plataforma", sistemas_alerta)
        descricao_erro = st.text_area("Descrição do alerta / erro")
        vinculado_glpi = st.selectbox("Há chamado GLPI vinculado?", ["Não", "Sim"])
        chamado_glpi = st.text_input("Número do Chamado GLPI (se houver)")
        equipe_acionada = st.text_input("Equipe / analista acionado")
        status = st.selectbox("Status", status_alerta_options)
        problema_selecionado = st.selectbox(
            "Problema GLPI relacionado (opcional)",
            opcoes_problemas,
            disabled=not problemas_ativos.shape[0],
        )
        
        submit_alerta = st.form_submit_button("Registrar Alerta Sistêmico")
        if submit_alerta:
            if not descricao_erro.strip():
                st.error("Descreva o alerta ou erro.")
            elif vinculado_glpi == "Sim" and not chamado_glpi.strip():
                st.error("Informe o número do GLPI ou altere o vínculo para Não.")
            elif status == "Relacionado a problema" and problema_selecionado == opcoes_problemas[0]:
                st.error("Selecione o problema GLPI que está relacionado ao alerta.")
            else:
                problema_glpi_id = None
                if problema_selecionado != opcoes_problemas[0]:
                    indice_problema = opcoes_problemas.index(problema_selecionado) - 1
                    problema_glpi_id = int(problemas_ativos.iloc[indice_problema]["id"])
                run_query(
                    """INSERT INTO alertas_sistemicos
                       (sistema, descricao_erro, chamado_glpi, vinculado_glpi,
                        problema_glpi_id, equipe_acionada, status, turno,
                        data_atualizacao, data_resolucao)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        sistema, descricao_erro.strip(), chamado_glpi.strip(),
                        vinculado_glpi, problema_glpi_id, equipe_acionada.strip(),
                        status, turno_atual, now_utc_iso(),
                        now_utc_iso() if status == "Resolvido" else None,
                    ),
                )
                rerun_with_success("Alerta sistêmico salvo!")

    st.markdown("### Histórico de alertas sistêmicos")
    df_alertas = load_data(
        """SELECT a.id, a.sistema, a.descricao_erro, a.chamado_glpi,
                  a.equipe_acionada, a.status, p.num_problema AS problema_relacionado,
                  a.turno, a.data_registro, a.data_atualizacao, a.data_resolucao
           FROM alertas_sistemicos AS a
           LEFT JOIN problemas_glpi AS p ON p.id = a.problema_glpi_id
           ORDER BY a.id DESC"""
    )
    render_status_manager(
        "alertas_sistemicos",
        df_alertas,
        "Alertas sistêmicos com horários e duração do atendimento",
    )

# 5. MALHA DE PREÇOS
with st.container(key="module-body-5"):
    st.subheader("Acompanhamento da Malha de Preços")
    status_malha_options = [
        "Pendente",
        "Em andamento",
        "Resolvido após acionamento",
    ]
    with st.form("form_malha"):
        col1, col2, col3 = st.columns(3)
        with col1:
            fase_malha = st.selectbox(
                "Turno / fase da malha",
                ["Manhã", "Tarde", "Noite", "Madrugada"],
            )
            houve_incidente = st.selectbox("Houve incidente?", ["Não", "Sim"])
        with col2:
            houve_chamado = st.selectbox("Houve chamado aberto?", ["Não", "Sim"])
            numero_chamado = st.text_input("Número do chamado (se houver)")
        with col3:
            time_acionado = st.text_input("Time acionado (se houver)")
            analista_acionado = st.text_input("Analista acionado (se houver)")

        observacao_malha = st.text_area(
            "Observação",
            placeholder="Descreva o incidente, a falha ou outro contexto relevante.",
        )
        status = st.selectbox("Status", status_malha_options)
        
        submit_malha = st.form_submit_button("Registrar Malha de Preços")
        if submit_malha:
            if houve_incidente != "Sim":
                st.error("Use este registro somente quando houver um incidente na malha.")
            elif houve_chamado == "Sim" and not numero_chamado.strip():
                st.error("Informe o número do chamado aberto.")
            elif not observacao_malha.strip():
                st.error("Descreva o incidente na observação.")
            else:
                acionamento = houve_incidente
                analista_acionado = analista_acionado.strip()
                run_query(
                    """INSERT INTO malha_precos
                       (fase_malha, acionamento, houve_incidente, houve_chamado,
                        numero_chamado, time_acionado, analista_acionado, descricao_erro,
                        status, turno, data_atualizacao, data_resolucao)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        fase_malha,
                        acionamento,
                        houve_incidente,
                        houve_chamado,
                        numero_chamado.strip(),
                        time_acionado.strip(),
                        analista_acionado,
                        observacao_malha.strip(),
                        status,
                        turno_atual,
                        now_utc_iso(),
                        now_utc_iso()
                        if status == "Resolvido após acionamento"
                        else None,
                    ),
                )
                rerun_with_success("Incidente da malha de preços registrado.")

    st.markdown("### Histórico / Status da Malha")
    df_malha = load_data(
        """SELECT id, fase_malha, houve_incidente, houve_chamado, numero_chamado,
                  time_acionado, analista_acionado, descricao_erro, status, turno,
                  data_registro, data_atualizacao, data_resolucao
           FROM malha_precos
           ORDER BY id DESC"""
    )
    render_status_manager(
        "malha_precos",
        df_malha,
        "Malha de preços com horários e duração do atendimento",
    )

# 6. LOJAS PENDENTES DE BASE DE PREÇO
with st.container(key="module-body-6"):
    st.subheader("Lojas Pendentes de Recebimento de Base de Preço")
    st.caption(
        "Consulte a planilha compartilhada para acompanhar as unidades e registre "
        "nesta aplicação cada pendência que exigir acompanhamento."
    )
    st.link_button(
        "Abrir planilha de descida de bases no SharePoint",
        "https://dpspo365.sharepoint.com/:x:/r/sites/commandcenter/_layouts/15/doc2.aspx?sourcedoc=%7B5B275B13-E740-4288-8BC9-801D5DE01F0B%7D&file=Descida%20de%20bases%203.0.xlsx&action=default&mobileredirect=true&DefaultItemOpen=1%3Fweb%3D1&wdOrigin=TEAMS-MAGLEV.p2p_ns.rwc&wdExp=TEAMS-TREATMENT&wdhostclicktime=1769511050756&web=1",
        icon=":material/open_in_new:",
    )
    with st.form("form_base"):
        col1, col2 = st.columns(2)
        with col1:
            unidade = st.text_input("Unidade (VD/L + Nome)")
            motivo_obs = st.text_input(
                "Motivo",
                placeholder="Ex.: Desk Service desligado / Sem internet",
            )
        with col2:
            tratativa = st.text_input("Tratativa")
            status = st.selectbox("Status", ["Pendente", "Em andamento"])
        
        submit_base = st.form_submit_button("Adicionar Loja Pendente de Base")
        if submit_base and unidade:
            run_query(
                """INSERT INTO pendentes_base
                   (unidade, motivo_obs, tratativa, status, turno, data_atualizacao)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (unidade, motivo_obs, tratativa, status, turno_atual, now_utc_iso())
            )
            rerun_with_success("Loja pendente de base cadastrada!")

    st.caption(
        "Para acompanhar os cards de TI da malha de preços, abra o link e encaminhe "
        "o card atualizado no grupo operacional."
    )
    st.link_button(
        "Abrir cards de TI — malha de preços",
        "https://dpspo365.sharepoint.com/:p:/r/sites/commandcenter/_layouts/15/Doc.aspx?sourcedoc=%7B152B498C-4C2C-4583-8508-C254312CD929%7D&file=Cards%20TI%20-%20WhatsApp%20-%20Central%20de%20Comando.pptx&action=edit&mobileredirect=true",
        icon=":material/open_in_new:",
    )

    st.markdown("### Histórico de lojas pendentes de base")
    df_base = load_data(
        """SELECT id, unidade, motivo_obs, tratativa, status, turno,
                  data_registro, data_atualizacao, data_resolucao
           FROM pendentes_base ORDER BY id DESC"""
    )
    render_status_manager(
        "pendentes_base",
        df_base,
        "Lojas pendentes de base de preço com horários e duração",
    )

# 7. FLASH & GAP DE VENDAS
with st.container(key="module-body-7"):
    st.subheader("Registro de incidentes de Flash e Gap de Vendas")
    st.caption(
        "Registre somente erros ou incidentes. Se não houver registro no período, "
        "considere o Flash e o Gap de Vendas operando normalmente."
    )
    with st.form("form_vendas"):
        col1, col2 = st.columns(2)
        with col1:
            tipo_indicador = st.selectbox(
                "Sistema/incidente",
                ["Flash de Vendas", "Gap de Vendas"],
            )
            analista_acionado = st.text_input("Analista acionado")
        with col2:
            descricao_erro = st.text_area("Descrição do erro")
            status = st.selectbox(
                "Status",
                ["Pendente", "Em andamento", "Resolvido"],
            )
        
        submit_vendas = st.form_submit_button("Salvar Registro de Vendas")
        if submit_vendas:
            if not descricao_erro.strip():
                st.error("Descreva o erro identificado.")
            else:
                timestamp = now_utc_iso()
                run_query(
                    """INSERT INTO indicadores_vendas
                       (tipo_indicador, acionamento, analista_acionado, descricao_erro,
                        status, turno, data_atualizacao, data_resolucao)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        tipo_indicador,
                        None,
                        analista_acionado.strip(),
                        descricao_erro.strip(),
                        status,
                        turno_atual,
                        timestamp,
                        timestamp if status == "Resolvido" else None,
                    )
                )
                rerun_with_success("Registro de vendas salvo!")

    st.markdown("### Histórico de incidentes de Flash e Gap")
    df_vendas = load_data(
        """SELECT id, tipo_indicador, analista_acionado, descricao_erro, status,
                  turno, data_registro, data_atualizacao, data_resolucao
           FROM indicadores_vendas ORDER BY id DESC"""
    )
    render_status_manager(
        "indicadores_vendas",
        df_vendas,
        "Incidentes de Flash e Gap com horários e duração do atendimento",
    )

# 8. PROBLEMAS GLPI
with st.container(key="module-body-8"):
    st.subheader("Gerenciamento de Problemas Abertos (GLPI - PRB)")
    with st.form("form_prb"):
        col1, col2 = st.columns(2)
        with col1:
            num_problema = st.text_input("Número do problema (Ex.: PRB-12345)")
            titulo_erro = st.text_input("Sintoma")
        with col2:
            time_responsavel = st.text_input("Time responsável")
            sistema_afetado = st.text_input("Sistema / Aplicação Afetada")
        quantidade_chamados = st.number_input(
            "Quantidade de chamados vinculados",
            min_value=0,
            value=0,
            step=1,
            help="Informe a quantidade manualmente até a integração com a API do GLPI.",
        )
        orientacao = st.text_area("Descrição")
        status = st.selectbox(
            "Status",
            STATUS_OPTIONS["problemas_glpi"],
        )

        submit_prb = st.form_submit_button("Cadastrar Problema GLPI")
        if submit_prb and num_problema.strip():
            timestamp = now_utc_iso()
            run_query(
                """INSERT INTO problemas_glpi
                   (num_problema, titulo_erro, time_responsavel, sistema_afetado,
                    orientacao, quantidade_chamados, status, turno,
                    data_atualizacao, data_resolucao)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    num_problema.strip(),
                    titulo_erro.strip(),
                    time_responsavel.strip(),
                    sistema_afetado.strip(),
                    orientacao.strip(),
                    int(quantidade_chamados),
                    status,
                    turno_atual,
                    timestamp,
                    timestamp if status in RESOLVED_STATUSES else None,
                )
            )
            rerun_with_success("Problema cadastrado com sucesso!")

    st.markdown("### Problemas GLPI")
    df_prb = load_data(
        """SELECT id, num_problema, titulo_erro, time_responsavel,
                  sistema_afetado, quantidade_chamados, orientacao, status,
                  turno, data_registro, data_atualizacao, data_resolucao
           FROM problemas_glpi ORDER BY data_registro DESC"""
    )
    st.caption(
        "Os problemas são referências para relacionar alertas já registrados. "
        "O alerta continua sendo o único evento contado nos indicadores."
    )
    render_status_manager(
        "problemas_glpi",
        df_prb,
        "Problemas GLPI, chamados informados, status e tempos de acompanhamento",
    )

    alertas_relacionados = load_data(
        """SELECT p.num_problema, a.data_registro, a.sistema, a.descricao_erro,
                  a.chamado_glpi, a.status, a.turno
           FROM alertas_sistemicos AS a
           JOIN problemas_glpi AS p ON p.id = a.problema_glpi_id
           ORDER BY a.data_registro DESC"""
    )
    if not alertas_relacionados.empty:
        st.markdown("### Alertas vinculados aos problemas")
        st.dataframe(
            alertas_relacionados,
            width="stretch",
            hide_index=True,
            alt="Alertas já registrados relacionados a problemas GLPI",
        )

# 9. FILA GLPI
with st.container(key="module-body-9"):
    st.subheader("Resumo da Fila do GLPI (Backlog do Turno)")
    with st.form("form_fila"):
        col1, col2, col3 = st.columns(3)
        with col1:
            total_fila = st.number_input("Total na Fila", min_value=0, value=0)
            automaticos = st.number_input("Alertas Automáticos (Zabbix/Grafana)", min_value=0, value=0)
        with col2:
            inauguracoes = st.number_input("Inaugurações de Lojas", min_value=0, value=0)
            link1 = st.number_input("Ativações Link 1 (Dedicados)", min_value=0, value=0)
        with col3:
            link2 = st.number_input("Ativações Link 2 (Contingência)", min_value=0, value=0)
            manuais = st.number_input("Chamados Manuais / Infra / Switches", min_value=0, value=0)
        
        submit_fila = st.form_submit_button("Salvar Métricas da Fila")
        if submit_fila:
            soma_categorias = automaticos + inauguracoes + link1 + link2 + manuais
            if total_fila != soma_categorias:
                st.error(
                    f"O total informado ({total_fila}) deve ser igual à soma das categorias "
                    f"({soma_categorias})."
                )
            else:
                run_query(
                    """INSERT INTO fila_glpi_metrics
                       (total_fila, automaticos, inauguracoes, link1, link2,
                        manuais, turno, data_atualizacao)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        total_fila, automaticos, inauguracoes, link1, link2,
                        manuais, turno_atual,
                        now_utc_iso(),
                    )
                )
                rerun_with_success("Métricas da fila salvas com sucesso!")

    st.markdown("### Evolução da Fila GLPI")
    df_fila_completo = load_data(
        """SELECT data_registro, data_atualizacao, turno, total_fila,
                  automaticos, inauguracoes, link1, link2, manuais
           FROM fila_glpi_metrics ORDER BY data_registro, id"""
    )
    if df_fila_completo.empty:
        st.info("As métricas salvas aparecerão aqui em um gráfico por data e turno.")
    else:
        df_fila_completo["data/hora (Brasília)"] = df_fila_completo[
            "data_registro"
        ].map(display_timestamp)
        df_fila_completo["atualizado (Brasília)"] = df_fila_completo[
            "data_atualizacao"
        ].map(display_timestamp)
        df_fila_completo["_timestamp_brasilia"] = (
            pd.to_datetime(df_fila_completo["data_registro"], utc=True)
            .dt.tz_convert(BRASILIA_TZ)
            .dt.tz_localize(None)
        )
        st.line_chart(
            df_fila_completo.set_index("_timestamp_brasilia")[
                ["total_fila", "automaticos", "inauguracoes", "link1", "link2", "manuais"]
            ]
        )
        st.markdown("### Histórico recente de métricas por turno")
        st.dataframe(
            df_fila_completo.sort_values("data_registro", ascending=False)
            .drop(columns=["data_registro", "data_atualizacao", "_timestamp_brasilia"])
            .head(10),
            width="stretch",
            hide_index=True,
        )

# 10. RESUMO EXECUTIVO PARA PASSAGEM DE TURNO
with st.container(key="module-body-10"):
    st.subheader("Dashboard operacional")
    st.caption(
        "Visão consolidada para compartilhar com a gestão. "
        "Use os filtros e baixe uma versão pronta para impressão ou e-mail."
    )
    col_data, col_turno = st.columns(2)
    with col_data:
        data_resumo = st.date_input(
            "Data do resumo",
            value=datetime.now(BRASILIA_TZ).date(),
            key="data_resumo",
        )
    with col_turno:
        turno_resumo = st.selectbox(
            "Turno do resumo",
            ["Todos", *turnos],
            key="turno_resumo",
        )

    historico_resumo = load_history(data_resumo, data_resumo, turno_resumo)
    ocorrencias_resumo = historico_resumo[
        ~historico_resumo["categoria"].isin(CATEGORIAS_NAO_OPERACIONAIS)
    ]
    em_aberto_resumo = ocorrencias_resumo[
        ~ocorrencias_resumo["status"].isin(STATUS_ENCERRADOS)
    ]
    resolvidas_resumo = ocorrencias_resumo[
        ocorrencias_resumo["status"].isin(STATUS_ENCERRADOS)
    ]
    criticas_abertas = em_aberto_resumo[
        em_aberto_resumo["criticidade"] == "CRÍTICO / P1"
    ]
    passagens_resumo = historico_resumo[
        historico_resumo["categoria"] == "Passagem de Turno"
    ]

    st.markdown(f"**Período:** {data_resumo} · **Turno:** {turno_resumo}")
    with st.container(horizontal=True):
        st.metric("Ocorrências", len(ocorrencias_resumo), border=True)
        st.metric("Em aberto", len(em_aberto_resumo), border=True)
        st.metric("Resolvidas", len(resolvidas_resumo), border=True)
        st.metric("Críticas / P1", len(criticas_abertas), border=True)

    links_resumo = load_data(
        """SELECT COALESCE(NULLIF(operadora, ''), 'Não informada') AS operadora,
                  COUNT(*) AS ocorrencias
           FROM conectividade
           WHERE DATE(data_registro, '-3 hours') = ? AND (? = 'Todos' OR turno = ?)
           GROUP BY COALESCE(NULLIF(operadora, ''), 'Não informada')
           ORDER BY ocorrencias DESC, operadora""",
        (str(data_resumo), turno_resumo, turno_resumo),
    )
    gnet_resumo = load_data(
        """SELECT unidade AS loja, COUNT(*) AS registros
           FROM lojas_gnet
           WHERE DATE(data_registro, '-3 hours') = ? AND (? = 'Todos' OR turno = ?)
           GROUP BY unidade ORDER BY registros DESC, loja LIMIT 10""",
        (str(data_resumo), turno_resumo, turno_resumo),
    )
    fila_resumo = load_data(
        """SELECT data_registro, turno, total_fila, automaticos, inauguracoes,
                  link1, link2, manuais
           FROM fila_glpi_metrics
           WHERE DATE(data_registro, '-3 hours') = ? AND (? = 'Todos' OR turno = ?)
           ORDER BY data_registro""",
        (str(data_resumo), turno_resumo, turno_resumo),
    )
    malha_resumo = historico_resumo[
        historico_resumo["categoria"] == "Malha de Preços"
    ][["data_registro", "turno", "unidade", "resumo", "status", "protocolo"]]
    ocorrencias_criticas_exibicao = criticas_abertas[
        ["unidade", "resumo", "status", "turno", "protocolo"]
    ]

    st.markdown("### Pontos de atenção")
    if ocorrencias_criticas_exibicao.empty:
        st.success("Nenhuma ocorrência crítica/P1 em aberto neste período.")
    else:
        st.dataframe(
            ocorrencias_criticas_exibicao,
            width="stretch",
            hide_index=True,
            alt="Ocorrências críticas que continuam abertas",
        )

    if not passagens_resumo.empty:
        st.markdown("### Recados das passagens registradas")
        st.dataframe(
            passagens_resumo[["data_registro", "turno", "resumo"]],
            width="stretch",
            hide_index=True,
            alt="Resumos das passagens de turno do período",
        )

    grafico_links, grafico_gnet = st.columns(2)
    with grafico_links:
        with st.container(border=True):
            st.markdown("**Quedas de link por operadora**")
            if links_resumo.empty:
                st.info("Sem registros de conectividade no período.")
            else:
                st.bar_chart(
                    links_resumo,
                    x="operadora",
                    y="ocorrencias",
                    horizontal=True,
                    alt="Ocorrências de conectividade agrupadas por operadora",
                )
    with grafico_gnet:
        with st.container(border=True):
            st.markdown("**Lojas com mais registros em GNET**")
            if gnet_resumo.empty:
                st.info("Sem registros de GNET no período.")
            else:
                st.bar_chart(
                    gnet_resumo,
                    x="loja",
                    y="registros",
                    horizontal=True,
                    alt="Lojas com mais registros de contingência GNET",
                )

    with st.container(border=True):
        st.markdown("**Evolução da fila GLPI**")
        if fila_resumo.empty:
            st.info("Sem snapshots da fila GLPI no período.")
        else:
            fila_grafico = fila_resumo.copy()
            fila_grafico["data_registro"] = (
                pd.to_datetime(fila_grafico["data_registro"], utc=True)
                .dt.tz_convert(BRASILIA_TZ)
                .dt.tz_localize(None)
            )
            fila_grafico["turno"] = (
                fila_grafico["data_registro"].dt.strftime("%H:%M")
                + " · "
                + fila_grafico["turno"].fillna("")
            )
            st.line_chart(
                fila_grafico,
                x="data_registro",
                y="total_fila",
                color="turno",
                alt="Volume da fila GLPI em cada medição do período",
            )
            st.dataframe(
                fila_resumo,
                width="stretch",
                hide_index=True,
                alt="Medições e categorias da fila GLPI",
            )

    with st.container(border=True):
        st.markdown("**Malha de preços e acionamentos**")
        if malha_resumo.empty:
            st.info("Sem registros de malha de preços no período.")
        else:
            st.metric(
                "Acionamentos de suporte",
                int(malha_resumo["resumo"].str.contains("Houve incidente: Sim", case=False, na=False).sum()),
            )
            st.dataframe(
                malha_resumo,
                width="stretch",
                hide_index=True,
                alt="Histórico das malhas de preço e acionamentos",
            )

    indicadores_resumo = {
        "Ocorrências registradas": len(ocorrencias_resumo),
        "Em aberto": len(em_aberto_resumo),
        "Resolvidas": len(resolvidas_resumo),
        "Críticas / P1": len(criticas_abertas),
    }
    relatorio_html = build_executive_report_html(
        data_resumo,
        turno_resumo,
        indicadores_resumo,
        links_resumo,
        gnet_resumo,
        fila_resumo,
        malha_resumo,
        ocorrencias_criticas_exibicao,
    )
    st.download_button(
        "Baixar resumo executivo para impressão / e-mail",
        data=relatorio_html.encode("utf-8"),
        file_name=f"resumo_operacional_{data_resumo}_{turno_resumo.lower()}.html",
        mime="text/html",
        width="stretch",
    )
    st.caption(
        "O arquivo HTML mantém os indicadores e tabelas em formato executivo; "
        "abra-o no navegador para imprimir ou anexar ao e-mail."
    )

# 11. CONSULTA DE HISTÓRICO POR PERÍODO
with st.container(key="module-body-11"):
    st.subheader("Relatórios e histórico por período")
    st.caption(
        "Consulte todos os registros do intervalo, inclusive ocorrências resolvidas, "
        "passagens de turno e snapshots do GLPI."
    )
    col_inicio, col_fim, col_turno_hist = st.columns(3)
    with col_inicio:
        data_inicio_hist = st.date_input(
            "Data inicial",
            value=datetime.now(BRASILIA_TZ).date().replace(day=1),
            key="data_inicio_hist",
        )
    with col_fim:
        data_fim_hist = st.date_input(
            "Data final",
            value=datetime.now(BRASILIA_TZ).date(),
            key="data_fim_hist",
        )
    with col_turno_hist:
        turno_hist = st.selectbox(
            "Turno",
            ["Todos", *turnos],
            key="turno_hist",
        )

    if data_inicio_hist > data_fim_hist:
        st.error("A data inicial deve ser anterior ou igual à data final.")
    else:
        historico_periodo = load_history(
            data_inicio_hist,
            data_fim_hist,
            turno_hist,
        )
        categorias_periodo = ["Todas"] + sorted(historico_periodo["categoria"].unique())
        col_categoria, col_status = st.columns(2)
        with col_categoria:
            categoria_filtro = st.selectbox(
                "Categoria",
                categorias_periodo,
                key="categoria_historico",
            )
        with col_status:
            status_filtro = st.selectbox(
                "Status",
                ["Todos", "Em aberto", "Resolvidos", "Registros de operação"],
                key="status_historico",
            )

        resultado_periodo = historico_periodo.copy()
        if categoria_filtro != "Todas":
            resultado_periodo = resultado_periodo[
                resultado_periodo["categoria"] == categoria_filtro
            ]
        if status_filtro == "Em aberto":
            resultado_periodo = resultado_periodo[
                ~resultado_periodo["status"].isin(STATUS_ENCERRADOS)
                & ~resultado_periodo["categoria"].isin(CATEGORIAS_NAO_OPERACIONAIS)
            ]
        elif status_filtro == "Resolvidos":
            resultado_periodo = resultado_periodo[
                resultado_periodo["status"].isin(STATUS_ENCERRADOS)
            ]
        elif status_filtro == "Registros de operação":
            resultado_periodo = resultado_periodo[
                resultado_periodo["categoria"].isin(CATEGORIAS_NAO_OPERACIONAIS)
            ]

        if (
            categoria_filtro in {"Todas", "Fila GLPI"}
            and status_filtro in {"Todos", "Registros de operação"}
        ):
            evolucao_fila = load_data(
                """SELECT DATE(m.data_registro, '-3 hours') AS dia, m.turno, m.total_fila
                   FROM fila_glpi_metrics AS m
                   WHERE DATE(m.data_registro, '-3 hours') BETWEEN ? AND ?
                     AND (? = 'Todos' OR m.turno = ?)
                     AND NOT EXISTS (
                         SELECT 1 FROM fila_glpi_metrics AS recente
                         WHERE DATE(recente.data_registro, '-3 hours')
                               = DATE(m.data_registro, '-3 hours')
                           AND recente.turno = m.turno
                           AND (recente.data_registro > m.data_registro
                                OR (recente.data_registro = m.data_registro
                                    AND recente.id > m.id))
                     )
                   ORDER BY dia, m.turno""",
                (
                    str(data_inicio_hist),
                    str(data_fim_hist),
                    turno_hist,
                    turno_hist,
                ),
            )
            st.markdown("### Evolução diária da fila GLPI")
            if evolucao_fila.empty:
                st.info("Não há medições da fila GLPI neste intervalo.")
            else:
                st.line_chart(
                    evolucao_fila,
                    x="dia",
                    y="total_fila",
                    color="turno",
                    alt="Última medição diária do volume da fila GLPI por turno",
                )

        col_total, col_abertas, col_resolvidas = st.columns(3)
        registros_operacionais = resultado_periodo[
            ~resultado_periodo["categoria"].isin(CATEGORIAS_NAO_OPERACIONAIS)
        ]
        col_total.metric("Registros no filtro", len(resultado_periodo))
        col_abertas.metric(
            "Ocorrências em aberto",
            int((~registros_operacionais["status"].isin(STATUS_ENCERRADOS)).sum()),
        )
        col_resolvidas.metric(
            "Ocorrências resolvidas",
            int(registros_operacionais["status"].isin(STATUS_ENCERRADOS).sum()),
        )

        if resultado_periodo.empty:
            st.info("Nenhum registro encontrado para os filtros selecionados.")
        else:
            volume_categoria = (
                resultado_periodo.groupby("categoria", as_index=False)
                .size()
                .rename(columns={"size": "registros"})
                .sort_values("registros", ascending=False)
            )
            st.bar_chart(
                volume_categoria,
                x="categoria",
                y="registros",
                horizontal=True,
                alt="Volume de registros por categoria no período selecionado",
            )
            st.dataframe(
                resultado_periodo,
                width="stretch",
                hide_index=True,
                alt="Histórico completo de ocorrências, passagens e métricas no período",
            )
            st.download_button(
                "Baixar consulta em CSV",
                data=resultado_periodo.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"historico_{data_inicio_hist}_{data_fim_hist}.csv",
                mime="text/csv",
            )

if is_admin:
    with st.container(key="module-body-12"):
        st.subheader("Gestão de usuários e permissões")
        st.caption(
            "Cadastre operadores, conceda perfil de administrador, redefina senhas "
            "ou bloqueie acessos. Usuários criados receberão uma senha provisória "
            "e deverão alterá-la no primeiro acesso. Entregue a senha por um canal "
            "seguro; a aplicação não envia e-mails."
        )

        st.markdown("### Base de lojas")
        st.caption(
            "Atualize a planilha usada para preencher os dados da loja no módulo "
            "Conectividade. Os cabeçalhos obrigatórios devem estar na primeira linha."
        )
        store_catalog_upload = st.file_uploader(
            "Planilha base de lojas (.xlsx)",
            type=["xlsx"],
            key="store_catalog_upload",
        )
        if st.button("Atualizar base de lojas", key="update_store_catalog"):
            if store_catalog_upload is None:
                st.error("Selecione uma planilha .xlsx para atualizar a base.")
            else:
                try:
                    save_store_catalog(store_catalog_upload.getvalue())
                except (OSError, ValueError) as error:
                    st.error(f"Não foi possível atualizar a base de lojas: {error}")
                else:
                    load_store_catalog.clear()
                    st.success("Base de lojas atualizada.")
                    st.rerun()

        with st.form("create_user_form"):
            col_name, col_email = st.columns(2)
            with col_name:
                new_full_name = st.text_input("Nome completo")
            with col_email:
                new_email = st.text_input("E-mail")
            col_password, col_confirm = st.columns(2)
            with col_password:
                temporary_password = st.text_input(
                    "Senha provisória (mínimo 12 caracteres)",
                    type="password",
                )
            with col_confirm:
                temporary_password_confirmation = st.text_input(
                    "Confirme a senha provisória",
                    type="password",
                )
            new_role_label = st.selectbox(
                "Perfil de acesso",
                ["Operador", "Administrador"],
            )
            create_user_submitted = st.form_submit_button("Cadastrar usuário")
        if create_user_submitted:
            if temporary_password != temporary_password_confirmation:
                st.error("As senhas provisórias não coincidem.")
            else:
                try:
                    create_user(
                        new_email,
                        new_full_name,
                        temporary_password,
                        "admin" if new_role_label == "Administrador" else "operador",
                        user_id,
                    )
                except (PermissionError, ValueError) as error:
                    st.error(str(error))
                else:
                    st.success(
                        "Usuário cadastrado. A senha provisória deverá ser "
                        "trocada no primeiro acesso."
                    )
                    st.rerun()

        users = list_users()
        if users:
            users_by_id = {account["id"]: account for account in users}
            selected_user_id = st.selectbox(
                "Conta para gerenciar",
                options=list(users_by_id),
                format_func=lambda account_id: (
                    f"{users_by_id[account_id]['full_name']} "
                    f"({users_by_id[account_id]['email']})"
                ),
            )
            selected_user = users_by_id[selected_user_id]
            is_selected_user = selected_user_id == user_id

            with st.form("update_user_access_form"):
                selected_role_label = st.selectbox(
                    "Perfil",
                    ["Administrador", "Operador"],
                    index=0 if selected_user["role"] == "admin" else 1,
                    disabled=is_selected_user,
                )
                selected_user_active = st.checkbox(
                    "Conta ativa",
                    value=selected_user["is_active"],
                    disabled=is_selected_user,
                )
                update_user_submitted = st.form_submit_button(
                    "Salvar permissões"
                )
            if update_user_submitted:
                try:
                    update_user_access(
                        selected_user_id,
                        "admin"
                        if selected_role_label == "Administrador"
                        else "operador",
                        selected_user_active,
                        user_id,
                    )
                except (PermissionError, ValueError) as error:
                    st.error(str(error))
                else:
                    st.success("Permissões atualizadas.")
                    st.rerun()

            with st.form("reset_user_password_form"):
                reset_password = st.text_input(
                    "Nova senha provisória",
                    type="password",
                )
                reset_password_confirmation = st.text_input(
                    "Confirme a nova senha provisória",
                    type="password",
                )
                reset_password_submitted = st.form_submit_button(
                    "Redefinir senha"
                )
            if reset_password_submitted:
                if reset_password != reset_password_confirmation:
                    st.error("As senhas provisórias não coincidem.")
                else:
                    try:
                        reset_user_password(
                            selected_user_id,
                            reset_password,
                            user_id,
                        )
                    except (PermissionError, ValueError) as error:
                        st.error(str(error))
                    else:
                        st.success(
                            "Senha redefinida. O usuário deverá alterá-la ao "
                            "fazer login."
                        )
                        st.rerun()

            users_table = pd.DataFrame(users)
            users_table["created_at"] = users_table["created_at"].map(
                lambda value: display_timestamp(value)
            )
            users_table["role"] = users_table["role"].replace(
                {"admin": "Administrador", "operador": "Operador"}
            )
            users_table["is_active"] = users_table["is_active"].map(
                {True: "Ativo", False: "Inativo"}
            )
            users_table["must_change_password"] = users_table[
                "must_change_password"
            ].map({True: "Sim", False: "Não"})
            users_table = users_table.rename(
                columns={
                    "email": "E-mail",
                    "full_name": "Nome completo",
                    "role": "Perfil",
                    "is_active": "Acesso",
                    "must_change_password": "Troca de senha pendente",
                    "created_at": "Criado em (Brasília)",
                }
            )
            st.markdown("#### Contas cadastradas")
            st.dataframe(
                users_table.drop(columns=["id"]),
                width="stretch",
                hide_index=True,
                alt="Usuários cadastrados e respectivos perfis de acesso",
            )