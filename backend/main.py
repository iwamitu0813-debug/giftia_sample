# main.py — Giftia 検索API（22班 さんこいち）
# 2週目の検索APIに、次の3つを足した。
#   ① 入口    ：贈る相手（recipient）と贈る機会（purpose）を受け取る
#   ② 順位付け：その相手 × 機会の実績がある商品を上に並べ、理由を件数で返す（ranking.py）
#   ③ 贈った後：メッセージカード、受け取った人の返信、次の機会の案内（local_store.py / occasions.py）
# 班のDB（Azure MySQL）は SELECT で読むだけ。新しく貯めるデータは、このPCの SQLite ファイルに置く。
#
# 起動：uvicorn main:app --reload
# 確認：http://localhost:8000/docs

import os
import re
from datetime import date
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import local_store
from database import fetch_all
from occasions import build_suggestions
from ranking import PURPOSES, RECIPIENTS, rank_products, sort_rule_text

load_dotenv()

app = FastAPI(title="Giftia API（22班 さんこいち）")

origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["*"])

RecipientKey = Literal["", "mother", "father", "family", "friend", "coworker", "client", "annual"]
PurposeKey = Literal["", "誕生日", "母の日", "父の日", "お中元", "お歳暮", "お礼", "送別", "結婚祝い", "出産祝い"]
RELATIONS = ["母", "父", "配偶者", "子", "きょうだい", "祖父母", "友人", "職場の人", "取引先", "その他"]
PERSONAS = [  # 班のDBに入っている、ケースの顧客A〜Eにあたる会員（デモ用）
    {"userId": "U-PERSONA-A", "label": "Aさん（先輩への送別）"},
    {"userId": "U-PERSONA-B", "label": "Bさん（友人への誕生日）"},
    {"userId": "U-PERSONA-C", "label": "Cさん（取引先へのお礼）"},
    {"userId": "U-PERSONA-D", "label": "Dさん（母への誕生日）"},
    {"userId": "U-PERSONA-E", "label": "Eさん（お中元・お歳暮）"},
]

# 班のDBの集計は重いので、同じ条件の結果はプロセスの中で覚えておく（注文とレビューは開発中に変わらない）
_cache: dict = {}


@app.get("/api/health")
def health():
    row = fetch_all("SELECT DATABASE() AS db, COUNT(*) AS products FROM products")[0]
    return {"status": "ok", "db": row["db"], "products": row["products"]}


@app.get("/api/options")
def options():
    """画面のプルダウンに出す選択肢。画面とAPIで同じ一覧を使うため、APIから配る"""
    return {
        "recipients": [{"key": k, "label": v["label"]} for k, v in RECIPIENTS.items()],
        "purposes": PURPOSES,
        "relations": RELATIONS,
        "personas": PERSONAS,
    }


# ── ② 順位付けに使う実績（班のDBから読む） ─────────────────────────
def chosen_counts(group: str, purpose: str) -> dict[str, int]:
    """商品ID → その相手の区分 × 機会で選ばれた注文の件数"""
    key = ("chosen", group, purpose)
    if key not in _cache:
        where, params = [], []
        if group:
            where.append("o.estimated_scene = %s"); params.append(group)
        if purpose:
            where.append("o.gift_purpose = %s"); params.append(purpose)
        rows = fetch_all(
            f"""SELECT oi.product_id, COUNT(*) AS n
                FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
                WHERE {' AND '.join(where)}
                GROUP BY oi.product_id""",
            tuple(params),
        )
        _cache[key] = {r["product_id"]: int(r["n"]) for r in rows}
    return _cache[key]


def review_text_column() -> str:
    """reviews の本文の列名を調べる（列名を決め打ちにしない）。見つからなければ空文字"""
    if "review_col" not in _cache:
        name = ""
        try:
            for c in fetch_all("SHOW COLUMNS FROM reviews"):
                typ = str(c["Type"]).lower()
                long_varchar = (m := re.match(r"varchar\((\d+)\)", typ)) and int(m.group(1)) >= 200
                if ("text" in typ or long_varchar) and re.fullmatch(r"[A-Za-z0-9_]+", c["Field"]):
                    name = c["Field"]
                    break
        except Exception:
            name = ""
        _cache["review_col"] = name
    return _cache["review_col"]


def voice_counts(recipient: str) -> dict[str, int]:
    """商品ID → その相手に贈ったと書かれたレビューの件数（「母」を含み、「祖母」などを含まない）"""
    key = ("voice", recipient)
    if key not in _cache:
        spec, col = RECIPIENTS[recipient], review_text_column()
        counts: dict[str, int] = {}
        if spec["words"] and col:
            hit = " OR ".join([f"`{col}` LIKE %s"] * len(spec["words"]))
            miss = "".join([f" AND `{col}` NOT LIKE %s"] * len(spec["exclude"]))
            params = [f"%{w}%" for w in spec["words"]] + [f"%{w}%" for w in spec["exclude"]]
            try:
                rows = fetch_all(f"SELECT product_id, COUNT(*) AS n FROM reviews WHERE ({hit}){miss} GROUP BY product_id", tuple(params))
                counts = {r["product_id"]: int(r["n"]) for r in rows}
            except Exception:
                counts = {}  # レビューから取れなくても、検索は止めない（注文の実績と人気順で並べる）
        _cache[key] = counts
    return _cache[key]


# ── ① 入口 ＋ ② 順位付け ───────────────────────────────────
@app.get("/api/search")
def search(
    recipient: RecipientKey = Query(default="", description="贈る相手（空なら指定なし）"),
    purpose: PurposeKey = Query(default="", description="贈る機会（空なら指定なし）"),
    q: str = Query(default="", max_length=100, description="キーワード（空白区切りで複数。すべてを含む商品）"),
    price_min: int | None = Query(default=None, ge=0, description="価格の下限（以上）"),
    price_max: int | None = Query(default=None, ge=0, description="価格の上限（以下）"),
    limit: int = Query(default=20, ge=1, le=100, description="返す件数"),
):
    """条件に合う商品を、その相手 × 機会の実績がある順に返す。相手も機会も空なら、いままでの人気順"""
    # 候補を取る。機会を選んだときは、その機会のタグ（product_scenes）を持つ商品に絞る。相手では絞らない（候補が減りすぎるため）
    join, where, params = "", ["p.stock > 0"], []
    if purpose:
        join = "JOIN product_scenes ps ON ps.product_id = p.product_id AND ps.scene_tag = %s"
        params.append(purpose)
    for word in q.split():
        where.append("(p.product_name LIKE %s OR p.brand LIKE %s OR p.description LIKE %s)")
        params += [f"%{word}%"] * 3
    if price_min is not None:
        where.append("p.price >= %s"); params.append(price_min)
    if price_max is not None:
        where.append("p.price <= %s"); params.append(price_max)
    rows = fetch_all(
        f"""SELECT p.product_id, p.category, p.brand, p.product_name, p.price, p.rating, p.review_count, p.sales_count
            FROM products p {join}
            WHERE {' AND '.join(where)}""",
        tuple(params),
    )

    # 実績を付けて並べる
    group = RECIPIENTS[recipient]["group"] if recipient else ""
    chosen = chosen_counts(group, purpose) if (recipient or purpose) else {}
    voice = voice_counts(recipient) if recipient else {}
    used = local_store.used_counts(recipient, purpose) if (recipient or purpose) else {}
    ranked = rank_products(rows, chosen, voice, used, recipient, purpose, limit)

    return {
        "total": len(rows),
        "sortRule": sort_rule_text(recipient, purpose),
        "evidenceCount": ranked["evidence_in_top"],  # 上位のうち、実績のある商品の数。ここから下は人気順
        "results": [to_gift(x["row"], x["reasons"]) for x in ranked["items"]],
    }


def to_gift(r: dict, reasons: list[dict]) -> dict:
    return {
        "id": r["product_id"], "category": r["category"], "brand": r["brand"], "name": r["product_name"],
        "price": r["price"], "rating": float(r["rating"]) if r["rating"] is not None else 0,
        "reviewCount": r["review_count"], "reasons": reasons,
    }


# ── ③ 贈った後：メッセージカードと返信 ──────────────────────────
USER_ID = r"^U-[A-Za-z0-9-]{1,40}$"


class CardIn(BaseModel):
    userId: str = Field(pattern=USER_ID)
    productId: str = Field(pattern=r"^[A-Za-z0-9_-]{1,20}$")
    recipient: RecipientKey
    purpose: PurposeKey
    senderName: str = Field(min_length=1, max_length=30)
    message: str = Field(min_length=1, max_length=300)
    reason: Literal["相手の言葉や暮らしを思い出した", "実績の件数を見て", "価格が合った", "見た目が気に入った", "その他"]


@app.post("/api/cards")
def create_card(body: CardIn):
    """商品を贈るときにメッセージカードを作る。返信用のコードを返す（カードに印刷するQRコードの中身）"""
    rows = fetch_all("SELECT product_name FROM products WHERE product_id = %s", (body.productId,))
    if not rows:
        raise HTTPException(404, "商品が見つかりません")
    code = local_store.create_card(body.userId, body.productId, rows[0]["product_name"], body.recipient,
                                   body.purpose, body.senderName, body.message, body.reason)
    return {"code": code}


@app.get("/api/cards")
def list_cards(user_id: str = Query(pattern=USER_ID)):
    """贈り主が見る一覧。お礼の言葉は見える。星とコメントは見えない"""
    return {"cards": local_store.cards_of(user_id)}


@app.get("/api/cards/{code}")
def get_card(code: str):
    """受け取った人が見る画面用。価格は返さない"""
    card = local_store.get_card(code)
    if not card:
        raise HTTPException(404, "カードが見つかりません")
    return {"senderName": card["sender_name"], "message": card["message"], "productName": card["product_name"],
            "replied": bool(card["replied"])}


class ReplyIn(BaseModel):
    thanks: str = Field(min_length=1, max_length=300)
    inUse: Literal["using", "not_yet", "not_using"]
    shareUse: bool = False               # 「使っています」を贈り主にも伝えるか（受け取った人が選ぶ）
    stars: int | None = Field(default=None, ge=1, le=5)  # 贈り主には見せない
    comment: str = Field(default="", max_length=300)     # 贈り主には見せない


@app.post("/api/cards/{code}/reply")
def reply(code: str, body: ReplyIn):
    if not local_store.get_card(code):
        raise HTTPException(404, "カードが見つかりません")
    if not local_store.save_reply(code, body.thanks, body.inUse, body.shareUse, body.stars, body.comment):
        raise HTTPException(409, "このカードには、すでに返信があります")
    return {"status": "ok"}


# ── ③ 贈った後：次の機会の案内 ──────────────────────────────
class RelationIn(BaseModel):
    userId: str = Field(pattern=USER_ID)
    recipientKey: str = Field(pattern=r"^rcp_[A-Za-z0-9]{1,40}$")
    relation: Literal["母", "父", "配偶者", "子", "きょうだい", "祖父母", "友人", "職場の人", "取引先", "その他"]


@app.post("/api/relations")
def set_relation(body: RelationIn):
    """相手との関係を一度だけ聞いて覚える（班のDBには関係が入っていないため）"""
    local_store.set_relation(body.userId, body.recipientKey, body.relation)
    return {"status": "ok"}


@app.get("/api/next")
def next_occasions(
    user_id: str = Query(pattern=USER_ID),
    today: date | None = Query(default=None, description="デモ用：この日を今日として案内を作る（例 2027-04-05）"),
):
    """会員の注文の履歴から、次の機会の案内を作る"""
    orders = fetch_all(
        """SELECT o.recipient_key, o.gift_purpose, o.estimated_scene, o.ordered_at, p.product_id, p.product_name
           FROM orders o
           JOIN order_items oi ON oi.order_id = o.order_id
           JOIN products p ON p.product_id = oi.product_id
           WHERE o.user_id = %s
           ORDER BY o.ordered_at""",
        (user_id,),
    )
    base = today or date.today()
    return {
        "today": base.isoformat(),
        "suggestions": build_suggestions(orders, local_store.relations_of(user_id), local_store.shared_use_of(user_id), base),
    }
