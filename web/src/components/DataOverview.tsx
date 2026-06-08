import type { EmotionTrendItem, ReviewData } from '../types'
import { BoardTiers } from './BoardTiers'
import { CollapsibleSection } from './CollapsibleSection'
import { EmotionTrend } from './EmotionTrend'
import { HighStocks } from './HighStocks'
import { HotPlates } from './HotPlates'
import { IndexCards } from './IndexCards'
import { LimitUpStats } from './LimitUpStats'
import { MarketEnvironment } from './MarketEnvironment'
import { StockTable } from './StockTable'

interface Props {
  data: ReviewData
  trend: EmotionTrendItem[]
}

export function DataOverview({ data, trend }: Props) {
  return (
    <div className="review-stack">
      <div className="top-row">
        <IndexCards indices={data.indices} />
        <LimitUpStats stats={data.limit_up_stats} />
      </div>
      <MarketEnvironment data={data.market_environment} />
      <CollapsibleSection title="近5日趋势" summary="情绪、涨停、最高板">
        <EmotionTrend trend={trend} />
      </CollapsibleSection>
      <CollapsibleSection title="连板和热门板块" summary={`${data.board_tiers.length} 个梯队 · ${data.hot_plates.length} 个板块`}>
        <div className="grid-2">
          <BoardTiers tiers={data.board_tiers} />
          <HotPlates plates={data.hot_plates} stocks={data.all_stocks} />
        </div>
      </CollapsibleSection>
      <CollapsibleSection title="高位股" summary={`${data.high_stocks.length} 只`}>
        <HighStocks stocks={data.high_stocks} />
      </CollapsibleSection>
      <CollapsibleSection title="全部涨停股" summary={`${data.all_stocks.length} 只，可搜索`}>
        <StockTable stocks={data.all_stocks} />
      </CollapsibleSection>
    </div>
  )
}
