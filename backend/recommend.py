# recommend.py — 母の手掛かりから、合う商品を5つ選んで理由を付ける（FR-02・04・05）
#
# 流れ（ケースの必須処理：入力 → 候補の取得 → 順位付け → 結果）
#   ① Q1の困りごと → 対応表（concern_keywords）から「探す言葉」を取り出す
#      Q1の「その他」（自由入力）→ AI で探す言葉に変換（AI が使えないときは、近い困りごとの言葉を使う）
#   ② Q2の自由入力 → AI で探す言葉に変換して足す
#   ③ 探す言葉のどれかを、商品名か説明書きに含む商品を集める
#   ④ Q3で「あまり使っていない」「合わなかった」なら、去年の品物に近い商品を外す
#   ⑤ 直近1年の販売数が多い順に並べて上から5件。足りなければ誕生日向けランキングで埋める
#   ⑥ 合う商品には理由を2行付ける。埋めた商品は「人気の商品です」

import time
from concurrent.futures import ThreadPoolExecutor

from ai_keywords import to_keywords
from database import fetch_all

LIMIT = 5                # 候補の数
FILL_SCENE = "誕生日"     # 足りないときに埋めるランキングのシーン（product_scenes.scene_tag）
AI_DEADLINE = 9.0        # AI を待つのは合計9秒まで（画面は最長10秒で必ず結果を出す）
BAD_RESULTS = {"あまり使っていない", "サイズや好みが合わなかった"}

COLUMNS = "p.product_id, p.category, p.brand, p.product_name, p.price, p.rating, p.review_count, p.description"


def get_concerns() -> list[dict]:
    """困りごとの一覧と、それぞれの探す言葉（画面の選択肢に使う）"""
    rows = fetch_all("SELECT concern_label, keyword FROM concern_keywords ORDER BY sort_order, id")
    concerns: dict[str, list[str]] = {}
    for r in rows:
        concerns.setdefault(r["concern_label"], []).append(r["keyword"])
    return [{"label": k, "keywords": v} for k, v in concerns.items()]


def recommend(concerns: list[str], hint: str = "", last_gift: str = "", last_result: str = "",
              concern_text: str = "") -> dict:
    # ① Q1：チェックした困りごと → 探す言葉（どの困りごとの言葉かも覚えておく。理由に使う）
    table = {c["label"]: c["keywords"] for c in get_concerns()}
    words: list[tuple[str, str]] = []  # (探す言葉, どこから来たか)
    for label in concerns:
        for kw in table.get(label, []):
            words.append((kw, label))

    # ①②④ AI：Q1その他・Q2・Q3-1 を同時に変換する（3回待たない）。合計9秒を超えたら AI なしで続ける
    concern_text, hint = concern_text.strip(), hint.strip()
    need_exclude = bool(last_gift.strip()) and last_result in BAD_RESULTS
    ai_tried = bool(concern_text) or bool(hint) or need_exclude
    c_words, hint_words, gift_words = ai_convert(concern_text, hint, last_gift if need_exclude else "")
    # 答えた自由入力のうち、1つでも AI の返事があれば「AI を使えた」
    used_ai = any(bool(asked) and r is not None
                  for r, asked in ((c_words, concern_text), (hint_words, hint), (gift_words, need_exclude)))

    # ① Q1その他：AI の言葉を使う。AI が使えないときは、5つの困りごとの中から文字の重なりがいちばん多いものを使う
    if concern_text:
        if c_words:
            for w in c_words:
                words.append((w, "concern_text"))
        elif c_words is None:
            label = closest_concern(concern_text, list(table))
            for kw in table.get(label, []) if label else []:
                words.append((kw, label))

    for w in hint_words or []:
        words.append((w, "hint"))
    exclude: list[str] = []
    if need_exclude:
        exclude = gift_words if gift_words else [last_gift.strip()]  # AI が使えなくても、入力した言葉そのものは外す

    # 同じ言葉は1回だけ探す（最初に出てきた方を優先：チェック → その他 → Q2 の順）
    seen, uniq = set(), []
    for w, src in words:
        if w not in seen:
            seen.add(w)
            uniq.append((w, src))
    words = uniq

    # ③⑤ 合う商品を販売数順に5件
    items = []
    if words:
        where = ["p.stock > 0"]
        params: list = []
        where.append("(" + " OR ".join(["p.product_name LIKE %s OR p.description LIKE %s"] * len(words)) + ")")
        for w, _ in words:
            params += [f"%{w}%", f"%{w}%"]
        add_exclusion(where, params, exclude)
        rows = fetch_all(
            f"SELECT {COLUMNS} FROM products p WHERE {' AND '.join(where)} ORDER BY p.sales_count DESC, p.product_id LIMIT %s",
            (*params, LIMIT),
        )
        for r in rows:
            main, detail = make_reason(r, words, hint, concern_text)
            items.append(to_item(r, main, detail, False))

    # ⑤ 足りない分を誕生日向けランキングで埋める（もう出した商品と、外す商品は除く）
    if len(items) < LIMIT:
        items += fill_popular([i["id"] for i in items], exclude, LIMIT - len(items))

    return {
        "items": items,
        "usedAi": used_ai,
        "aiTried": ai_tried,
        "searchWords": [w for w, _ in words],
        "excludeWords": exclude,
    }


def ai_convert(concern_text: str, hint: str, last_gift: str) -> tuple[list[str] | None, ...]:
    """Q1その他・Q2・Q3-1 の変換を並べて実行し、合計 AI_DEADLINE 秒で打ち切る"""
    jobs = [(concern_text, "concern"), (hint, "hint"), (last_gift, "gift")]
    if not any(t for t, _ in jobs):
        return [], [], []
    start = time.monotonic()
    pool = ThreadPoolExecutor(max_workers=3)
    futures = [pool.submit(to_keywords, t, AI_DEADLINE, k) for t, k in jobs]
    results = []
    for f in futures:
        left = max(0.1, AI_DEADLINE - (time.monotonic() - start))
        try:
            results.append(f.result(timeout=left))
        except Exception:
            results.append(None)  # 時間切れ → この入力は AI なしで扱う
    pool.shutdown(wait=False)  # 遅れている AI の返事は待たない（with を使うと、終わるまで待ってしまう）
    return tuple(results)


def closest_concern(text: str, labels: list[str]) -> str | None:
    """AI が使えないときの予備：入力文と困りごとの「2文字の組」の重なりを数え、いちばん多いものを返す
    例：「重い荷物を運ぶのが大変そう」→「重い物を持つ・運ぶのが大変」（重い・運ぶ・大変 が重なる）"""
    def pairs(s: str) -> set[str]:
        s = "".join(ch for ch in s if ch not in "・、。 　")
        return {s[i:i + 2] for i in range(len(s) - 1)}
    src = pairs(text)
    best, best_score = None, 0
    for label in labels:
        score = len(src & pairs(label))
        if score > best_score:
            best, best_score = label, score
    return best if best_score >= 2 else None  # 重なりが少なすぎるときは当て推量をしない


def add_exclusion(where: list[str], params: list, exclude: list[str]) -> None:
    """外す言葉を、商品名にも説明書きにも含まない、という条件を足す"""
    for w in exclude:
        where.append("p.product_name NOT LIKE %s AND p.description NOT LIKE %s")
        params += [f"%{w}%", f"%{w}%"]


def fill_popular(used_ids: list[str], exclude: list[str], n: int) -> list[dict]:
    """誕生日向けランキング（誕生日タグの商品を販売数順）で n 件埋める。足りなければ全体の人気順"""
    out: list[dict] = []
    for scene in (FILL_SCENE, None):
        if len(out) >= n:
            break
        where, params = ["p.stock > 0"], []
        ids = used_ids + [i["id"] for i in out]
        if ids:
            where.append("p.product_id NOT IN (" + ",".join(["%s"] * len(ids)) + ")")
            params += ids
        add_exclusion(where, params, exclude)
        if scene:
            where.append("p.product_id IN (SELECT s.product_id FROM product_scenes s WHERE s.scene_tag = %s)")
            params.append(scene)
        rows = fetch_all(
            f"SELECT {COLUMNS} FROM products p WHERE {' AND '.join(where)} ORDER BY p.sales_count DESC, p.product_id LIMIT %s",
            (*params, n - len(out)),
        )
        out += [to_item(r, "人気の商品です", "", True) for r in rows]
    return out


def make_reason(r: dict, words: list[tuple[str, str]], hint: str, concern_text: str = "") -> tuple[str, str]:
    """理由を2行で作る。1行目：どの手掛かりに合うか。2行目：説明書き（または商品名）の根拠"""
    desc = r.get("description") or ""
    name = r.get("product_name") or ""
    for w, src in words:  # 困りごとの言葉を先に見る（words は困りごとが先に並んでいる）
        if w in desc or w in name:
            if src == "hint":
                main = f"お母さんの「{short(hint, 20)}」に合いそうな商品です"
            elif src == "concern_text":
                main = f"お母さんの「{short(concern_text, 20)}」に合いそうな商品です"
            else:
                main = f"お母さんの「{src}」に合う商品です"
            if w in desc:
                detail = f"説明書きに「{snippet(desc, w)}」とあります"
            else:
                detail = f"商品名に「{w}」が入っています"
            return main, detail
    return "人気の商品です", ""  # ここには来ない想定（検索で言葉を含む商品だけを集めている）


def snippet(text: str, word: str, width: int = 18) -> str:
    """説明書きの中で、言葉の前後だけを切り出す（文の区切り「。」で止める）"""
    i = text.find(word)
    start = max(text.rfind("。", 0, i) + 1, i - width)
    end_dot = text.find("。", i)
    end = min(end_dot if end_dot != -1 else len(text), i + len(word) + width)
    s = text[start:end].strip()
    return ("…" if start > 0 and text[start - 1] != "。" else "") + s + ("…" if end < len(text) and text[end] != "。" else "")


def short(text: str, n: int) -> str:
    text = text.strip()
    return text if len(text) <= n else text[:n] + "…"


def to_item(r: dict, reason_main: str, reason_detail: str, is_fill: bool) -> dict:
    """DB の行 → 画面の Recommendation 型（Gift 型に理由を足したもの）"""
    return {
        "id": r["product_id"],
        "category": r["category"],
        "brand": r["brand"],
        "name": r["product_name"],
        "price": r["price"],
        "rating": float(r["rating"]) if r["rating"] is not None else 0,
        "reviewCount": r["review_count"],
        "reasonMain": reason_main,
        "reasonDetail": reason_detail,
        "isPopularFill": is_fill,
    }
