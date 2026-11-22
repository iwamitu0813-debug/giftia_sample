// app/ResultCard.tsx — 結果カード（部品）。順位の理由を件数で出し、その場でメッセージカードを作れる
"use client";

import { useState } from "react";
import { createCard, type Gift } from "@/lib/api";

const REASONS = ["相手の言葉や暮らしを思い出した", "実績の件数を見て", "価格が合った", "見た目が気に入った", "その他"];

type Props = { gift: Gift; rank: number; userId: string; recipient: string; purpose: string };

export default function ResultCard({ gift, rank, userId, recipient, purpose }: Props) {
  const [open, setOpen] = useState(false);            // カードを作る欄を開いているか
  const [senderName, setSenderName] = useState("");
  const [message, setMessage] = useState("");
  const [reason, setReason] = useState(REASONS[0]);
  const [code, setCode] = useState("");               // 作ったカードの返信用コード
  const [error, setError] = useState("");

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const res = await createCard({ userId, productId: gift.id, recipient, purpose, senderName, message, reason });
      setCode(res.code);
    } catch (err) {
      setError(`カードを作れませんでした：${(err as Error).message}`);
    }
  }

  return (
    <div className="card">
      <p className="meta">{rank}位・{gift.category}・{gift.brand}</p>
      <h3 className="name">{gift.name}</h3>
      <p className="price">{gift.price.toLocaleString()}円</p>
      <p className="meta">評価{gift.rating}（{gift.reviewCount}件）</p>

      {/* 順位の理由。順位を決めた順に並ぶ（第一の決め手が先頭）。「おすすめ」とは書かず、件数という事実だけを出す */}
      {gift.reasons.length > 0 && (
        <ul className="reasons">
          {gift.reasons.map((r) => (
            <li key={r.kind} className={`reason ${r.kind}`}>
              {r.label}
              {r.isTest && <span className="test">テスト用データ</span>}
            </li>
          ))}
        </ul>
      )}

      {!open && <button className="link" onClick={() => setOpen(true)}>この品を贈る（メッセージカードを作る）</button>}

      {open && !code && (
        <form className="cardform" onSubmit={onCreate}>
          <label>贈り主の名前<input value={senderName} onChange={(e) => setSenderName(e.target.value)} maxLength={30} required /></label>
          <label>メッセージ<textarea value={message} onChange={(e) => setMessage(e.target.value)} maxLength={300} rows={3} required /></label>
          <label>この品に決めた理由
            <select value={reason} onChange={(e) => setReason(e.target.value)}>
              {REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </label>
          <button type="submit">カードを作る</button>
          {error && <p className="error">{error}</p>}
        </form>
      )}

      {code && (
        <div className="done">
          <p>カードを作りました。返信用コード：<b>{code}</b></p>
          <p className="meta">本番ではこのコードをカードに印刷します。開発中は下のリンクが、受け取った方の画面です。</p>
          <a href={`/reply?code=${code}`} target="_blank" rel="noreferrer">受け取った方の画面を開く</a>
        </div>
      )}
    </div>
  );
}
