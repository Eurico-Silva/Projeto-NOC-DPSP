import hashlib
import hmac
import os
import re
from contextlib import closing
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.exc import IntegrityError

from database import connect

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 256
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT = timedelta(minutes=15)
BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")


def now_brasilia_iso():
    return datetime.now(BRASILIA_TZ).isoformat(timespec="seconds")


def normalize_email(email):
    if not isinstance(email, str):
        return ""
    return email.strip().casefold()


def validate_email(email):
    if not isinstance(email, str):
        raise ValueError("Informe um endereço de e-mail válido.")
    normalized_email = normalize_email(email)
    if len(normalized_email) > 254 or not EMAIL_PATTERN.fullmatch(normalized_email):
        raise ValueError("Informe um endereço de e-mail válido.")
    return normalized_email


def validate_full_name(full_name):
    if not isinstance(full_name, str):
        raise ValueError("Informe o nome completo (até 120 caracteres).")
    name = " ".join(full_name.split())
    if not name or len(name) > 120:
        raise ValueError("Informe o nome completo (até 120 caracteres).")
    return name


def validate_password(password):
    if not isinstance(password, str):
        raise ValueError("A senha deve ser um texto válido.")
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError("A senha deve ter pelo menos 12 caracteres.")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError("A senha não pode exceder 256 caracteres.")


def hash_password(password):
    validate_password(password)
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password, stored_hash):
    try:
        algorithm, salt_hex, digest_hex = stored_hash.split("$")
        if algorithm != "scrypt" or len(password) > PASSWORD_MAX_LENGTH:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        if len(salt) != 16 or len(expected) != 32:
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def _connect():
    return connect()


def _user_from_row(row):
    if row is None:
        return None
    return {
        "id": row["id"],
        "email": row["email"],
        "full_name": row["full_name"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "must_change_password": bool(row["must_change_password"]),
        "created_at": row["created_at"],
    }


def get_user_by_id(user_id):
    with closing(_connect()) as connection:
        row = connection.execute(
            """SELECT id, email, full_name, role, is_active,
                      must_change_password, created_at
               FROM users WHERE id = ?""",
            (user_id,),
        ).fetchone()
    return _user_from_row(row)


def list_users():
    with closing(_connect()) as connection:
        rows = connection.execute(
            """SELECT id, email, full_name, role, is_active,
                      must_change_password, created_at
               FROM users ORDER BY full_name, email"""
        ).fetchall()
    return [_user_from_row(row) for row in rows]


def user_count():
    with closing(_connect()) as connection:
        return connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def create_initial_admin(email, full_name, password):
    normalized_email = validate_email(email)
    validated_name = validate_full_name(full_name)
    password_hash = hash_password(password)
    with closing(_connect()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            connection.rollback()
            raise ValueError(
                "A configuração inicial já foi concluída. Entre com uma conta "
                "administradora existente."
            )
        cursor = connection.execute(
            """INSERT INTO users
               (email, password_hash, full_name, role, is_active,
                must_change_password, created_at)
               VALUES (?, ?, ?, 'admin', 1, 0, ?) RETURNING id""",
            (normalized_email, password_hash, validated_name, now_brasilia_iso()),
        )
        user_id = cursor.fetchone()[0]
        connection.commit()
        return user_id


def authenticate_user(email, password):
    normalized_email = normalize_email(email)
    if len(normalized_email) > 254 or not EMAIL_PATTERN.fullmatch(normalized_email):
        normalized_email = ""
    now = datetime.now(BRASILIA_TZ)
    with closing(_connect()) as connection:
        user_row = connection.execute(
            """SELECT id, email, password_hash, full_name, role, is_active,
                      must_change_password, created_at
               FROM users WHERE email = ?""",
            (normalized_email,),
        ).fetchone()
        attempt = connection.execute(
            """SELECT failed_attempts, locked_until
               FROM login_attempts WHERE email = ?""",
            (normalized_email,),
        ).fetchone()
        if attempt and attempt["locked_until"]:
            locked_until = datetime.fromisoformat(attempt["locked_until"])
            if locked_until > now:
                return None

        password_matches = verify_password(
            password,
            user_row["password_hash"] if user_row else _DUMMY_PASSWORD_HASH,
        )
        if user_row is None or not user_row["is_active"] or not password_matches:
            failed_attempts = attempt["failed_attempts"] if attempt else 0
            failed_attempts += 1
            locked_until = (
                (now + LOGIN_LOCKOUT).isoformat(timespec="seconds")
                if failed_attempts >= LOGIN_MAX_ATTEMPTS
                else None
            )
            connection.execute(
                """INSERT INTO login_attempts
                   (email, failed_attempts, locked_until)
                   VALUES (?, ?, ?)
                   ON CONFLICT(email) DO UPDATE SET
                       failed_attempts = excluded.failed_attempts,
                       locked_until = excluded.locked_until""",
                (normalized_email, failed_attempts, locked_until),
            )
            connection.commit()
            return None

        connection.execute(
            "DELETE FROM login_attempts WHERE email = ?",
            (normalized_email,),
        )
        connection.commit()
    return _user_from_row(user_row)


def change_password(user_id, new_password, current_password=None):
    validate_password(new_password)
    new_hash = hash_password(new_password)
    with closing(_connect()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT email, password_hash, is_active FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None or not row["is_active"]:
            connection.rollback()
            raise PermissionError("A conta não está ativa.")
        if current_password is not None and not verify_password(
            current_password, row["password_hash"]
        ):
            connection.rollback()
            raise ValueError("A senha atual está incorreta.")
        if verify_password(new_password, row["password_hash"]):
            connection.rollback()
            raise ValueError("A nova senha deve ser diferente da senha provisória ou atual.")
        connection.execute(
            """UPDATE users SET password_hash = ?, must_change_password = 0
               WHERE id = ?""",
            (new_hash, user_id),
        )
        connection.execute(
            "DELETE FROM login_attempts WHERE email = ?",
            (row["email"],),
        )
        connection.commit()


def _require_admin(connection, actor_id):
    actor = connection.execute(
        "SELECT role, is_active FROM users WHERE id = ?",
        (actor_id,),
    ).fetchone()
    if actor is None or actor["role"] != "admin" or not actor["is_active"]:
        raise PermissionError("Apenas administradores ativos podem gerenciar usuários.")


def create_user(email, full_name, password, role, actor_id):
    normalized_email = validate_email(email)
    validated_name = validate_full_name(full_name)
    validate_password(password)
    if role not in {"operador", "admin"}:
        raise ValueError("O perfil selecionado não é válido.")
    password_hash = hash_password(password)
    with closing(_connect()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _require_admin(connection, actor_id)
        try:
            cursor = connection.execute(
                """INSERT INTO users
                   (email, password_hash, full_name, role, is_active,
                    must_change_password, created_at)
                         VALUES (?, ?, ?, ?, 1, 1, ?) RETURNING id""",
                (
                    normalized_email,
                    password_hash,
                    validated_name,
                    role,
                    now_brasilia_iso(),
                ),
            )
        except IntegrityError as error:
            connection.rollback()
            raise ValueError("Esse e-mail já possui uma conta.") from error
        user_id = cursor.fetchone()[0]
        connection.commit()
        return user_id


def update_user_access(user_id, role, is_active, actor_id):
    if role not in {"operador", "admin"}:
        raise ValueError("O perfil selecionado não é válido.")
    with closing(_connect()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _require_admin(connection, actor_id)
        target = connection.execute(
            "SELECT role, is_active FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if target is None:
            connection.rollback()
            raise ValueError("A conta selecionada não existe.")
        if user_id == actor_id and (role != "admin" or not is_active):
            connection.rollback()
            raise ValueError(
                "Você não pode remover ou desativar sua própria conta administradora."
            )
        removes_active_admin = (
            target["role"] == "admin"
            and target["is_active"]
            and (role != "admin" or not is_active)
        )
        if removes_active_admin:
            active_admins = connection.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1"
            ).fetchone()[0]
            if active_admins <= 1:
                connection.rollback()
                raise ValueError(
                    "Mantenha pelo menos um administrador ativo na plataforma."
                )
        connection.execute(
            "UPDATE users SET role = ?, is_active = ? WHERE id = ?",
            (role, int(is_active), user_id),
        )
        connection.commit()


def reset_user_password(user_id, temporary_password, actor_id):
    validate_password(temporary_password)
    password_hash = hash_password(temporary_password)
    with closing(_connect()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _require_admin(connection, actor_id)
        row = connection.execute(
            "SELECT email FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            connection.rollback()
            raise ValueError("A conta selecionada não existe.")
        connection.execute(
            """UPDATE users
               SET password_hash = ?, must_change_password = 1
               WHERE id = ?""",
            (password_hash, user_id),
        )
        connection.execute(
            "DELETE FROM login_attempts WHERE email = ?",
            (row["email"],),
        )
        connection.commit()


_DUMMY_PASSWORD_HASH = (
    "scrypt$2e2b7d3ff5d7e1f82291a2c7b91ad4d2$"
    "b879a4fc5065c9228d8c8a1d527ea13241b8eb980a44828302fa1b0f885144f"
)
