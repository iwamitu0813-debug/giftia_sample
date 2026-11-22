// app/MotherForm.tsx — 「お母さんへの誕生日」タブ（FR-01・05）
// Dさんの決め手は、ランキングではなく母の一言だった。だから、母の手掛かりを思い出せる3つの質問を出し、
// 答えに合う商品を5つ、理由つきで見せる。3問とも任意で、「質問をとばす」と誕生日の人気順が出る。
// 入口は「ギフトを探す」タブ：👩母 × 🎂誕生日 を選ぶと「3つの質問に答えて選ぶ」ボタンが出る（page.tsx）。
"use client";

import { useEffect, useState } from "react";
import RecommendCard from "./RecommendCard";
import { fetchConcerns, recommendGifts, type RecommendResult } from "@/lib/api";

// Q3-2 の選択肢。「あまり使っていない」「サイズや好みが合わなかった」のときだけ、去年の品物に近い商品を外す
const LAST_RESULTS = ["よく使ってくれている", "あまり使っていない", "サイズや好みが合わなかった", "分からない", "去年は贈っていない"];
const THINKING_AFTER_MS = 5000; // 5秒たっても出なければ「考え中です」（要件定義書 8章）

export default function MotherForm({ onBack }: { onBack?: () => void }) {
  const [options, setOptions] = useState<string[]>([]);       // Q1 の選択肢（対応表から）
  const [concerns, setConcerns] = useState<string[]>([]);     // Q1 で選んだ困りごと
  const [concernText, setConcernText] = useState("");         // Q1 その他（自由入力）
  const [hint, setHint] = useState("");                       // Q2
  const [lastGift, setLastGift] = useState("");               // Q3-1
  const [lastResult, setLastResult] = useState("");           // Q3-2
  const [result, setResult] = useState<RecommendResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState("");

  // タブを開いたら、Q1 の選択肢を API から取ってくる（対応表を直せば、画面も自動で変わる）
  useEffect(() => {
    fetchConcerns()
      .then(setOptions)
      .catch((err) => setError(`APIにつながりません：${(err as Error).message}`));
  }, []);

  function toggle(label: string) {
    setConcerns((prev) => (prev.includes(label) ? prev.filter((x) => x !== label) : [...prev, label]));
  }

  async function run(skip: boolean) {
    setError("");
    setResult(null);
    setLoading(true);
    setThinking(false);
    const timer = setTimeout(() => setThinking(true), THINKING_AFTER_MS);
    const answers = skip
      ? { concerns: [], concernText: "", hint: "", lastGift: "", lastResult: "" } // とばしたら何も送らない → 人気順
      : { concerns, concernText, hint, lastGift, lastResult };
    try {
      setResult(await recommendGifts(answers));
    } catch (err) {
      setError(`APIにつながりません：${(err as Error).message}`);
    } finally {
      clearTimeout(timer);
      setLoading(false);
      setThinking(false);
    }
  }

  return (
    <>
      {/* 「ギフトを探す」で 母 × 誕生日 を選んだときに開く。タイルの画面に戻れるようにする */}
      {onBack && <button type="button" className="link" onClick={onBack}>← タイルで探す画面に戻る</button>}
      <p className="summary">お母さんへの誕生日：最近のお母さんの様子を教えてください。答えに合う品を、理由つきで5つ選びます。</p>
      <form className="form mother" onSubmit={(e) => { e.preventDefault(); run(false); }}>
        <fieldset className="qbox">
          <legend>Q1　お母さんが最近、困っていること・面倒そうにしていることは？（いくつでも）</legend>
          <div className="choices">
            {options.map((label) => (
              <label key={label} className="chk">
                <input type="checkbox" checked={concerns.includes(label)} onChange={() => toggle(label)} /> {label}
              </label>
            ))}
          </div>
          {/* チェックにない困りごとは自由に書ける。AI が「困りごとを楽にする品物の言葉」に変える */}
          <input className="q" value={concernText} onChange={(e) => setConcernText(e.target.value)} maxLength={200}
            placeholder="その他（自由に書けます）例：膝が痛くて階段がつらそう" />
        </fieldset>

        <fieldset className="qbox">
          <legend>Q2　お母さんが「便利そう」「いいね」と言っていた物は？</legend>
          <input className="q" value={hint} onChange={(e) => setHint(e.target.value)} maxLength={200}
            placeholder="例：お茶をよく飲む／旅行に行きたいと言っていた" />
        </fieldset>

        <fieldset className="qbox">
          <legend>Q3　去年、お母さんに贈った物と、その結果は？</legend>
          <div className="choices">
            <input value={lastGift} onChange={(e) => setLastGift(e.target.value)} maxLength={100} placeholder="例：服" />
            <select value={lastResult} onChange={(e) => setLastResult(e.target.value)}>
              <option value="">贈った結果（選ぶ）</option>
              {LAST_RESULTS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        </fieldset>

        <div className="actions">
          <button type="submit" disabled={loading}>おすすめを見る</button>
          <button type="button" className="skip" disabled={loading} onClick={() => run(true)}>質問をとばす</button>
          <span className="summary">3つとも答えなくても大丈夫です</span>
        </div>
      </form>

      {loading && <p className="summary">{thinking ? "考え中です…" : "探しています…"}</p>}
      {error && <p className="summary">{error}</p>}

      {result && (
        <section>
          <p className="summary">
            おすすめ {result.items.length} 件
            {result.searchWords.length > 0 && `（探した言葉：${result.searchWords.join("・")}）`}
            {result.aiTried && !result.usedAi && "　※AIを使えなかったため、チェックした困りごと（と、近い困りごと）で探しました"}
          </p>
          <div className="grid">
            {result.items.map((g, i) => <RecommendCard key={g.id} item={g} rank={i + 1} />)}
          </div>
        </section>
      )}
    </>
  );
}
