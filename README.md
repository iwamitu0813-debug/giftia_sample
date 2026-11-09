# giftia_sample

Giftia（ギフト専門 EC）のチーム開発用リポジトリです。

## 班のルール

### 作業の流れ
1. main（完成版）を pull（最新版を取得）する
2. ブランチ（作業用のコピー）を作る　名前：`feature/やること`
3. 作業したら commit（記録）して push（GitHub に送る）
4. PR（完成版に入れるお願い）を出し、Slack で知らせる
5. 本人以外の1人が確認して Approve（承認）→ merge（完成版に合体）
6. merge したら Slack で知らせ、全員が pull する

### 守ること
- main に直接 push しない
- `.env`（秘密情報）は GitHub に上げない
- 1つの PR には、1つの目的だけ

## 起動方法
`backend` に `.env`、`giftia-frontend` に `.env.local` を各自で置いてから起動します。

**frontend**（http://localhost:3000）
```
cd giftia-frontend
npm install
npm run dev
```

**backend**（http://localhost:8000/docs）
```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```
