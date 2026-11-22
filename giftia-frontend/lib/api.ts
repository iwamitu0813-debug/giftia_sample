// lib/api.ts — 画面から FastAPI を呼ぶ関数をまとめたファイル
// 2週目からの変更：検索条件に「贈る相手」「贈る機会」を足し、結果に「理由（reasons）」が付く。
// あわせて、メッセージカード・受け取った人の返信・次の機会の案内を呼ぶ関数を足した。

// 順位の理由。API が件数つきで返すので、画面は並べるだけ（順位の根拠と表示が必ず一致する）
export type Reason = {
  kind: "used" | "voice" | "chosen"; // 使っています／その相手に贈ったレビュー／選ばれた注文
  label: string;                      // 例：「家族 × 誕生日で選ばれた 48件」
  count: number;
  isTest: boolean;                    // テスト用データを含むか
};

export type Gift = {
  id: string;
  category: string;
  brand: string;
  name: string;
  price: number;
  rating: number;
  reviewCount: number;
  reasons: Reason[];
};

export type SearchCondition = {
  recipient: string; // 贈る相手（空なら指定なし）
  purpose: string;   // 贈る機会（空なら指定なし）
  keyword: string;
  priceBand: string; // "" | "3000" | "5000"
};

export type SearchResponse = {
  total: number;
  sortRule: string;      // 並び順の説明
  evidenceCount: number; // 上位のうち実績のある件数。ここから下は人気順
  results: Gift[];
};

export type Options = {
  recipients: { key: string; label: string }[];
  purposes: string[];
  relations: string[];
  personas: { userId: string; label: string }[];
};

export type CardSummary = {
  code: string;
  product_id: string;
  product_name: string;
  recipient: string;
  purpose: string;
  message: string;
  reason: string;
  created_at: string;
  thanks: string | null;          // お礼の言葉（返信があれば）
  replied_at: string | null;
  shared_in_use: string | null;   // 受け取った人が伝えると選んだときだけ入る
};

export type CardForRecipient = { senderName: string; message: string; productName: string; replied: boolean };

export type Suggestion = {
  type: "annual" | "cross";
  recipientKey: string;
  relation: string;
  purpose: string;
  nextDate: string;
  noticeFrom: string;
  soon: boolean;
  lastDate?: string;
  lastProductName?: string;
  times?: number;
  sameAsBefore?: boolean;
  usedShared?: boolean;
  needsRelation?: boolean;
  suppressed?: boolean;
  note?: string;
};

// API の場所。NEXT_PUBLIC_ の値はブラウザに配られる＝秘密は置かない（.env.local に書く）
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function getOptions(): Promise<Options> {
  return getJson("/api/options");
}

export function searchGifts(c: SearchCondition): Promise<SearchResponse> {
  const params = new URLSearchParams();
  if (c.recipient) params.set("recipient", c.recipient);
  if (c.purpose) params.set("purpose", c.purpose);
  if (c.keyword) params.set("q", c.keyword);
  if (c.priceBand === "3000") { params.set("price_min", "3000"); params.set("price_max", "4999"); }
  if (c.priceBand === "5000") { params.set("price_min", "5000"); params.set("price_max", "9999"); }
  return getJson(`/api/search?${params.toString()}`);
}

export function createCard(body: { userId: string; productId: string; recipient: string; purpose: string; senderName: string; message: string; reason: string }): Promise<{ code: string }> {
  return postJson("/api/cards", body);
}

export async function listCards(userId: string): Promise<CardSummary[]> {
  return (await getJson<{ cards: CardSummary[] }>(`/api/cards?user_id=${encodeURIComponent(userId)}`)).cards;
}

export function getCard(code: string): Promise<CardForRecipient> {
  return getJson(`/api/cards/${encodeURIComponent(code)}`);
}

export function sendReply(code: string, body: { thanks: string; inUse: string; shareUse: boolean; stars: number | null; comment: string }): Promise<{ status: string }> {
  return postJson(`/api/cards/${encodeURIComponent(code)}/reply`, body);
}

export function getNext(userId: string, today: string): Promise<{ today: string; suggestions: Suggestion[] }> {
  const t = today ? `&today=${today}` : "";
  return getJson(`/api/next?user_id=${encodeURIComponent(userId)}${t}`);
}

export function saveRelation(userId: string, recipientKey: string, relation: string): Promise<{ status: string }> {
  return postJson("/api/relations", { userId, recipientKey, relation });
}

// ── お母さんへの誕生日（3週目以降。要件定義書 FR-01〜05） ─────────────────
// 候補1件の形：Gift（件数の理由 reasons は使わない）に「使ってもらえそうな理由」を足したもの
export type Recommendation = Omit<Gift, "reasons"> & {
  reasonMain: string;      // 1行目：どの手掛かりに合うか（埋めた商品は「人気の商品です」）
  reasonDetail: string;    // 2行目：説明書き（または商品名）の根拠
  isPopularFill: boolean;  // 合う商品が足りず、誕生日ランキングから足した商品か
};

export type RecommendResult = {
  items: Recommendation[];
  usedAi: boolean;         // AI で自由入力を言葉に変換できたか
  aiTried: boolean;        // AI を使おうとしたか（自由入力があったか）
  searchWords: string[];   // 実際に探した言葉（発表・確認用に画面に出す）
  excludeWords: string[];  // 外した言葉（去年の失敗）
};

export type MotherAnswers = {
  concerns: string[];  // Q1：困りごと（複数）
  concernText: string; // Q1 その他：困りごと（自由入力。AI で探す言葉に変える）
  hint: string;        // Q2：自由入力
  lastGift: string;    // Q3-1：去年贈った物
  lastResult: string;  // Q3-2：その結果
};

// Q1 の選択肢（困りごと）を API からもらう
export async function fetchConcerns(): Promise<string[]> {
  const res = await fetch(`${API}/api/concerns`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data: { concerns: { label: string }[] } = await res.json();
  return data.concerns.map((c) => c.label);
}

// 3つの質問の答えを送り、おすすめ5件をもらう。API 側は最長でも約10秒で返す。念のため15秒で打ち切る
export async function recommendGifts(a: MotherAnswers): Promise<RecommendResult> {
  const params = new URLSearchParams();
  a.concerns.forEach((c) => params.append("concerns", c)); // 複数選んだら concerns=..&concerns=..
  if (a.concernText.trim()) params.set("concern_text", a.concernText.trim());
  if (a.hint.trim()) params.set("hint", a.hint.trim());
  if (a.lastGift.trim()) params.set("last_gift", a.lastGift.trim());
  if (a.lastResult) params.set("last_result", a.lastResult);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API}/api/recommend?${params.toString()}`, { signal: controller.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}
