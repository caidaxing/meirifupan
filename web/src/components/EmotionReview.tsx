import type { EmotionTrendItem, HotData, ReviewData } from '../types'
import { CollapsibleSection } from './CollapsibleSection'
import { EmotionDetail } from './EmotionDetail'
import { HotView } from './HotView'
import { ReviewReport } from './ReviewReport'

interface Props {
  data: ReviewData
  trend: EmotionTrendItem[]
  hotData: HotData | null
  hotLoading: boolean
  hotError: string | null
}

export function EmotionReview({ data, trend, hotData, hotLoading, hotError }: Props) {
  return (
    <div className="review-stack">
      <ReviewReport review={data.saved_review} mode="emotion" />
      <CollapsibleSection title="情绪评分细节" summary="拆开看各项分数">
        <EmotionDetail emotion={data.emotion} trend={trend} />
      </CollapsibleSection>
      <CollapsibleSection title="热门榜明细" summary={hotData ? `${hotData.hot_stocks.length} 只人气股` : '按需查看'}>
        {hotLoading ? (
          <div className="loading">加载热门数据...</div>
        ) : hotData ? (
          <HotView data={hotData} />
        ) : (
          <div className="error">{hotError ?? '暂无热门数据'}</div>
        )}
      </CollapsibleSection>
    </div>
  )
}
