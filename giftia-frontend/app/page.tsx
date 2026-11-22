// app/page.tsx — Giftia（22班 さんこいち）
// 2週目からの変更：
//   ① 入口を「誰に × どんな機会」に変えた。絵のタイルから選ぶ（キーワードは任意）
//   ② 結果に、並び順の説明と、商品ごとの理由（件数）を出す。実績のない商品との間に区切りを入れる
//   ③ 「贈ったギフト」（お礼の返信が届く）と「次の機会」（案内）のタブを足した
"use client";

import { useEffect, useState } from "react";
import ResultCard from "./ResultCard";
import MotherForm from "./MotherForm"; // 母 × 誕生日：3つの質問で選ぶ（要件定義書 FR-01〜05）
import {
  getNext, getOptions, listCards, saveRelation, searchGifts,
  type CardSummary, type Options, type SearchResponse, type Suggestion,
} from "@/lib/api";

type Tab = "search" | "sent" | "next";
// タイルに出す絵（絵文字）。キーは API の選択肢と同じ
const RECIPIENT_ICON: Record<string, string> = { mother: "👩", father: "👨", family: "👪", friend: "🧑‍🤝‍🧑", coworker: "💼", client: "🏢", annual: "📅" };
const PURPOSE_ICON: Record<string, string> = { 誕生日: "🎂", 母の日: "🌷", 父の日: "👔", お中元: "🎐", お歳暮: "🎍", お礼: "💌", 送別: "💐", 結婚祝い: "💍", 出産祝い: "👶" };
const IN_USE: Record<string, string> = { using: "使っています", not_yet: "これから使います", not_using: "使っていません" };

export default function Home() {
  const [options, setOptions] = useState<Options | null>(null); // 選択肢（APIから受け取る）
  const [tab, setTab] = useState<Tab>("search");
  const [userId, setUserId] = useState("U-PERSONA-D");           // デモ用の会員（ケースの顧客A〜E）
  const [error, setError] = useState("");

  // 探す
  const [recipient, setRecipient] = useState("");
  const [purpose, setPurpose] = useState("");
  const [keyword, setKeyword] = useState("");
  const [priceBand, setPriceBand] = useState("");
  const [found, setFound] = useState<SearchResponse | null>(null);
  const [searched, setSearched] = useState({ recipient: "", purpose: "" }); // 検索したときの条件（カード作成に使う）
  const [loading, setLoading] = useState(false);
  const [askMother, setAskMother] = useState(false); // 母 × 誕生日：3つの質問の画面を出しているか

  // 贈ったギフト／次の機会
  const [cards, setCards] = useState<CardSummary[] | null>(null);
  const [demoToday, setDemoToday] = useState("");
  const [next, setNext] = useState<{ today: string; suggestions: Suggestion[] } | null>(null);

  // 最初に1回、選択肢を読む
  useEffect(() => {
    getOptions().then(setOptions).catch((err) => setError(`APIにつながりません：${(err as Error).message}`));
  }, []);

  async function onSearch(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      setFound(await searchGifts({ recipient, purpose, keyword, priceBand }));
      setSearched({ recipient, purpose });
    } catch (err) {
      setFound(null);
      setError(`検索できませんでした：${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  async function loadCards(uid: string) {
    setError("");
    try { setCards(await listCards(uid)); } catch (err) { setError(`読み込めませんでした：${(err as Error).message}`); }
  }

  async function loadNext(uid: string, today: string) {
    setError("");
    try { setNext(await getNext(uid, today)); } catch (err) { setError(`読み込めませんでした：${(err as Error).message}`); }
  }

  function openTab(t: Tab) {
    setTab(t);
    if (t === "sent") loadCards(userId);
    if (t === "next") loadNext(userId, demoToday);
  }

  function changeUser(uid: string) {
    setUserId(uid);
    if (tab === "sent") loadCards(uid);
    if (tab === "next") loadNext(uid, demoToday);
  }

  async function onRelation(recipientKey: string, relation: string) {
    if (!relation) return;
    await saveRelation(userId, recipientKey, relation);
    loadNext(userId, demoToday);
  }

  const recipientLabel = (key: string) => options?.recipients.find((r) => r.key === key)?.label ?? key;

  return (
    <main className="page">
      <header className="header">
        <h1>Giftia</h1>
        <label className="who">デモ用の会員
          <select value={userId} onChange={(e) => changeUser(e.target.value)}>
            {(options?.personas ?? []).map((p) => <option key={p.userId} value={p.userId}>{p.label}</option>)}
          </select>
        </label>
      </header>

      <nav className="modes">
        <button className={tab === "search" ? "on" : ""} onClick={() => openTab("search")}>ギフトを探す</button>
        <button className={tab === "sent" ? "on" : ""} onClick={() => openTab("sent")}>贈ったギフト</button>
        <button className={tab === "next" ? "on" : ""} onClick={() => openTab("next")}>次の機会</button>
      </nav>

      {error && <p className="error">{error}</p>}

      {/* ── ギフトを探す ── */}
      {/* 母 × 誕生日：3つの質問で選ぶ画面（タイルの画面の代わりに出す） */}
      {tab === "search" && askMother && <MotherForm onBack={() => setAskMother(false)} />}

      {tab === "search" && !askMother && (
        <>
          <form className="form" onSubmit={onSearch}>
            {/* 入口：相手と機会を、絵のタイルから選ぶ（もう一度押すと選択を外せる） */}
            <div className="pick">
              <p className="picktitle">誰に贈りますか？</p>
              <div className="tiles">
                {(options?.recipients ?? []).map((r) => (
                  <button type="button" key={r.key} className={`tile ${recipient === r.key ? "on" : ""}`} aria-pressed={recipient === r.key}
                    onClick={() => setRecipient(recipient === r.key ? "" : r.key)}>
                    <span className="icon" aria-hidden="true">{RECIPIENT_ICON[r.key] ?? "🎁"}</span>
                    <span className="tilelabel">{r.label}</span>
                  </button>
                ))}
              </div>
            </div>
            <div className="pick">
              <p className="picktitle">どんな機会ですか？</p>
              <div className="tiles">
                {(options?.purposes ?? []).map((p) => (
                  <button type="button" key={p} className={`tile ${purpose === p ? "on" : ""}`} aria-pressed={purpose === p}
                    onClick={() => setPurpose(purpose === p ? "" : p)}>
                    <span className="icon" aria-hidden="true">{PURPOSE_ICON[p] ?? "🎁"}</span>
                    <span className="tilelabel">{p}</span>
                  </button>
                ))}
              </div>
            </div>
            <label>予算
              <select value={priceBand} onChange={(e) => setPriceBand(e.target.value)}>
                <option value="">すべての価格帯</option>
                <option value="3000">3,000〜5,000円</option>
                <option value="5000">5,000〜10,000円</option>
              </select>
            </label>
            <label className="grow">キーワード（任意）
              <input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="例：ケトル" maxLength={100} />
            </label>
            <button type="submit" disabled={loading}>{loading ? "検索中…" : "検索"}</button>
          </form>

          {/* 母 × 誕生日を選んだら、3つの質問へ進む入口を出す（Dさんの場面） */}
          {recipient === "mother" && purpose === "誕生日" && (
            <div className="motherask">
              <p>お母さんへの誕生日ですね。最近のお母さんの様子を3つ答えると、使ってもらえそうな品を理由つきで5つ選びます。</p>
              <button type="button" onClick={() => setAskMother(true)}>3つの質問に答えて選ぶ</button>
            </div>
          )}

          {found && (
            <section>
              <p className="summary">{found.total.toLocaleString()}件のうち上位 {found.results.length} 件</p>
              <p className="rule">{found.sortRule}</p>
              <div className="grid">
                {found.results.map((g, i) => (
                  <div key={g.id} className="cell">
                    {/* 実績のある商品が終わる位置に、区切りを1回だけ入れる */}
                    {(searched.recipient || searched.purpose) && i === found.evidenceCount && (
                      <p className="divider">{i === 0 ? "この組み合わせでの記録はまだありません。人気順で表示しています" : "ここから人気順（この組み合わせでの記録はまだありません）"}</p>
                    )}
                    <ResultCard gift={g} rank={i + 1} userId={userId} recipient={searched.recipient} purpose={searched.purpose} />
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {/* ── 贈ったギフト：受け取った方のお礼が届く ── */}
      {tab === "sent" && (
        <section>
          <p className="summary">この会員が、メッセージカードを付けて贈ったギフトです。</p>
          {cards && cards.length === 0 && <p className="empty">まだありません。「ギフトを探す」で商品を選び、メッセージカードを作ってください。</p>}
          <div className="list">
            {(cards ?? []).map((c) => (
              <div key={c.code} className="card">
                <p className="meta">{c.created_at.slice(0, 10)}・{recipientLabel(c.recipient) || "相手の指定なし"}{c.purpose && ` × ${c.purpose}`}</p>
                <h3 className="name">{c.product_name}</h3>
                <p className="meta">決めた理由：{c.reason}</p>
                {c.thanks ? (
                  <div className="thanks">
                    <p className="meta">お礼が届きました（{c.replied_at?.slice(0, 10)}）</p>
                    <p>{c.thanks}</p>
                    {c.shared_in_use && <p className="reason used">受け取った方より：「{IN_USE[c.shared_in_use]}」</p>}
                  </div>
                ) : (
                  <p className="meta">まだ返信はありません。<a href={`/reply?code=${c.code}`} target="_blank" rel="noreferrer">受け取った方の画面を開く</a></p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── 次の機会：注文の履歴から案内を作る ── */}
      {tab === "next" && (
        <section>
          <div className="form">
            <label>デモ用：この日を今日として表示
              <input type="date" value={demoToday} onChange={(e) => { setDemoToday(e.target.value); loadNext(userId, e.target.value); }} />
            </label>
          </div>
          {next && <p className="summary">{next.today} 時点の案内です。班のDBの注文の履歴から作っています。</p>}
          {next && next.suggestions.length === 0 && <p className="empty">案内できる機会はまだありません。</p>}
          <div className="list">
            {(next?.suggestions ?? []).map((s) => (
              <div key={`${s.recipientKey}-${s.purpose}-${s.type}`} className={`card ${s.soon ? "soon" : ""}`}>
                <p className="meta">相手 {s.relation || "（関係は未登録）"}・ID末尾 {s.recipientKey.slice(-4)}</p>
                {s.type === "annual" ? (
                  <>
                    <h3 className="name">{s.purpose}：次は {s.nextDate}{s.soon && <span className="badge">そろそろ</span>}</h3>
                    <p>前回（{s.lastDate}）は「{s.lastProductName}」を贈りました。</p>
                    {s.usedShared && <p className="reason used">受け取った方から「使っています」と届いています</p>}
                    {s.sameAsBefore && <p className="meta">{s.times}回続けて同じ品です。同じ品をもう一度贈れます。</p>}
                    {!s.soon && <p className="meta">{s.noticeFrom} ごろにお知らせします。</p>}
                    {s.needsRelation && (
                      <label className="ask">この相手はどなたですか？（一度だけ伺います）
                        <select defaultValue="" onChange={(e) => onRelation(s.recipientKey, e.target.value)}>
                          <option value="">選んでください</option>
                          {(options?.relations ?? []).map((r) => <option key={r} value={r}>{r}</option>)}
                        </select>
                      </label>
                    )}
                  </>
                ) : (
                  <>
                    <h3 className="name">{s.purpose}（{s.nextDate}）</h3>
                    <p className={s.suppressed ? "meta" : ""}>{s.note}</p>
                  </>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
