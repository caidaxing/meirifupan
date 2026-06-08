import type { DataJob, EmotionTrendItem, ReviewData } from '../types'
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
  latestJob?: DataJob | null
}

function statusText(status: string) {
  if (status === 'success') return '更新完成'
  if (status === 'partial') return '部分完成'
  if (status === 'failed') return '更新失败'
  if (status === 'running') return '更新中'
  if (status === 'skipped') return '已跳过'
  return status
}

function formatTime(value?: string | null) {
  if (!value) return '-'
  return value.replace('T', ' ').slice(0, 16)
}

function DataUpdateStatus({ job }: { job?: DataJob | null }) {
  if (!job) {
    return (
      <div className="job-status job-status-empty">
        <div>
          <span>自动更新</span>
          <strong>暂无记录</strong>
        </div>
        <small>调度启动后会在这里看到最近一次结果</small>
      </div>
    )
  }

  const failedSteps = job.details.steps?.filter(step => step.status !== 'success') ?? []

  return (
    <div className={`job-status job-status-${job.status}`}>
      <div className="job-status-main">
        <div>
          <span>自动更新</span>
          <strong>{statusText(job.status)}</strong>
        </div>
        <div>
          <span>交易日</span>
          <strong>{job.trade_date ?? '-'}</strong>
        </div>
        <div>
          <span>结束时间</span>
          <strong>{formatTime(job.finished_at ?? job.created_at)}</strong>
        </div>
        <div>
          <span>失败步骤</span>
          <strong>{failedSteps.length}</strong>
        </div>
      </div>
      {job.message && <p>{job.message}</p>}
      {failedSteps.length > 0 && (
        <CollapsibleSection title="失败明细" summary={`${failedSteps.length} 项`} flush>
          <div className="job-step-list">
            {failedSteps.map(step => (
              <div className="job-step" key={`${step.name}-${step.started_at}`}>
                <span>{step.name}</span>
                <small>{step.message || '没有返回具体原因'}</small>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}
    </div>
  )
}

export function DataOverview({ data, trend, latestJob }: Props) {
  return (
    <div className="review-stack">
      <DataUpdateStatus job={latestJob} />
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
