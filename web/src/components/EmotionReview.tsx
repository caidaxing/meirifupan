import type { EmotionTrendItem, HotData, ReviewData } from '../types'
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
      <EmotionDetail emotion={data.emotion} trend={trend} />
      {hotLoading ? (
        <div className="loading">加载热门数据...</div>
      ) : hotData ? (
        <HotView data={hotData} />
      ) : (
        <div className="error">{hotError ?? '暂无热门数据'}</div>
      )}
    </div>
  )
}
