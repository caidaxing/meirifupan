import type { ReviewData } from '../types'
import { BoardTiers } from './BoardTiers'
import { CollapsibleSection } from './CollapsibleSection'
import { PlateGroupView } from './PlateGroupView'
import { ReviewReport } from './ReviewReport'

interface Props {
  data: ReviewData
}

export function LimitUpReview({ data }: Props) {
  return (
    <div className="review-stack">
      <ReviewReport review={data.saved_review} mode="limit-up" />
      <CollapsibleSection
        title="连板梯队"
        summary={`${data.board_tiers.length} 个层级`}
      >
        <BoardTiers tiers={data.board_tiers} fullView />
      </CollapsibleSection>
      <CollapsibleSection
        title="涨停原因明细"
        summary={`${data.all_stocks.length} 只涨停股`}
      >
        <PlateGroupView stocks={data.all_stocks} embedded />
      </CollapsibleSection>
    </div>
  )
}
