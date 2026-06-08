import type { MarketInsights, ReviewData } from '../types'
import { CollapsibleSection } from './CollapsibleSection'
import { InsightView } from './InsightView'
import { MarketEnvironment } from './MarketEnvironment'
import { ReviewReport } from './ReviewReport'

interface Props {
  data: ReviewData
  insights: MarketInsights | null
  loading: boolean
}

export function ProfitEffectReview({ data, insights, loading }: Props) {
  return (
    <div className="review-stack">
      <ReviewReport review={data.saved_review} mode="profit" />
      <MarketEnvironment data={data.market_environment} compact />
      <CollapsibleSection title="封板、晋级和资金细节" summary="按需展开">
        {loading ? (
          <div className="loading">加载赚钱效应数据...</div>
        ) : insights ? (
          <InsightView data={insights} focus="profit" />
        ) : (
          <div className="error">暂无赚钱效应数据</div>
        )}
      </CollapsibleSection>
    </div>
  )
}
