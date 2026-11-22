# 実装メモ：理由表示・メッセージカード・次の機会（22班 さんこいち）

2週目の配布コード（Next.js ＋ FastAPI）をもとに、検索の入口・順位付け・理由表示と、贈った後の仕組みを足したコードです。
今後の開発は、このコードを土台に進めます。

## できること

| 画面 | 内容 |
| --- | --- |
| ギフトを探す | 「誰に × どんな機会」をタイルから選んで検索。実績のある商品を上に並べ、理由を件数で表示。実績のない商品との間に区切りを入れる |
| この品を贈る | 結果カードからメッセージカードを作る。決めた理由も記録する |
| 受け取った方の画面（/reply） | 会員登録なしで、お礼の言葉と「使っているか」を返す。星とコメントは贈り主に見せない |
| 贈ったギフト | 届いたお礼を贈り主が見る |
| 次の機会 | 注文の履歴から、次の時期と前回の品を案内する。相手との関係は一度だけ聞く |

## ファイルの役割

| ファイル | 役割 |
| --- | --- |
| backend/main.py | API の窓口（検索、カード、返信、次の機会） |
| backend/ranking.py | 並び順と理由の作り方。DBに触らない関数だけ |
| backend/occasions.py | 次の機会の案内のルール。DBに触らない関数だけ |
| backend/local_store.py | 新しく貯めるデータの保存（PC内の SQLite） |
| backend/database.py | 班のDBへの接続（配布コードのまま） |
| backend/check_v2.py | 班のDBで動くかの確認（SELECTだけ） |
| backend/seed_demo.py | デモ用のテストデータを入れる・消す |
| backend/test_app.py | 自動テスト（班のDBにつながずに動く） |
| giftia-frontend/app/page.tsx | 検索・贈ったギフト・次の機会の画面 |
| giftia-frontend/app/ResultCard.tsx | 結果カード（理由の表示、カード作成） |
| giftia-frontend/app/reply/page.tsx | 受け取った方の画面 |
| giftia-frontend/lib/api.ts | 画面から API を呼ぶ関数 |

## 並び順のルール（backend/ranking.py）

上から順に比べます。同じ入力なら必ず同じ順になります。生成AIは使いません。

1. 受け取った人の「使っています」の件数（3件以上で使う）
2. その相手に贈ったと書かれたレビューの件数（班のDBの reviews）
3. その相手の区分 × 機会で選ばれた注文の件数（班のDBの orders）
4. 販売数
5. 商品ID

## データの置き場所

- 班のDB（Azure MySQL）は SELECT で読むだけです。書き込みはしません。
- カード、返信、相手との関係は `backend/giftia_local.db`（PC内の SQLite）に保存します。最初の起動で自動で作られます。GitHub には上げません。

## 動かし方

`.env` は各自のPCで用意します（GitHub には上げません）。

- `backend/.env`：`backend/.env.example` をコピーして作り、DB_HOST、DB_PORT、DB_USER、DB_PASSWORD、DB_NAME、DB_SSL_CA、CORS_ORIGINS を入れる。CORS_ORIGINS は `http://localhost:3000`。
- `giftia-frontend/.env.local`：`giftia-frontend/.env.local.example` をコピーして作る。

```
# backend フォルダーで
pip install -r requirements.txt
python check_v2.py                       # 班のDBで動くかを確かめる
python -m uvicorn main:app --reload      # API を起動

# 別のターミナル。giftia-frontend フォルダーで
npm install
npm run dev                              # 画面を起動
```

ブラウザーで http://localhost:3000 を開きます。API の確認は http://localhost:8000/docs です。

## テスト

```
# backend フォルダーで
pip install pytest httpx
python -m pytest -q
```

## デモ用のテストデータ

受け取った人の「使っています」が順位に効く様子を見せるときに使います。画面では「テスト用データ」と表示されます。

```
python seed_demo.py           # ケトル（G0567）に4件入れる
python seed_demo.py --clear   # 消す
```

## 更新版の要件定義書（11/21）との関係

更新版の Phase1 は「3つの質問で母の手掛かりを引き出し、合う商品5件を理由つきで出す」設計です。このコードにはまだ入っていません。

| 更新版の要件 | このコードの状態 |
| --- | --- |
| FR-01 質問入力（Q1〜Q3） | 未実装 |
| FR-02 困りごとの言葉で候補を探し、販売数順に5件 | 未実装（いまは機会のタグと実績で並べる） |
| FR-03 自由入力の変換（AI） | 未実装 |
| FR-04 去年の失敗の除外 | 未実装 |
| FR-05 理由2行の表示 | 一部（理由を出す枠はある。文言は件数の表示） |
| FR-07 去年の注文の表示（Phase2） | 「次の機会」で前回の品を表示済み |
| DR-01 concern_keywords | 未実装 |

## 注意

- Next.js 16.4.3 には既知の脆弱性の案内が出ます（配布コードのバージョン）。公開する場合は更新を検討してください。
- 「次の日付」は、前回の注文と同じ月日です（班のDBに相手の誕生日は入っていません）。
- 班のDBの列名は、配布コードと班のDBでの集計結果から決めています。reviews の本文の列名は起動時に自動で調べます。
