import sqlite3
import os
import time
import json
from contextlib import contextmanager

from app.config import DB_PATH


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                phone TEXT PRIMARY KEY,
                customer_name TEXT,
                ai_active INTEGER DEFAULT 1,
                last_human_reply_at REAL,
                created_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT,
                role TEXT,        -- 'user' or 'assistant'
                content TEXT,
                created_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sent_by_bot (
                message_id TEXT PRIMARY KEY,
                phone TEXT,
                text TEXT,
                created_at REAL
            )
        """)
        # Migration: older deployments may have this table without the "text" column.
        try:
            conn.execute("ALTER TABLE sent_by_bot ADD COLUMN text TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customer_info (
                phone TEXT PRIMARY KEY,
                name TEXT,
                interest TEXT,
                budget TEXT,
                notes TEXT,
                updated_at REAL
            )
        """)
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ---------- Chat state ----------

def get_or_create_chat(phone: str, customer_name: str = ""):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM chats WHERE phone = ?", (phone,)).fetchone()
        if row:
            return dict(row)
        conn.execute(
            "INSERT INTO chats (phone, customer_name, ai_active, created_at) VALUES (?, ?, 1, ?)",
            (phone, customer_name, time.time()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM chats WHERE phone = ?", (phone,)).fetchone()
        return dict(row)


def set_ai_active(phone: str, active: bool):
    with get_conn() as conn:
        conn.execute("UPDATE chats SET ai_active = ? WHERE phone = ?", (1 if active else 0, phone))
        conn.commit()


def mark_human_reply(phone: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE chats SET ai_active = 0, last_human_reply_at = ? WHERE phone = ?",
            (time.time(), phone),
        )
        conn.commit()


# ---------- Message history ----------

def add_message(phone: str, role: str, content: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (phone, role, content, created_at) VALUES (?, ?, ?, ?)",
            (phone, role, content, time.time()),
        )
        conn.commit()


def get_history(phone: str, limit: int = 20):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE phone = ? ORDER BY id DESC LIMIT ?",
            (phone, limit),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


# ---------- Bot-sent message tracking (this is the core of the handover logic) ----------

def record_bot_sent(message_id: str, phone: str, text: str = ""):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sent_by_bot (message_id, phone, text, created_at) VALUES (?, ?, ?, ?)",
            (message_id or f"noid-{time.time()}", phone, text, time.time()),
        )
        conn.commit()


def was_sent_by_bot(message_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM sent_by_bot WHERE message_id = ?", (message_id,)
        ).fetchone()
        return row is not None


def was_recently_sent_by_bot(phone: str, text: str, window_seconds: float = 45) -> bool:
    """
    More robust than ID matching: BotSpace's send-response id and the id that
    later appears in the outgoing webhook don't always match. Instead, check
    whether the bot sent this exact text to this exact number within the last
    `window_seconds` — if so, this outgoing webhook is just an echo of our own
    message, not a human agent reply.
    """
    cutoff = time.time() - window_seconds
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM sent_by_bot WHERE phone = ? AND text = ? AND created_at >= ?",
            (phone, text, cutoff),
        ).fetchone()
        return row is not None


# ---------- Customer info (mirrors what goes to Google Sheets) ----------

def upsert_customer_info(phone: str, name: str = None, interest: str = None,
                          budget: str = None, notes: str = None):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM customer_info WHERE phone = ?", (phone,)).fetchone()
        if row:
            data = dict(row)
            name = name or data["name"]
            interest = interest or data["interest"]
            budget = budget or data["budget"]
            notes = notes or data["notes"]
            conn.execute(
                "UPDATE customer_info SET name=?, interest=?, budget=?, notes=?, updated_at=? WHERE phone=?",
                (name, interest, budget, notes, time.time(), phone),
            )
        else:
            conn.execute(
                "INSERT INTO customer_info (phone, name, interest, budget, notes, updated_at) VALUES (?,?,?,?,?,?)",
                (phone, name, interest, budget, notes, time.time()),
            )
        conn.commit()
