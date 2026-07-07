import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { EmotionModuleKey, EmotionModuleTab, EmotionModulesData, EmotionRealtimeData, EmotionTrendItem, HotData, ReviewData } from '../types'
import { EmotionDetail } from './EmotionDetail'
import { HotView } from './HotView'

const EMOTION_TABS: { key: EmotionModuleKey; label: string }[] = [
  { key: 'cycle', label: '情绪周期' },
  { key: 'intraday', label: '情绪日内' },
  { key: 'cycle_vip', label: '情绪周期VIP' },
  { key: 'cycle_year', label: '情绪周期-年' },
  { key: 'space_board', label: '空间板' },
  { key: 'popularity', label: '人气' },
  { key: 'popularity_compare', label: '人气对比' },
  { key: 'heat_single', label: '情绪热度单页' },
]

interface Props {
  data: ReviewData
  trend: EmotionTrendItem[]
  hotData: HotData | null
  hotLoading: boolean
  hotError: string | null
  modules: EmotionModulesData | null
  modulesLoading: boolean
  modulesError: string | null
  realtime: EmotionRealtimeData | null
  realtimeLoading: boolean
  realtimeError: string | null
  controls?: ReactNode
}

export function EmotionReview({
  data,
  trend,
  hotData,
  hotLoading,
  hotError,
  modules,
  modulesLoading,
  modulesError,
  realtime,
  realtimeLoading,
  realtimeError,
  controls,
}: Props) {
  const [active, setActive] = useState<EmotionModuleKey>('cycle')
  const emotionPayload = realtime ?? modules
  const loading = realtimeLoading || (!realtime && modulesLoading)
  const error = realtimeError ?? (!realtime ? modulesError : null)
  const moduleMap = useMemo(() => {
    const map = new Map<EmotionModuleKey, EmotionModuleTab>()
    emotionPayload?.modules.forEach(item => map.set(item.key, item))
    return map
  }, [emotionPayload])
  const activeModule = moduleMap.get(active)

  return (
    <div className="review-stack emotion-workbench">
      <div className="review-subtabs emotion-subtabs">
        {EMOTION_TABS.map(tab => (
          <button key={tab.key} className={active === tab.key ? 'active' : ''} onClick={() => setActive(tab.key)}>
            {tab.label}
          </button>
        ))}
      </div>
      {controls}

      <section className="review-module-shell emotion-module-shell">
        <div className="review-module-top">
          <div>
            <h2>{EMOTION_TABS.find(tab => tab.key === active)?.label}</h2>
            <span>{formatHeaderMeta(emotionPayload, data.date)}</span>
          </div>
          <span className={`review-status review-status-${activeModule?.status || 'empty'}`}>
            {loading ? '加载中' : activeModule?.status || '暂无'}
          </span>
        </div>

        {error && <div className="review-empty review-empty-error">{error}</div>}
        {loading && <div className="review-empty">加载实时情绪...</div>}
        {!loading && !activeModule && !error && <div className="review-empty">暂无数据</div>}
        {activeModule && (
          <>
            <ModuleSummary module={activeModule} />
            <ModuleBody module={activeModule} hotData={hotData} hotLoading={hotLoading} hotError={hotError} />
          </>
        )}
      </section>

      <section className="review-module-shell emotion-detail-shell">
        <div className="review-module-top">
          <div>
            <h2>评分拆解</h2>
            <span>历史模型参考</span>
          </div>
        </div>
        <EmotionDetail emotion={data.emotion} trend={trend} />
      </section>
    </div>
  )
}

function formatHeaderMeta(payload: EmotionRealtimeData | EmotionModulesData | null, fallbackDate: string) {
  if (!payload) return `${fallbackDate} · 实时情绪`
  if ('mode' in payload && payload.mode === 'realtime') {
    return `${payload.date} · 实时情绪 · ${payload.as_of}`
  }
  return `${payload.date} · 历史情绪`
}

function ModuleSummary({ module }: { module: EmotionModuleTab }) {
  const metrics = Object.entries(module.summary || {})
    .filter(([, value]) => value == null || ['string', 'number', 'boolean'].includes(typeof value))
    .slice(0, 8)

  return (
    <div className="emotion-module-metrics">
      {metrics.map(([key, value]) => (
        <div className="emotion-module-metric" key={key}>
          <span>{metricLabel(key)}</span>
          <strong>{formatValue(value)}</strong>
        </div>
      ))}
      {module.warnings.map(warning => (
        <div className="emotion-module-warning" key={warning}>{warning}</div>
      ))}
    </div>
  )
}

function ModuleBody({
  module,
  hotData,
  hotLoading,
  hotError,
}: {
  module: EmotionModuleTab
  hotData: HotData | null
  hotLoading: boolean
  hotError: string | null
}) {
  if (module.key === 'cycle' || module.key === 'cycle_year' || module.key === 'heat_single') {
    return <HeatTable rows={module.items} />
  }
  if (module.key === 'intraday') {
    return <IntradayList rows={module.items} />
  }
  if (module.key === 'cycle_vip') {
    return <PromotionTable rows={module.items} />
  }
  if (module.key === 'space_board' || module.key === 'popularity' || module.key === 'popularity_compare') {
    if (module.key === 'popularity' && module.items.length === 0) {
      return hotLoading ? <div className="review-empty">加载人气榜...</div> : hotData ? <HotView data={hotData} /> : <div className="review-empty">{hotError ?? '暂无人气数据'}</div>
    }
    return <StockRankTable rows={module.items} showCompare={module.key === 'popularity_compare'} />
  }
  return <GenericList rows={module.items} />
}

function HeatTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  return (
    <div className="review-table-wrap">
      <table className="review-mini-table emotion-table">
        <thead>
          <tr><th>日期</th><th>涨停</th><th>最高板</th><th>红盘率</th><th>炸板率</th><th>人气跌幅</th></tr>
        </thead>
        <tbody>
          {rows.slice(-80).reverse().map(row => (
            <tr key={String(row.date)}>
              <td>{formatValue(row.date)}</td>
              <td>{formatValue(row.limit_up_count)}</td>
              <td>{formatValue(row.highest_board)}</td>
              <td>{formatPct(row.up_rate)}</td>
              <td>{formatPct(row.broken_rate)}</td>
              <td>{formatValue(row.hot_top20_heavy_fall_count)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function IntradayList({ rows }: { rows: Array<Record<string, unknown>> }) {
  return (
    <div className="emotion-list">
      {rows.slice(0, 60).map((row, index) => (
        <div className="emotion-list-row" key={`${row.alert_time}-${row.stock_code}-${index}`}>
          <strong>{formatValue(row.alert_time)} · {formatValue(row.stock_name)}</strong>
          <span>{formatValue(row.alert_type)} · {formatValue(row.change_pct)}%</span>
          <p>{formatValue(row.alert_text)}</p>
        </div>
      ))}
    </div>
  )
}

function PromotionTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  return (
    <div className="review-table-wrap">
      <table className="review-mini-table emotion-table">
        <thead>
          <tr><th>梯队</th><th>昨日</th><th>晋级</th><th>维持</th><th>断板</th><th>晋级率</th></tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={String(row.level)}>
              <td>{formatValue(row.level)}板</td>
              <td>{formatValue(row.total)}</td>
              <td>{formatValue(row.advanced)}</td>
              <td>{formatValue(row.maintained)}</td>
              <td>{formatValue(row.failed)}</td>
              <td>{formatPct(row.advancement_rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function StockRankTable({ rows, showCompare = false }: { rows: Array<Record<string, unknown>>; showCompare?: boolean }) {
  return (
    <div className="review-table-wrap">
      <table className="review-mini-table emotion-table">
        <thead>
          <tr><th>排名</th><th>股票</th><th>涨幅</th>{showCompare && <th>昨日</th>}{showCompare && <th>变化</th>}<th>金额/封单</th></tr>
        </thead>
        <tbody>
          {rows.slice(0, 40).map((row, index) => (
            <tr key={`${row.stock_code}-${index}`}>
              <td>{formatValue(row.rank_no ?? index + 1)}</td>
              <td>{formatValue(row.stock_name)} <span>{formatValue(row.stock_code)}</span></td>
              <td>{formatValue(row.change_pct)}%</td>
              {showCompare && <td>{formatValue(row.prev_rank_no)}</td>}
              {showCompare && <td>{formatSigned(row.rank_change)}</td>}
              <td>{formatMoney(row.amount ?? row.fengdan_money)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function GenericList({ rows }: { rows: Array<Record<string, unknown>> }) {
  return (
    <div className="emotion-list">
      {rows.slice(0, 40).map((row, index) => (
        <div className="emotion-list-row" key={index}>
          <strong>{formatValue(row.name ?? row.stock_name ?? row.date ?? index + 1)}</strong>
          <p>{JSON.stringify(row)}</p>
        </div>
      ))}
    </div>
  )
}

function metricLabel(key: string) {
  const labels: Record<string, string> = {
    score: '情绪分',
    level: '阶段',
    advice: '建议',
    limit_up_count: '涨停数',
    highest_board: '最高板',
    broken_rate: '炸板率',
    alert_count: '异动数',
    seal_success_rate: '封板率',
    hot_top20_avg_change_pct: '人气均涨幅',
    hot_top20_heavy_fall_count: '人气大跌',
    limit_down_count: '跌停',
    broken_limit_up_count: '炸板',
    days: '天数',
    max_limit_up_count: '峰值涨停',
    max_highest_board: '峰值高度',
    avg_up_rate: '平均红盘',
    stock_count: '股票数',
    top20_count: '人气数',
    avg_change_pct: '均涨幅',
    up_count: '上涨',
    down_count: '下跌',
    heavy_fall_count: '大跌',
    limit_up_overlap_count: '涨停重合',
    limit_up_overlap_rate: '重合率',
    current_count: '今日',
    prev_count: '昨日',
    new_count: '新上榜',
  }
  return labels[key] ?? key
}

function formatValue(value: unknown) {
  if (value == null || value === '') return '-'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2)
  if (typeof value === 'boolean') return value ? '是' : '否'
  return String(value)
}

function formatPct(value: unknown) {
  if (value == null || value === '') return '-'
  const num = Number(value)
  return Number.isFinite(num) ? `${num.toFixed(1)}%` : String(value)
}

function formatSigned(value: unknown) {
  if (value == null || value === '') return '-'
  const num = Number(value)
  if (!Number.isFinite(num)) return String(value)
  return num > 0 ? `+${num}` : String(num)
}

function formatMoney(value: unknown) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  if (Math.abs(num) >= 100000000) return `${(num / 100000000).toFixed(1)}亿`
  if (Math.abs(num) >= 10000) return `${(num / 10000).toFixed(1)}万`
  return String(num)
}
