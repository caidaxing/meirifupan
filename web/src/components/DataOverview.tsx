import type { EmotionTrendItem, ReviewData } from '../types'
import { BoardTiers } from './BoardTiers'
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
      <EmotionTrend trend={trend} />
      <div className="grid-2">
        <BoardTiers tiers={data.board_tiers} />
        <HotPlates plates={data.hot_plates} stocks={data.all_stocks} />
      </div>
      <HighStocks stocks={data.high_stocks} />
      <StockTable stocks={data.all_stocks} />
    </div>
  )
}
