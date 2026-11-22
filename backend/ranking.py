# ranking.py — 候補の並べ方と、理由（根拠）の作り方。DB に触らない純粋な関数だけを置く（テストしやすくするため）
#
# 並び順（上から順に比べる。同じ入力なら必ず同じ順になる）
#   1. used_n   受け取った人の「使っています」の件数（このアプリで貯め始めるデータ。3件以上で使う）
#   2. voice_n  その相手に贈ったと書かれたレビューの件数（班のDBの reviews）
#   3. chosen_n その相手の区分 × 機会で選ばれた注文の件数（班のDBの orders）
#   4. sales    販売数（いままでの人気順）
#   5. id       商品ID（最後の決め手。順位がぶれないようにする）

MIN_USED_PUBLIC = 3  # 受け手の反応は、この件数に届くまで順位にも表示にも使わない（1件だと誰の評価か分かってしまう）

# 贈る相手の選択肢。group は班のDBの orders.estimated_scene の値（相手の区分として使う）
RECIPIENTS: dict[str, dict] = {
    "mother":   {"label": "母",           "group": "家族への誕生日",           "group_label": "家族",       "words": ["母"],           "exclude": ["祖母", "叔母", "伯母"]},
    "father":   {"label": "父",           "group": "家族への誕生日",           "group_label": "家族",       "words": ["父"],           "exclude": ["祖父", "叔父", "伯父"]},
    "family":   {"label": "家族（ほか）", "group": "家族への誕生日",           "group_label": "家族",       "words": [],               "exclude": []},
    "friend":   {"label": "友人",         "group": "友人への誕生日",           "group_label": "友人",       "words": ["友人", "友達"], "exclude": []},
    "coworker": {"label": "職場の人",     "group": "送別",                     "group_label": "職場の人",   "words": ["同僚", "先輩"], "exclude": []},
    "client":   {"label": "取引先",       "group": "ビジネスのお礼",           "group_label": "取引先",     "words": ["取引先"],       "exclude": []},
    "annual":   {"label": "毎年贈る相手", "group": "毎年決まった相手への贈答", "group_label": "毎年の相手", "words": [],               "exclude": []},
}

# 贈る機会の選択肢。班のDBの product_scenes.scene_tag / orders.gift_purpose と同じ9種
PURPOSES = ["誕生日", "母の日", "父の日", "お中元", "お歳暮", "お礼", "送別", "結婚祝い", "出産祝い"]


def sort_rule_text(recipient: str, purpose: str) -> str:
    """結果の上に出す「並び順」の説明。順位付けの第一キーから順に書く"""
    if not recipient and not purpose:
        return "並び順：人気順（販売数）"
    who = RECIPIENTS[recipient]["label"] if recipient else ""
    parts = ["受け取った人の「使っています」の件数"]
    if recipient and RECIPIENTS[recipient]["words"]:
        parts.append(f"{who}に贈ったというレビューの件数")
    parts.append(f"{scope_label(recipient, purpose)}で選ばれた件数")
    parts.append("人気順（販売数）")
    return "並び順：" + " → ".join(parts)


def scope_label(recipient: str, purpose: str) -> str:
    """「家族 × 誕生日」のような、注文実績の範囲の呼び名"""
    group = RECIPIENTS[recipient]["group_label"] if recipient else ""
    return " × ".join(x for x in [group, purpose] if x)


def rank_products(rows: list[dict], chosen: dict[str, int], voice: dict[str, int],
                  used: dict[str, dict], recipient: str, purpose: str, limit: int) -> dict:
    """候補（rows）に実績を付けて並べ、上位 limit 件と、実績ありの件数（区切りの位置）を返す"""
    who = RECIPIENTS[recipient]["label"] if recipient else ""
    scope = scope_label(recipient, purpose)
    items = []
    for r in rows:
        pid = r["product_id"]
        u = used.get(pid, {"n": 0, "test": False})
        used_n = u["n"] if u["n"] >= MIN_USED_PUBLIC else 0
        voice_n = voice.get(pid, 0)
        chosen_n = chosen.get(pid, 0)
        reasons = []  # 順位を決めた順に並べる（第一キーがカードの先頭に出る）
        if used_n:
            reasons.append({"kind": "used", "label": f"受け取った人の「使っています」 {used_n}件", "count": used_n, "isTest": bool(u["test"])})
        if voice_n:
            reasons.append({"kind": "voice", "label": f"{who}に贈ったというレビュー {voice_n}件", "count": voice_n, "isTest": False})
        if chosen_n:
            reasons.append({"kind": "chosen", "label": f"{scope}で選ばれた {chosen_n}件", "count": chosen_n, "isTest": False})
        items.append({"row": r, "key": (-used_n, -voice_n, -chosen_n, -(r.get("sales_count") or 0), pid), "reasons": reasons})
    items.sort(key=lambda x: x["key"])
    evidence_total = sum(1 for x in items if x["reasons"])
    top = items[:limit]
    return {"items": top, "evidence_in_top": sum(1 for x in top if x["reasons"]), "evidence_total": evidence_total}
