# occasions.py — 「次の機会の案内」を、注文の履歴から作る。DB に触らない純粋な関数だけを置く
#
# ルール
#   ・毎年の機会（誕生日・母の日・父の日・お中元・お歳暮）は、前回の注文をもとに次の時期を出す
#   ・案内は、その日の NOTICE_DAYS 日前から「そろそろ」と表示する
#   ・相手との関係が母／父と分かっていて、母の日／父の日をまだ贈っていなければ、別の機会として提案する
#   ・ただし、いつもの機会から MIN_GAP_DAYS 日以内の機会は案内しない（短い間に2回の贈り物は負担になる）

from datetime import date, datetime, timedelta

NOTICE_DAYS = 21   # 何日前から「そろそろ」と出すか
MIN_GAP_DAYS = 30  # これより近い別の機会は案内しない

ANNUAL = {"誕生日", "母の日", "父の日", "お中元", "お歳暮"}
CROSS = {"母": "母の日", "父": "父の日"}  # 関係 → 提案する別の機会


def nth_sunday(year: int, month: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)  # その月の最初の日曜
    return d + timedelta(weeks=n - 1)


def holiday(purpose: str, year: int) -> date | None:
    if purpose == "母の日":
        return nth_sunday(year, 5, 2)  # 5月の第2日曜
    if purpose == "父の日":
        return nth_sunday(year, 6, 3)  # 6月の第3日曜
    return None


def next_occurrence(purpose: str, last: date, today: date) -> date:
    """次にその機会が来る日。母の日・父の日は暦の日、ほかは前回の注文と同じ月日"""
    for year in (today.year, today.year + 1):
        h = holiday(purpose, year)
        if h is None:
            try:
                h = last.replace(year=year)
            except ValueError:  # 2月29日
                h = date(year, 2, 28)
        if h >= today:
            return h
    return h


def _d(v) -> date:
    return v.date() if isinstance(v, datetime) else v


def build_suggestions(orders: list[dict], relations: dict[str, str], shared_use: dict[str, bool], today: date) -> list[dict]:
    """orders: 注文明細（recipient_key, gift_purpose, estimated_scene, ordered_at, product_id, product_name）
    relations: 相手の匿名ID → 関係（母・父・友人 など。一度だけ聞いてローカルに保存したもの）
    shared_use: 商品ID → 受け手が「使っています」を贈り主に伝えたか"""
    by_rcp: dict[str, list[dict]] = {}
    for o in orders:
        if o.get("recipient_key"):
            by_rcp.setdefault(o["recipient_key"], []).append(o)

    out = []
    for rcp, rows in by_rcp.items():
        rows.sort(key=lambda r: r["ordered_at"])
        relation = relations.get(rcp, "")
        purposes = {r["gift_purpose"] for r in rows if r.get("gift_purpose")}
        anchors: list[date] = []  # この相手の「いつもの機会」の次の日付

        for p in sorted(purposes & ANNUAL):
            same = [r for r in rows if r["gift_purpose"] == p]
            last = same[-1]
            nxt = next_occurrence(p, _d(last["ordered_at"]), today)
            anchors.append(nxt)
            names = [r["product_name"] for r in same]
            out.append({
                "type": "annual", "recipientKey": rcp, "relation": relation, "purpose": p,
                "nextDate": nxt.isoformat(), "noticeFrom": (nxt - timedelta(days=NOTICE_DAYS)).isoformat(),
                "soon": today >= nxt - timedelta(days=NOTICE_DAYS),
                "lastDate": _d(last["ordered_at"]).isoformat(), "lastProductId": last["product_id"], "lastProductName": last["product_name"],
                "times": len(same), "sameAsBefore": len(same) >= 2 and names[-1] == names[-2],
                "usedShared": bool(shared_use.get(last["product_id"])),
                "needsRelation": not relation,
            })

        cross = CROSS.get(relation)
        if cross and cross not in purposes:
            nxt = next_occurrence(cross, today, today)
            near = [a for a in anchors if abs((date(nxt.year, a.month, min(a.day, 28)) - nxt).days) < MIN_GAP_DAYS]
            out.append({
                "type": "cross", "recipientKey": rcp, "relation": relation, "purpose": cross,
                "nextDate": nxt.isoformat(), "noticeFrom": (nxt - timedelta(days=NOTICE_DAYS)).isoformat(),
                "soon": False, "suppressed": bool(near),
                "note": (f"いつもの機会から{MIN_GAP_DAYS}日以内のため、案内しません" if near else "まだ贈っていない機会です"),
            })

    out.sort(key=lambda s: (s["nextDate"], s["recipientKey"], s["purpose"]))
    return out
