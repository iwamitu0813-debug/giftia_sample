# ai_keywords.py — 自由入力（Q1の「その他」・Q2・Q3-1）を「説明書きで探す言葉」に変える（FR-03）
#
# 工夫したこと
# - AI に任せるのは「言葉の変換」だけ。候補の選び方・並べ方・理由はルール（recommend.py）で決めるので、
#   同じ入力なら同じ結果になり、なぜその順番かを説明できる。
# - AI は Claude（Anthropic）の Haiku 5.5 を使う。短い言葉の変換なので、いちばん安くて速いモデルで足りる。
# - 新しいパッケージは足さない。Claude の API は Python 標準の urllib で呼ぶ。
# - APIキーは .env の ANTHROPIC_API_KEY から読む（コードに書かない・GitHub に上げない・画面側に置かない）。
#   キーがない／通信に失敗した／時間切れのときは None を返し、呼び出し側は AI なしで続ける（アプリは止まらない）。
# - 質問ごとに「何に変えてほしいか」を変える（困りごと → 困りごとを楽にする品物、去年の品物 → 似た品物の言葉）。

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5")
MAX_WORDS = 5

BASE = """あなたはギフト通販サイトの検索を手伝います。
家族が母親について入力した短い文から、商品の説明文に出てきそうな言葉を最大5つ選んでください。
- 名詞や短い形容詞にする（例：お茶、紅茶、軽い、保温、リラックス）
- 1語は10文字以内。入力に関係のない言葉は入れない
- 次の形の JSON だけを返す。説明文は付けない：{"keywords": ["言葉1", "言葉2"]}"""

# 質問ごとの追加の指示
KIND_RULES = {
    # Q1 その他：困りごとそのものではなく、困りごとを楽にする品物の言葉にする
    "concern": "- 入力は母親の「困っていること」。困りごとを楽にする・やわらげる品物の特徴を表す言葉にする（例：膝が痛くて階段がつらい → 軽い、クッション、サポート、楽）",
    # Q2：体験は、その体験を楽しむための品物の言葉にする
    "hint": "- 旅行・趣味などの体験が書かれていたら、その体験を楽しむための「品物」を表す言葉にする（例：旅行 → トラベル、ポーチ、持ち運び）",
    # Q3-1：去年の品物に似た商品を外すための言葉
    "gift": "- 入力は去年贈った品物。その品物と同じ種類の商品を見つけるための言葉にする（例：焼き菓子 → 焼き菓子、クッキー、菓子）",
}


def to_keywords(text: str, timeout: float = 9.0, kind: str = "hint") -> list[str] | None:
    """文を探す言葉のリストに変える。AI を使えなかったときは None（空の入力なら []）"""
    text = (text or "").strip()
    if not text:
        return []
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None  # キーがなければ AI なしで続ける

    body = json.dumps({
        "model": MODEL,
        "max_tokens": 200,   # 言葉5つなので短くてよい（使った分だけ料金がかかるので、上限を決めておく）
        "temperature": 0,    # 同じ入力で同じ言葉が返りやすくする
        "system": BASE + "\n" + KIND_RULES.get(kind, KIND_RULES["hint"]),
        "messages": [{"role": "user", "content": text[:200]}],
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={"content-type": "application/json", "x-api-key": api_key, "anthropic-version": API_VERSION},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            data = json.loads(res.read().decode("utf-8"))
        content = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
        words = json.loads(content[content.index("{"): content.rindex("}") + 1]).get("keywords", [])
    except (urllib.error.URLError, TimeoutError, OSError, KeyError, IndexError, ValueError, TypeError, AttributeError):
        return None  # 時間切れ・通信エラー・形が違う → AI なしで続ける

    # AI の返事をそのまま信じない：文字列で、短く、重ならないものだけ残す
    clean = []
    for w in words if isinstance(words, list) else []:
        if isinstance(w, str) and 0 < len(w.strip()) <= 10 and w.strip() not in clean:
            clean.append(w.strip())
    return clean[:MAX_WORDS]
