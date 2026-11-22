# test_app.py — 班のDBにつながずに、並び順・案内のルール・APIの流れを確かめる（pytest）
# 実行：python -m pytest -q
import os, tempfile
from datetime import date, datetime

os.environ["LOCAL_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

import local_store
import main
from fastapi.testclient import TestClient
from occasions import build_suggestions, nth_sunday
from ranking import rank_products, sort_rule_text

ROWS = [
    {"product_id": "G1", "category": "家電", "brand": "A", "product_name": "ケトル", "price": 5980, "rating": 4.5, "review_count": 10, "sales_count": 50, "description": ""},
    {"product_id": "G2", "category": "食品", "brand": "B", "product_name": "焼き菓子", "price": 3980, "rating": 4.2, "review_count": 80, "sales_count": 900, "description": ""},
    {"product_id": "G3", "category": "雑貨", "brand": "C", "product_name": "タオル", "price": 4400, "rating": 4.0, "review_count": 5, "sales_count": 300, "description": ""},
    {"product_id": "G4", "category": "雑貨", "brand": "D", "product_name": "花瓶", "price": 4000, "rating": 4.0, "review_count": 5, "sales_count": 300, "description": ""},
]


def test_rank_order_and_reasons():
    r = rank_products(ROWS, chosen={"G2": 40, "G3": 40}, voice={"G1": 2}, used={}, recipient="mother", purpose="誕生日", limit=10)
    assert [x["row"]["product_id"] for x in r["items"]] == ["G1", "G2", "G3", "G4"]  # レビュー → 選ばれた件数 → 販売数 → ID
    assert r["items"][0]["reasons"][0]["label"] == "母に贈ったというレビュー 2件"
    assert r["items"][1]["reasons"][0]["label"] == "家族 × 誕生日で選ばれた 40件"
    assert r["items"][3]["reasons"] == [] and r["evidence_in_top"] == 3


def test_used_needs_three():
    two = rank_products(ROWS, {}, {}, {"G4": {"n": 2, "test": False}}, "mother", "誕生日", 10)
    assert two["items"][0]["row"]["product_id"] == "G2"  # 2件では使わない → 人気順
    three = rank_products(ROWS, {}, {}, {"G4": {"n": 3, "test": True}}, "mother", "誕生日", 10)
    assert three["items"][0]["row"]["product_id"] == "G4" and three["items"][0]["reasons"][0]["isTest"] is True


def test_sort_rule_text():
    assert sort_rule_text("", "") == "並び順：人気順（販売数）"
    assert "家族 × 誕生日で選ばれた件数" in sort_rule_text("mother", "誕生日")


def test_holidays():
    assert nth_sunday(2027, 5, 2) == date(2027, 5, 9) and nth_sunday(2027, 6, 3) == date(2027, 6, 20)


def test_d_birthday_reminder_and_gap_rule():
    orders = [{"recipient_key": "rcp_m", "gift_purpose": "誕生日", "estimated_scene": "家族への誕生日",
               "ordered_at": datetime(2026, 4, 22, 20, 55), "product_id": "G0567", "product_name": "電気ケトル"}]
    s = build_suggestions(orders, {}, {}, date(2026, 11, 21))
    assert len(s) == 1 and s[0]["nextDate"] == "2027-04-22" and s[0]["soon"] is False and s[0]["needsRelation"] is True
    s = build_suggestions(orders, {"rcp_m": "母"}, {"G0567": True}, date(2027, 4, 5))
    annual = [x for x in s if x["type"] == "annual"][0]
    cross = [x for x in s if x["type"] == "cross"][0]
    assert annual["soon"] is True and annual["usedShared"] is True
    assert cross["purpose"] == "母の日" and cross["suppressed"] is True  # 誕生日(4/22)と母の日(5/9)は17日差 → 案内しない


def test_e_seasonal_same_product():
    orders = []
    for y in (2024, 2025):
        orders.append({"recipient_key": "rcp_a", "gift_purpose": "お歳暮", "estimated_scene": "毎年決まった相手への贈答",
                       "ordered_at": datetime(y, 12, 5), "product_id": "G9", "product_name": "ビール"})
    s = build_suggestions(orders, {}, {}, date(2026, 11, 21))
    assert s[0]["nextDate"] == "2026-12-05" and s[0]["soon"] is True and s[0]["sameAsBefore"] is True and s[0]["times"] == 2


def fake_fetch_all(query, params=()):
    q = " ".join(query.split())
    if q.startswith("SHOW COLUMNS"):
        return [{"Field": "review_id", "Type": "varchar(20)"}, {"Field": "body", "Type": "text"}]
    if "FROM reviews" in q:
        assert params == ("%母%", "%祖母%", "%叔母%", "%伯母%")
        return [{"product_id": "G1", "n": 2}]
    if "FROM orders o JOIN order_items" in q and "GROUP BY oi.product_id" in q:
        assert params == ("家族への誕生日", "誕生日")
        return [{"product_id": "G2", "n": 40}]
    if "FROM products p" in q:
        assert "JOIN product_scenes" in q and params[0] == "誕生日"
        return ROWS
    if "SELECT product_name FROM products" in q:
        return [{"product_name": "ケトル"}] if params == ("G1",) else []
    if "WHERE o.user_id" in q:
        return [{"recipient_key": "rcp_m", "gift_purpose": "誕生日", "estimated_scene": "家族への誕生日",
                 "ordered_at": datetime(2026, 4, 22), "product_id": "G1", "product_name": "ケトル"}]
    raise AssertionError(q)


def test_api_flow(monkeypatch):
    monkeypatch.setattr(main, "fetch_all", fake_fetch_all)
    main._cache.clear()
    c = TestClient(main.app)

    r = c.get("/api/search", params={"recipient": "mother", "purpose": "誕生日"}).json()
    assert [g["id"] for g in r["results"]] == ["G1", "G2", "G3", "G4"] and r["evidenceCount"] == 2
    assert c.get("/api/search", params={"recipient": "boss"}).status_code == 422  # 選択肢にない値は入力エラー

    card = {"userId": "U-PERSONA-D", "productId": "G1", "recipient": "mother", "purpose": "誕生日",
            "senderName": "D", "message": "おめでとう", "reason": "相手の言葉や暮らしを思い出した"}
    code = c.post("/api/cards", json=card).json()["code"]
    assert c.post("/api/cards", json={**card, "productId": "G9"}).status_code == 404
    seen = c.get(f"/api/cards/{code}").json()
    assert seen == {"senderName": "D", "message": "おめでとう", "productName": "ケトル", "replied": False}  # 価格は出ない

    reply = {"thanks": "毎朝使っています", "inUse": "using", "shareUse": True, "stars": 5, "comment": "軽い"}
    assert c.post(f"/api/cards/{code}/reply", json=reply).status_code == 200
    assert c.post(f"/api/cards/{code}/reply", json=reply).status_code == 409  # 返信は1回だけ
    mine = c.get("/api/cards", params={"user_id": "U-PERSONA-D"}).json()["cards"][0]
    assert mine["thanks"] == "毎朝使っています" and mine["shared_in_use"] == "using"
    assert "stars" not in mine and "comment" not in mine  # 星とコメントは贈り主に見せない

    assert c.post("/api/relations", json={"userId": "U-PERSONA-D", "recipientKey": "rcp_m", "relation": "母"}).status_code == 200
    nxt = c.get("/api/next", params={"user_id": "U-PERSONA-D", "today": "2027-04-05"}).json()["suggestions"]
    assert nxt[0]["purpose"] == "誕生日" and nxt[0]["usedShared"] is True and nxt[0]["soon"] is True
    assert c.get("/api/next", params={"user_id": "x; DROP"}).status_code == 422
