# local_store.py — このアプリで新しく貯めるデータの置き場所（このPCの中の SQLite ファイル）
#
# 班のDB（Azure MySQL）は読むだけにして、書き込みはすべてここに行う。
#   gift_cards          メッセージカード（誰が・どの商品を・誰に・何の機会で・選んだ理由）
#   gift_replies        受け取った人の返信（お礼の言葉、使っているか、星）
#   recipient_relations 相手との関係（一度だけ聞いて覚える）
# is_test = 1 は、seed_demo.py で入れたテスト用のデータ。画面でも「テスト用」と表示する。

import os
import secrets
import sqlite3
from datetime import datetime

DB_PATH = os.environ.get("LOCAL_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "giftia_local.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS gift_cards (
  code TEXT PRIMARY KEY, user_id TEXT NOT NULL, product_id TEXT NOT NULL, product_name TEXT NOT NULL,
  recipient TEXT NOT NULL, purpose TEXT NOT NULL, sender_name TEXT NOT NULL, message TEXT NOT NULL,
  reason TEXT NOT NULL, is_test INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS gift_replies (
  code TEXT PRIMARY KEY REFERENCES gift_cards(code), thanks TEXT NOT NULL, in_use TEXT NOT NULL,
  share_use INTEGER NOT NULL DEFAULT 0, stars INTEGER, comment TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS recipient_relations (
  user_id TEXT NOT NULL, recipient_key TEXT NOT NULL, relation TEXT NOT NULL, updated_at TEXT NOT NULL,
  PRIMARY KEY (user_id, recipient_key));
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create_card(user_id, product_id, product_name, recipient, purpose, sender_name, message, reason, is_test=0) -> str:
    code = secrets.token_urlsafe(6)
    with connect() as c:
        c.execute("INSERT INTO gift_cards VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (code, user_id, product_id, product_name, recipient, purpose, sender_name, message, reason, is_test, now()))
    return code


def get_card(code: str) -> dict | None:
    with connect() as c:
        row = c.execute("""SELECT g.*, r.code IS NOT NULL AS replied FROM gift_cards g
                           LEFT JOIN gift_replies r ON r.code = g.code WHERE g.code = ?""", (code,)).fetchone()
    return dict(row) if row else None


def save_reply(code, thanks, in_use, share_use, stars, comment) -> bool:
    """返信を保存する。同じカードへの返信は1回だけ（2回目は False）"""
    with connect() as c:
        if c.execute("SELECT 1 FROM gift_replies WHERE code = ?", (code,)).fetchone():
            return False
        c.execute("INSERT INTO gift_replies VALUES (?,?,?,?,?,?,?)", (code, thanks, in_use, int(share_use), stars, comment, now()))
    return True


def cards_of(user_id: str) -> list[dict]:
    """贈り主に見せる一覧。星とコメントは返さない。「使っています」は受け手が伝えると選んだときだけ返す"""
    with connect() as c:
        rows = c.execute("""SELECT g.code, g.product_id, g.product_name, g.recipient, g.purpose, g.message, g.reason, g.created_at,
                                   r.thanks, r.created_at AS replied_at,
                                   CASE WHEN r.share_use = 1 THEN r.in_use END AS shared_in_use
                            FROM gift_cards g LEFT JOIN gift_replies r ON r.code = g.code
                            WHERE g.user_id = ? AND g.is_test = 0 ORDER BY g.created_at DESC""", (user_id,)).fetchall()
    return [dict(r) for r in rows]


def used_counts(recipient: str, purpose: str) -> dict[str, dict]:
    """商品ID → {n: 「使っています」の件数, test: テスト用データを含むか}。相手と機会が同じカードだけ数える"""
    where, params = ["r.in_use = 'using'"], []
    if recipient:
        where.append("g.recipient = ?"); params.append(recipient)
    if purpose:
        where.append("g.purpose = ?"); params.append(purpose)
    with connect() as c:
        rows = c.execute(f"""SELECT g.product_id, COUNT(*) AS n, MAX(g.is_test) AS test FROM gift_replies r
                             JOIN gift_cards g ON g.code = r.code WHERE {' AND '.join(where)} GROUP BY g.product_id""", params).fetchall()
    return {r["product_id"]: {"n": r["n"], "test": bool(r["test"])} for r in rows}


def shared_use_of(user_id: str) -> dict[str, bool]:
    """商品ID → 受け手が「使っています」を贈り主に伝えたか（次の機会の案内に添える）"""
    with connect() as c:
        rows = c.execute("""SELECT g.product_id FROM gift_cards g JOIN gift_replies r ON r.code = g.code
                            WHERE g.user_id = ? AND r.share_use = 1 AND r.in_use = 'using'""", (user_id,)).fetchall()
    return {r["product_id"]: True for r in rows}


def relations_of(user_id: str) -> dict[str, str]:
    with connect() as c:
        rows = c.execute("SELECT recipient_key, relation FROM recipient_relations WHERE user_id = ?", (user_id,)).fetchall()
    return {r["recipient_key"]: r["relation"] for r in rows}


def set_relation(user_id: str, recipient_key: str, relation: str) -> None:
    with connect() as c:
        c.execute("""INSERT INTO recipient_relations VALUES (?,?,?,?)
                     ON CONFLICT(user_id, recipient_key) DO UPDATE SET relation = excluded.relation, updated_at = excluded.updated_at""",
                  (user_id, recipient_key, relation, now()))
