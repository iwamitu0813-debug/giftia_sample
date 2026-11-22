// app/reply/page.tsx — ギフトを受け取った方の画面
// メッセージカードのコード（?code=...）で開く。会員登録なしで、お礼の言葉と「使っているか」を返せる。
// 星とコメントは贈り主には表示しない。「使っています」は、受け取った方が選んだときだけ贈り主に伝える。
"use client";

import { useEffect, useState } from "react";
import { getCard, sendReply, type CardForRecipient } from "@/lib/api";

export default function ReplyPage() {
  const [code, setCode] = useState("");
  const [card, setCard] = useState<CardForRecipient | null>(null);
  const [error, setError] = useState("");
  const [thanks, setThanks] = useState("");
  const [inUse, setInUse] = useState("using");
  const [shareUse, setShareUse] = useState(true);
  const [stars, setStars] = useState("");
  const [comment, setComment] = useState("");
  const [sent, setSent] = useState(false);

  // 画面を開いたときに、URL のコードからカードを読む
  useEffect(() => {
    const c = new URLSearchParams(window.location.search).get("code") ?? "";
    setCode(c);
    if (!c) { setError("カードのコードがありません。"); return; }
    getCard(c).then(setCard).catch(() => setError("カードが見つかりません。コードをご確認ください。"));
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await sendReply(code, { thanks, inUse, shareUse, stars: stars ? Number(stars) : null, comment });
      setSent(true);
    } catch (err) {
      setError(`送れませんでした：${(err as Error).message}`);
    }
  }

  return (
    <main className="page narrow">
      <header className="header"><h1>Giftia</h1></header>
      {error && <p className="error">{error}</p>}

      {card && (
        <div className="card letter">
          <p className="meta">{card.senderName} さんからのメッセージ</p>
          <p className="message">{card.message}</p>
          <p className="meta">贈りもの：{card.productName}</p>
        </div>
      )}

      {card && (card.replied || sent) && (
        <div className="done">
          <p>{sent ? "お礼を送りました。ありがとうございました。" : "このカードには、すでに返信があります。"}</p>
          <p className="meta">大切な方へ、あなたからも贈ってみませんか。</p>
          <a href="/">Giftiaでギフトを探す</a>
        </div>
      )}

      {card && !card.replied && !sent && (
        <form className="cardform" onSubmit={onSubmit}>
          <label>お礼の言葉（{card.senderName} さんに届きます）
            <textarea value={thanks} onChange={(e) => setThanks(e.target.value)} maxLength={300} rows={3} required />
          </label>

          <fieldset>
            <legend>贈りものは使っていますか？</legend>
            <label className="chk"><input type="radio" name="inuse" checked={inUse === "using"} onChange={() => setInUse("using")} /> 使っています</label>
            <label className="chk"><input type="radio" name="inuse" checked={inUse === "not_yet"} onChange={() => setInUse("not_yet")} /> これから使います</label>
            <label className="chk"><input type="radio" name="inuse" checked={inUse === "not_using"} onChange={() => setInUse("not_using")} /> 使っていません</label>
          </fieldset>
          <label className="chk"><input type="checkbox" checked={shareUse} onChange={(e) => setShareUse(e.target.checked)} /> 上の答えを {card.senderName} さんにも伝える</label>

          <fieldset>
            <legend>よろしければ教えてください（任意）</legend>
            <p className="meta">ここから下は {card.senderName} さんには表示されません。ほかの方がギフトを選ぶときの参考として、件数だけを使います。</p>
            <label>満足度
              <select value={stars} onChange={(e) => setStars(e.target.value)}>
                <option value="">選ばない</option>
                {[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{"★".repeat(n)}</option>)}
              </select>
            </label>
            <label>ひとこと
              <textarea value={comment} onChange={(e) => setComment(e.target.value)} maxLength={300} rows={2} />
            </label>
          </fieldset>

          <button type="submit">送る</button>
        </form>
      )}
    </main>
  );
}
