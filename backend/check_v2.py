# check_v2.py — このコードが班のDBで動くかを、画面を使わずに確かめる（SELECT だけ。DBは書き換えない）
# 実行：python check_v2.py
# 「エラー」が出た項目は、列名などが想定と違う可能性がある。出た文をそのまま共有する。

import main

def step(title, fn):
    print(f"== {title} ==")
    try:
        fn()
    except Exception as e:
        print(f"  エラー: {e}")
    print()

def show_health():
    print(" ", main.health())

def show_search():
    r = main.search(recipient="mother", purpose="誕生日", q="", price_min=None, price_max=None, limit=10)
    print(f"  候補 {r['total']} 件 / {r['sortRule']}")
    print(f"  レビュー本文の列: {main.review_text_column() or '（見つからず。注文の実績と人気順で並べます）'}")
    for i, g in enumerate(r["results"], 1):
        print(f"  {i}位 {g['id']} {g['name']} / " + (" ・ ".join(x["label"] for x in g["reasons"]) or "（記録なし）"))

def show_kettle():
    r = main.search(recipient="mother", purpose="誕生日", q="", price_min=None, price_max=None, limit=100)
    pos = [i for i, g in enumerate(r["results"], 1) if g["id"] == "G0567"]
    print("  Dさんが買ったケトル（G0567）の順位:", f"{pos[0]}位" if pos else "上位100件に入っていません")

def show_next():
    for uid in ("U-PERSONA-D", "U-PERSONA-E"):
        r = main.next_occasions(user_id=uid, today=None)
        print(f"  {uid}（{r['today']} 時点）")
        for s in r["suggestions"]:
            print(f"    {s['purpose']} 次は {s['nextDate']} / " + (s.get("lastProductName") or s.get("note") or ""))

step("1. 班のDBにつながるか", show_health)
step("2. 母 × 誕生日の検索と理由", show_search)
step("3. ケトルの順位", show_kettle)
step("4. 次の機会の案内", show_next)
