# seed_demo.py — 受け取った人の「使っています」を、テスト用データとして入れる（このPCの SQLite だけ。班のDBには触らない）
#
# 使い方：
#   python seed_demo.py                 … ケトル（G0567）に、母 × 誕生日の「使っています」を4件入れる
#   python seed_demo.py G0567 G0001     … 商品IDを指定する
#   python seed_demo.py --clear         … テスト用データを消す
# 入れたデータは is_test = 1 になり、画面でも「テスト用データ」と表示される。

import sys

import local_store

args = sys.argv[1:]
if args == ["--clear"]:
    with local_store.connect() as c:
        c.execute("DELETE FROM gift_replies WHERE code IN (SELECT code FROM gift_cards WHERE is_test = 1)")
        n = c.execute("DELETE FROM gift_cards WHERE is_test = 1").rowcount
    print(f"テスト用データを {n} 件消しました")
else:
    for product_id in (args or ["G0567"]):
        for i in range(4):
            code = local_store.create_card("U-TEST", product_id, f"（テスト）{product_id}", "mother", "誕生日",
                                           "テスト", "テスト用のカード", "その他", is_test=1)
            local_store.save_reply(code, "ありがとう（テスト）", "using", False, 5, "")
        print(f"{product_id}：母 × 誕生日の「使っています」を4件入れました（テスト用）")
