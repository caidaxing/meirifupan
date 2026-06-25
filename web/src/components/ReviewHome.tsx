import { useEffect, useMemo, useState } from 'react'
import { fetchPlateRotation } from '../api/client'
import type {
  EmotionTrendItem,
  MarketOverviewTrendItem,
  PlateRotationData,
  PlateRotationRankItem,
  PlateRotationSelectedPlate,
  RecentHotPlate,
  RecentHotPlateStock,
  ReviewData,
} from '../types'
import type { TabKey } from './TabBar'
import { EmotionCycleChart } from './EmotionCycleChart'
import { ExpandableText } from './ExpandableText'
import { VolumeTrendChart } from './VolumeTrendChart'

interface Props {
  data: ReviewData
  emotionTrend: EmotionTrendItem[]
  marketTrend: MarketOverviewTrendItem[]
  plateRotation?: PlateRotationData | null
  onOpenTab: (tab: TabKey) => void
}

function fmtAmount(value: number | null | undefined) {
  if (value == null) return '-'
  return `${Math.round(value / 100000000)}亿`
}

function fmtSigned(value: number | null | undefined) {
  if (value == null) return '-'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

function fmtPct(value: number | null | undefined) {
  if (value == null) return '-'
  return `${value.toFixed(1)}%`
}

function fmtScore(value: number | null | undefined) {
  if (value == null) return '-'
  return Math.round(value).toLocaleString('zh-CN')
}

function fmtShortDate(value: string) {
  return value.slice(5).replace('-', '/')
}

function trendWord(value: number | null | undefined) {
  if (value == null) return '缺少对比'
  if (value >= 8) return '明显放量'
  if (value >= 2) return '温和放量'
  if (value <= -8) return '明显缩量'
  if (value <= -2) return '温和缩量'
  return '量能持平'
}

function emotionTone(score: number) {
  if (score >= 2.3) return '偏热'
  if (score >= 1.5) return '中性'
  if (score >= 0.8) return '偏冷'
  return '冰点'
}

function buildConclusion(data: ReviewData, latestMarket?: MarketOverviewTrendItem, prevMarket?: MarketOverviewTrendItem) {
  const amountText = fmtAmount(latestMarket?.amount ?? data.market_environment.breadth.amount)
  const changeText = fmtSigned(latestMarket?.amount_change_pct)
  const upRate = latestMarket?.up_rate ?? data.market_environment.breadth.up_rate
  const limitDown = latestMarket?.limit_down_count || data.market_environment.limit_down_total
  const broken = latestMarket?.broken_limit_up_count ?? data.market_environment.broken_limit_up_total
  const limitUp = latestMarket?.has_limit_up_events === false ? data.limit_up_stats.total : latestMarket?.limit_up_count ?? data.limit_up_stats.total
  const prevLimitUp = prevMarket?.has_limit_up_events === false ? data.limit_up_stats.prev_total : prevMarket?.limit_up_count ?? data.limit_up_stats.prev_total
  const limitDiff = limitUp - (prevLimitUp || 0)
  const score = data.emotion.total_score
  const tone = emotionTone(score)

  if (limitDown >= limitUp || broken >= limitUp * 0.45) {
    return `量能 ${amountText}，${trendWord(latestMarket?.amount_change_pct)}，但亏钱反馈偏重。涨停 ${limitUp} 只、跌停 ${limitDown} 只、炸板 ${broken} 只，情绪 ${tone}，先看风险释放是否结束。`
  }
  if ((latestMarket?.amount_change_pct ?? 0) > 0 && limitDiff > 0 && score >= 1.5) {
    return `量能 ${amountText}，较前一日 ${changeText}，涨停增加 ${limitDiff} 只，情绪 ${tone}。这类组合更适合围绕主线找强分歧后的回流。`
  }
  if ((latestMarket?.amount_change_pct ?? 0) < -5 && score < 1.5) {
    return `量能 ${amountText}，较前一日 ${changeText}，情绪 ${tone}。缩量叠加弱情绪时，不适合扩大出手范围。`
  }
  return `量能 ${amountText}，${trendWord(latestMarket?.amount_change_pct)}，红盘率 ${fmtPct(upRate)}。情绪 ${tone}，先看涨停数量和连板高度能否继续修复。`
}

function buildRotationSummary(plate: PlateRotationSelectedPlate | null | undefined, rank?: PlateRotationRankItem) {
  if (!plate) return '暂无题材详情'
  const latest = plate.trend.at(-1)
  const prev = plate.trend.at(-2)
  const rate = latest?.rate ?? rank?.rate
  const score = latest?.score ?? rank?.score
  if (latest?.score != null && prev?.score != null) {
    const diff = latest.score - prev.score
    const word = diff >= 0 ? '升温' : '降温'
    return `强度 ${fmtScore(score)}，涨幅 ${fmtSigned(rate)}，较前一日${word} ${fmtScore(Math.abs(diff))}。`
  }
  return `强度 ${fmtScore(score)}，涨幅 ${fmtSigned(rate)}。`
}

export function ReviewHome({ data, emotionTrend, marketTrend, plateRotation, onOpenTab }: Props) {
  const latestMarket = marketTrend.at(-1)
  const prevMarket = marketTrend.at(-2)
  const amountChange = latestMarket?.amount_change_pct
  const latestHasEvents = latestMarket?.has_limit_up_events !== false
  const limitDown = latestHasEvents ? latestMarket?.limit_down_count || data.market_environment.limit_down_total : data.market_environment.limit_down_total
  const broken = latestHasEvents ? latestMarket?.broken_limit_up_count ?? data.market_environment.broken_limit_up_total : data.market_environment.broken_limit_up_total
  const highBoard = latestHasEvents ? latestMarket?.highest_board ?? data.limit_up_stats.highest_board : data.limit_up_stats.highest_board
  const hotSummary = data.saved_review?.hot_stock_summary
  const recentHot = data.recent_hot_plates

  return (
    <div className="home-page">
      <section className="home-brief">
        <div>
          <div className="home-date">{data.date}</div>
          <h2>复盘首页</h2>
          <p>{buildConclusion(data, latestMarket, prevMarket)}</p>
        </div>
        <div className="home-score">
          <span>情绪指标</span>
          <strong>{data.emotion.total_score.toFixed(2)}</strong>
          <small>{data.emotion.level}</small>
        </div>
      </section>

      <section className="home-chart-grid">
        <div className="home-panel">
          <div className="home-panel-head">
            <div>
              <h3>量能趋势</h3>
              <span>每日成交额</span>
            </div>
            <strong>{fmtAmount(latestMarket?.amount)}</strong>
          </div>
          <VolumeTrendChart trend={marketTrend} />
          <div className="home-tips">
            <span>温馨提示</span>
            <p>红柱代表放量，绿柱代表缩量；黄线是近 5 日均量。复盘时先看量能是否支撑题材继续扩散。</p>
          </div>
        </div>

        <div className="home-panel">
          <div className="home-panel-head">
            <div>
              <h3>市场情绪</h3>
              <span>情绪分 + 涨停反馈</span>
            </div>
            <strong>{data.emotion.level}</strong>
          </div>
          <EmotionCycleChart emotionTrend={emotionTrend} marketTrend={marketTrend} />
          <div className="home-emotion-metrics">
            <Metric label="涨停家数" value={String(data.limit_up_stats.total)} tone="red" />
            <Metric label="跌停反馈" value={String(limitDown)} tone="green" />
            <Metric label="炸板反馈" value={String(broken)} tone="yellow" />
            <Metric label="连板高度" value={String(highBoard)} tone="purple" />
          </div>
        </div>
      </section>

      <PlateRotationBoard data={plateRotation} />

      <RecentHotPlateBoard dates={recentHot?.dates ?? []} plates={recentHot?.plates ?? []} />

      <section className="home-action-grid">
        <ActionCard
          title="盘前指引"
          value="8:30"
          text="结合昨日复盘、隔夜新闻公告和美股映射，早上先看方向。"
          onClick={() => onOpenTab('premarket-guide')}
        />
        <ActionCard
          title="量化全景"
          value={data.emotion.level}
          text="先看情绪、空间板、人气核心和亏钱反馈是否互相印证。"
          onClick={() => onOpenTab('quantzz-daily')}
        />
        <ActionCard
          title="涨停复盘"
          value={`${data.limit_up_stats.total}只`}
          text={`首板 ${data.limit_up_stats.first_board}，连板 ${data.limit_up_stats.multi_board}，最高 ${data.limit_up_stats.highest_board} 板。`}
          onClick={() => onOpenTab('limit-up-review')}
        />
        <ActionCard
          title="情绪复盘"
          value={hotSummary ? `${hotSummary.non_limit_up_count ?? 0}只` : data.emotion.level}
          text={hotSummary?.text ?? data.emotion.advice}
          onClick={() => onOpenTab('emotion-review')}
        />
        <ActionCard
          title="赚钱效应"
          value={amountChange == null ? '-' : fmtSigned(amountChange)}
          text={`成交额变化 ${fmtSigned(amountChange)}，红盘率 ${fmtPct(latestMarket?.up_rate ?? data.market_environment.breadth.up_rate)}。`}
          onClick={() => onOpenTab('profit-effect')}
        />
        <ActionCard
          title="数据总览"
          value={fmtAmount(latestMarket?.amount)}
          text="查看指数、跌停、炸板、龙虎榜和自动更新状态。"
          onClick={() => onOpenTab('data-overview')}
        />
      </section>
    </div>
  )
}

function findRankForPlate(data: PlateRotationData | null, plateCode?: string | null) {
  if (!data || !plateCode) return undefined
  for (const day of [...data.dates].reverse()) {
    const found = data.rank_by_date[day]?.find(item => item.plate_code === plateCode)
    if (found) return found
  }
  return undefined
}

function PlateRotationBoard({ data }: { data?: PlateRotationData | null }) {
  const [view, setView] = useState<PlateRotationData | null>(data ?? null)
  const [loadingCode, setLoadingCode] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setView(data ?? null)
    setLoadingCode(null)
    setError(null)
  }, [data])

  const selected = view?.selected_plate ?? null
  const selectedRank = useMemo(() => findRankForPlate(view, selected?.plate_code), [view, selected?.plate_code])
  const displayDates = useMemo(() => (view ? [...view.dates].reverse() : []), [view])
  const trend = selected?.trend.slice(-6) ?? []
  const maxScore = Math.max(1, ...trend.map(item => Math.abs(item.score ?? 0)))

  if (!view || view.dates.length === 0) {
    return (
      <section className="home-rotation">
        <div className="home-section-head">
          <div>
            <h3>题材轮动</h3>
            <span>暂无可用数据</span>
          </div>
        </div>
        <div className="home-empty-inline">等自动更新跑完后，这里会展示最近几天的题材强度、核心股和爆发原因。</div>
      </section>
    )
  }

  const openPlate = (plateCode: string) => {
    if (plateCode === selected?.plate_code || loadingCode) return
    setLoadingCode(plateCode)
    setError(null)
    fetchPlateRotation(view.date, view.dates.length || 8, 12, plateCode)
      .then(next => setView(next))
      .catch(e => setError(e.message ?? '题材详情加载失败'))
      .finally(() => setLoadingCode(null))
  }

  return (
    <section className="home-rotation">
      <div className="home-section-head">
        <div>
          <h3>题材轮动</h3>
          <span>{view.dates[0]} 至 {view.dates.at(-1)} · 资金强度榜</span>
        </div>
        <strong>{selected?.plate_name ?? '未选择'}</strong>
      </div>

      <div className="home-rotation-layout">
        <div className="home-rotation-scroll" aria-label="题材轮动排名">
          <div className="home-rotation-days">
            {displayDates.map(day => {
              const items = view.rank_by_date[day] ?? []
              return (
                <div className="home-rotation-day" key={day}>
                  <div className="home-rotation-day-head">
                    <strong>{fmtShortDate(day)}</strong>
                    <span>Top {items.length}</span>
                  </div>
                  <div className="home-rotation-list">
                    {items.slice(0, 10).map(item => (
                      <button
                        type="button"
                        className={`home-rotation-item ${item.plate_code === selected?.plate_code ? 'active' : ''}`}
                        key={`${day}-${item.plate_code}`}
                        onClick={() => openPlate(item.plate_code)}
                      >
                        <span className="home-rotation-rank">#{item.rank_no}</span>
                        <span className="home-rotation-name">{item.plate_name}</span>
                        <span className={item.rate != null && item.rate < 0 ? 'text-green' : 'text-red'}>
                          {fmtSigned(item.rate)}
                        </span>
                        <small>{loadingCode === item.plate_code ? '加载中' : fmtScore(item.score)}</small>
                      </button>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <aside className="home-rotation-detail">
          {selected ? (
            <>
              <div className="home-rotation-detail-head">
                <div>
                  <h4>{selected.plate_name}</h4>
                  <span>{selected.plate_code}</span>
                </div>
                <strong>{fmtSigned(selectedRank?.rate ?? trend.at(-1)?.rate)}</strong>
              </div>
              <p className="home-rotation-summary">{buildRotationSummary(selected, selectedRank)}</p>
              {error && <div className="home-rotation-error">{error}</div>}

              <div className="home-rotation-mini-trend">
                {trend.map(item => (
                  <div className="home-rotation-trend-row" key={`${selected.plate_code}-${item.trade_date}`}>
                    <span>{fmtShortDate(item.trade_date)}</span>
                    <div>
                      <i
                        className={item.rate != null && item.rate < 0 ? 'down' : 'up'}
                        style={{ width: `${Math.max(6, Math.min(100, Math.abs(item.score ?? 0) / maxScore * 100))}%` }}
                      />
                    </div>
                    <strong>{fmtScore(item.score)}</strong>
                  </div>
                ))}
              </div>

              <div className="home-rotation-detail-grid">
                <div className="home-rotation-block">
                  <h5>核心个股</h5>
                  <div className="home-rotation-stocks">
                    {selected.stocks.slice(0, 8).map(stock => (
                      <div className="home-rotation-stock" key={`${stock.trade_date}-${stock.stock_code}`}>
                        <div>
                          <strong>{stock.stock_name}</strong>
                          <span>{stock.stock_code}</span>
                        </div>
                        <small className={stock.change_pct != null && stock.change_pct < 0 ? 'text-green' : 'text-red'}>
                          {fmtSigned(stock.change_pct)}
                        </small>
                      </div>
                    ))}
                    {selected.stocks.length === 0 && <span className="home-empty-mini">暂无核心股</span>}
                  </div>
                </div>

                <div className="home-rotation-block">
                  <h5>爆发原因</h5>
                  <div className="home-rotation-reasons">
                    {selected.reasons.slice(0, 4).map(reason => (
                      <article className="home-rotation-reason" key={`${reason.date}-${reason.msg_id}`}>
                        <div className="home-rotation-reason-head">
                          <strong>{reason.title || '题材异动'}</strong>
                          <span>{reason.date}</span>
                        </div>
                        <ExpandableText text={reason.boomreason} lines={2} emptyText="暂无原因" />
                      </article>
                    ))}
                    {selected.reasons.length === 0 && <span className="home-empty-mini">暂无原因明细</span>}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="home-empty-inline">选择一个题材后查看趋势、核心股和原因。</div>
          )}
        </aside>
      </div>
    </section>
  )
}

function RecentHotPlateBoard({ dates, plates }: { dates: string[]; plates: RecentHotPlate[] }) {
  if (plates.length === 0) {
    return (
      <section className="home-recent-plates">
        <div className="home-section-head">
          <div>
            <h3>近5日热门板块</h3>
            <span>暂无可用板块数据</span>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="home-recent-plates">
      <div className="home-section-head">
        <div>
          <h3>近5日热门板块和前排股</h3>
          <span>{dates[0]} 至 {dates[dates.length - 1]}</span>
        </div>
        <strong>{plates.length} 个板块</strong>
      </div>
      <div className="home-plate-board">
        {plates.map(plate => (
          <RecentHotPlateCard key={plate.plate_code} plate={plate} />
        ))}
      </div>
    </section>
  )
}

function RecentHotPlateCard({ plate }: { plate: RecentHotPlate }) {
  return (
    <article className="home-plate-card">
      <div className="home-plate-card-head">
        <div>
          <h4>{plate.plate_name}</h4>
          <span>
            活跃 {plate.active_days} 天 · 涨停 {plate.limit_up_count} 次 · 今日 {plate.today_limit_up_count} 只
          </span>
        </div>
        <em>#{plate.best_rank}</em>
      </div>
      <div className="home-plate-stocks">
        {plate.stocks.map(stock => (
          <RecentHotStockPill key={stock.stock_code} stock={stock} />
        ))}
      </div>
    </article>
  )
}

function RecentHotStockPill({ stock }: { stock: RecentHotPlateStock }) {
  const board = stock.today_board ?? stock.max_board
  return (
    <div className={`home-stock-pill ${stock.is_today_limit_up ? 'active' : ''}`}>
      <div>
        <strong>{stock.stock_name}</strong>
        <span>{stock.stock_code}</span>
      </div>
      <small>
        {board > 1 ? `${board}板` : '首板'}
        {stock.active_days > 1 ? ` · ${stock.active_days}日` : ''}
      </small>
    </div>
  )
}

function Metric({ label, value, tone }: { label: string; value: string; tone: 'red' | 'green' | 'yellow' | 'purple' }) {
  return (
    <div className="home-emotion-metric">
      <span>{label}</span>
      <strong className={`text-${tone}`}>{value}</strong>
    </div>
  )
}

function ActionCard({ title, value, text, onClick }: { title: string; value: string; text: string; onClick: () => void }) {
  return (
    <button className="home-action-card" onClick={onClick}>
      <span>{title}</span>
      <strong>{value}</strong>
      <p>{text}</p>
    </button>
  )
}
