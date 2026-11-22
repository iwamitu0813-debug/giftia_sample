# setup_concern_keywords.py — 対応表（concern_keywords）を班のDBに作る。1回だけ実行する
# 使い方（backend フォルダで、.venv を有効にしてから）：python setup_concern_keywords.py
# 接続情報は database.py が .env から読む（このファイルには書かない）。

from pathlib import Path

from database import fetch_all, get_connection

SQL_FILE = Path(__file__).parent / "sql" / "concern_keywords.sql"


def main():
    # コメント行を除き、; で区切って1文ずつ実行する
    text = "\n".join(line for line in SQL_FILE.read_text(encoding="utf-8").splitlines() if not line.strip().startswith("--"))
    statements = [s.strip() for s in text.split(";") if s.strip()]
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for s in statements:
                cur.execute(s)
        conn.commit()
    finally:
        conn.close()
    n = fetch_all("SELECT COUNT(*) AS n FROM concern_keywords")[0]["n"]
    print(f"concern_keywords の準備ができました（{n} 行）")


if __name__ == "__main__":
    main()
