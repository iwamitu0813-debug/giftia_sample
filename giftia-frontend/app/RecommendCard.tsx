// app/RecommendCard.tsx — お母さんへの誕生日の候補カード（FR-05）
// ResultCard と同じ見た目に、「使ってもらえそうな理由」を2行足したもの。
// 見た目の名前は rec- で始める（メンバーの ResultCard の .reason と混ざらないように）。
// 埋めた商品（合う商品が5件に足りないときに誕生日ランキングから足したもの）は「人気の商品です」と出す。
import type { Recommendation } from "@/lib/api";

export default function RecommendCard({ item, rank }: { item: Recommendation; rank: number }) {
  return (
    <div className="card">
      <p className="meta">{rank}位・{item.category}・{item.brand}</p>
      <h3 className="name">{item.name}</h3>
      <p className="price">{item.price.toLocaleString()}円</p>
      <p className="meta">評価{item.rating}（{item.reviewCount}件）</p>
      <div className={item.isPopularFill ? "rec-reason pop" : "rec-reason"}>
        <p className="rec-reason-main">{item.reasonMain}</p>
        {item.reasonDetail && <p className="rec-reason-detail">{item.reasonDetail}</p>}
      </div>
    </div>
  );
}
