import type { ReviewData } from '../types'
import { BoardTiers } from './BoardTiers'
import { PlateGroupView } from './PlateGroupView'
import { ReviewReport } from './ReviewReport'

interface Props {
  data: ReviewData
}

export function LimitUpReview({ data }: Props) {
  return (
    <div className="review-stack">
      <ReviewReport review={data.saved_review} mode="limit-up" />
      <BoardTiers tiers={data.board_tiers} fullView />
      <section className="card">
        <div className="card-header">涨停原因明细</div>
        <div className="card-body">
          <PlateGroupView stocks={data.all_stocks} embedded />
        </div>
      </section>
    </div>
  )
}
