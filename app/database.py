import sqlite3
import os
import hashlib
import secrets
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "/data/kvm_manager.db")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True) if os.path.dirname(DB_PATH) else None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def hash_password(password: str) -> str:
    salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"


def verify_password(password: str, hashed: str) -> bool:
    salt, h = hashed.split(":", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == h


def init_db():
    conn = _get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS vm_ownership (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vm_name TEXT UNIQUE NOT NULL,
                owner_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_vm_owner ON vm_ownership(owner_id);
            CREATE INDEX IF NOT EXISTS idx_vm_name ON vm_ownership(vm_name);
        """)

        # Add email column if missing (migration)
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)")]
        if "email" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT UNIQUE")

        # Create default admin if not exists
        cur = conn.execute("SELECT id FROM users WHERE username = ?", ("admin",))
        if not cur.fetchone():
            pw = hash_password(os.getenv("API_PASSWORD", "admin"))
            conn.execute(
                "INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, 1)",
                ("admin", "admin@localhost", pw),
            )
            logger.info("Created default admin user")

        conn.commit()
    finally:
        conn.close()


def get_user_by_username(username: str) -> dict | None:
    conn = _get_conn()
    try:
        cur = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_login(login: str) -> dict | None:
    conn = _get_conn()
    try:
        cur = conn.execute("SELECT * FROM users WHERE username = ? OR email = ?", (login, login))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> dict | None:
    conn = _get_conn()
    try:
        cur = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_user(username: str, password: str, is_admin: bool = False, email: str = None) -> dict:
    conn = _get_conn()
    try:
        pw = hash_password(password)
        cur = conn.execute(
            "INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)",
            (username, email, pw, 1 if is_admin else 0),
        )
        conn.commit()
        return {"id": cur.lastrowid, "username": username, "email": email, "is_admin": is_admin}
    except sqlite3.IntegrityError:
        raise ValueError(f"User '{username}' already exists")
    finally:
        conn.close()


def list_users() -> list[dict]:
    conn = _get_conn()
    try:
        cur = conn.execute("SELECT id, username, email, is_admin, created_at FROM users ORDER BY id")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def set_vm_owner(vm_name: str, owner_id: int) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO vm_ownership (vm_name, owner_id) VALUES (?, ?)",
            (vm_name, owner_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_vm_owner(vm_name: str) -> dict | None:
    conn = _get_conn()
    try:
        cur = conn.execute(
            """SELECT u.id, u.username, v.vm_name
               FROM vm_ownership v JOIN users u ON v.owner_id = u.id
               WHERE v.vm_name = ?""",
            (vm_name,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_vms_for_user(owner_id: int) -> list[str]:
    conn = _get_conn()
    try:
        cur = conn.execute(
            "SELECT vm_name FROM vm_ownership WHERE owner_id = ?",
            (owner_id,),
        )
        return [r["vm_name"] for r in cur.fetchall()]
    finally:
        conn.close()


def delete_vm_ownership(vm_name: str) -> None:
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM vm_ownership WHERE vm_name = ?", (vm_name,))
        conn.commit()
    finally:
        conn.close()
