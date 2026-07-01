import { useMemo, useState } from 'react'
import { useReviewSubmodule } from '../../hooks/useReview'
import type { ReviewPayload, ReviewSubmoduleKey } from '../../types'

type Row = Record<string, any>

interface ReviewModuleConfig {
  key: ReviewSubmoduleKey
  label: string
  params?: Record<string, string | number | undefined>
}

interface Props {
  date: string
}

const MODULES: ReviewModuleConfig[] = [
  { key: 'limit-up-reasons', label: '涨停原因' },
  { key: 'limit-up-tiers', label: '涨停梯队' },
  { key: 'price-tiers', label: '涨幅梯队', params: { days: 10 } },
  { key: 'promotions', label: '晋级' },
  { key: 'plate-rotation', label: '题材轮动', params: { days: 8, top_n: 12 } },
  { key: 'lhb', label: '龙虎榜' },
  { key: 'movement-alerts', label: '异动' },
]

const PAGE_SIZE = 30
const ALERT_PAGE_SIZE = 50

const SUMMARY_LABELS: Record<string, string> = {
  limit_up_count: '涨停数',
  first_board_count: '首板',
  multi_board_count: '连板',
  highest_board: '最高板',
  plate_count: '题材数',
  broken_count: '炸板数',
  tier_count: '梯队数',
  base_date: '基准日',
  total: '样本',
  advanced: '晋级',
  advancement_rate: '晋级率',
  count: '数量',
  buy_amount: '买入',
  sell_amount: '卖出',
  net_buy_amount: '净买',
  alert_count: '异动数',
  stock_count: '个股数',
  days: '天数',
  top_n: '展示',
}

function formatMoney(value: unknown) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-'
  if (Math.abs(value) >= 100000000) return `${(value / 100000000).toFixed(1)}亿`
  if (Math.abs(value) >= 10000) return `${(value / 10000).toFixed(0)}万`
  return value.toFixed(0)
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'number') {
    if (Math.abs(value) >= 10000) return formatMoney(value)
    return Number.isInteger(value) ? String(value) : value.toFixed(2)
  }
  if (typeof value === 'object') return '-'
  return String(value)
}

function formatPercent(value: unknown) {
  if (value === null || value === undefined || value === '') return '-'
  const numberValue = Number(value)
  if (Number.isNaN(numberValue)) return String(value)
  return `${numberValue.toFixed(2)}%`
}

function formatStatus(status?: string) {
  if (status === 'ok') return '正常'
  if (status === 'partial') return '部分数据'
  if (status === 'empty') return '暂无数据'
  if (status === 'error') return '异常'
  return '-'
}

function formatTierLabel(label: unknown, level: unknown) {
  if (level === 0 || label === 'broken-limit-up') return '炸板'
  if (level === 1 || label === 'first-board') return '首板'
  if (typeof level === 'number') return `${level}板`
  return formatValue(label)
}

function rowMatches(row: Row, keyword: string, fields: string[]) {
  const text = keyword.trim().toLowerCase()
  if (!text) return true
  return fields.some(field => String(row[field] || '').toLowerCase().includes(text))
}

function numberValue(value: unknown) {
  const parsed = Number(value || 0)
  return Number.isNaN(parsed) ? 0 : parsed
}

function SummaryStrip({ payload }: { payload: ReviewPayload | null }) {
  const summary = payload?.summary || {}
  const entries = Object.entries(summary).filter(([, value]) => {
    return value !== null && value !== undefined && typeof value !== 'object'
  })
  if (!entries.length) return null
  return (
    <div className="review-summary-strip">
      {entries.map(([key, value]) => (
        <div key={key}>
          <span>{SUMMARY_LABELS[key] || key}</span>
          <strong>{formatValue(value)}</strong>
        </div>
      ))}
    </div>
  )
}

function WarningList({ warnings }: { warnings: string[] }) {
  if (!warnings.length) return null
  return (
    <div className="review-warning-list">
      {warnings.map(item => <span key={item}>{item}</span>)}
    </div>
  )
}

function EmptyState({ loading, error }: { loading: boolean; error: string | null }) {
  if (loading) return <div className="review-empty">加载中...</div>
  if (error) return <div className="review-empty review-empty-error">{error}</div>
  return <div className="review-empty">暂无数据</div>
}

function Pagination({
  page,
  pageCount,
  onChange,
}: {
  page: number
  pageCount: number
  onChange: (page: number) => void
}) {
  if (pageCount <= 1) return null
  return (
    <div className="review-pagination">
      <span>{page} / {pageCount}</span>
      <button type="button" disabled={page <= 1} onClick={() => onChange(page - 1)}>上一页</button>
      <button type="button" disabled={page >= pageCount} onClick={() => onChange(page + 1)}>下一页</button>
    </div>
  )
}

function ReasonPage({ payload }: { payload: ReviewPayload | null }) {
  const rows = (payload?.items || []) as Row[]
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState('hot')
  const [coreOnly, setCoreOnly] = useState(false)

  const visibleRows = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    return rows
      .filter(plate => {
        if (!keyword) return true
        const plateText = [
          plate.plate_name,
          plate.plate_code,
          plate.plate_score,
          ...(plate.reasons || []).map((reason: Row) => reason.reason || reason.title),
        ].join(' ').toLowerCase()
        const stockMatched = (plate.stocks || []).some((stock: Row) => {
          const concepts = Array.isArray(stock.concepts) ? stock.concepts.join(' ') : stock.concepts
          return [stock.stock_name, stock.stock_code, stock.reason, stock.board_label, concepts]
            .join(' ')
            .toLowerCase()
            .includes(keyword)
        })
        return plateText.includes(keyword) || stockMatched
      })
      .sort((left, right) => {
        if (sortBy === 'count') return numberValue(right.limit_up_count) - numberValue(left.limit_up_count)
        if (sortBy === 'score') return numberValue(right.plate_score) - numberValue(left.plate_score)
        if (sortBy === 'name') return String(left.plate_name || '').localeCompare(String(right.plate_name || ''), 'zh-CN')
        return (
          numberValue(left.rank_no || 9999) - numberValue(right.rank_no || 9999) ||
          numberValue(right.limit_up_count) - numberValue(left.limit_up_count) ||
          numberValue(right.plate_score) - numberValue(left.plate_score)
        )
      })
  }, [rows, search, sortBy])

  return (
    <>
      <div className="review-filter-bar review-filter-bar-wide">
        <input
          type="search"
          value={search}
          placeholder="搜索题材、股票、代码、原因"
          onChange={event => setSearch(event.target.value)}
        />
        <select value={sortBy} onChange={event => setSortBy(event.target.value)}>
          <option value="hot">按热度排序</option>
          <option value="count">按涨停数排序</option>
          <option value="score">按强度排序</option>
          <option value="name">按名称排序</option>
        </select>
        <label className="review-check-option">
          <input type="checkbox" checked={coreOnly} onChange={event => setCoreOnly(event.target.checked)} />
          只看核心股
        </label>
        <span>显示 {visibleRows.length} / {rows.length} 个题材</span>
      </div>
      {!visibleRows.length ? <EmptyState loading={false} error={null} /> : null}
      <div className="review-module-grid">
      {visibleRows.map(plate => {
        const sortedStocks = [...(plate.stocks || [])].sort((left: Row, right: Row) => {
          return (
            numberValue(right.board_count) - numberValue(left.board_count) ||
            numberValue(right.seal_amount) - numberValue(left.seal_amount) ||
            String(left.limit_up_time || '').localeCompare(String(right.limit_up_time || ''))
          )
        })
        const coreStocks = sortedStocks.filter((stock: Row) => {
          return numberValue(stock.board_count) >= 2 || numberValue(stock.seal_amount) >= 100000000
        })
        const stocks = coreOnly ? (coreStocks.length ? coreStocks : sortedStocks.slice(0, 5)) : sortedStocks
        return (
        <section key={plate.plate_code || plate.plate_name} className="review-module-card">
          <div className="review-module-card-head">
            <div>
              <h3>{plate.plate_name}</h3>
              <span>
                {formatValue(plate.plate_code)}
                {plate.rank_no ? ` · 热度第 ${formatValue(plate.rank_no)}` : ''}
                {plate.plate_score ? ` · 强度 ${formatValue(plate.plate_score)}` : ''}
              </span>
            </div>
            <strong>{formatValue(plate.limit_up_count)} 家</strong>
          </div>
          <div className="review-tag-list">
            {(plate.reasons || []).map((reason: Row, index: number) => (
              <em key={`${plate.plate_code}-reason-${index}`}>{formatValue(reason.reason)}</em>
            ))}
          </div>
          <div className="review-stock-list review-stock-list-with-reason">
            {stocks.map((stock: Row) => (
              <span key={stock.stock_code}>
                <b>{stock.stock_name}</b>
                <small>{stock.stock_code}</small>
                <i>{formatValue(stock.reason)}</i>
                <em>{formatValue(stock.board_count)}板 · {formatValue(stock.limit_up_time)}</em>
              </span>
            ))}
          </div>
        </section>
      )})}
      </div>
    </>
  )
}

function LimitUpTierPage({ payload }: { payload: ReviewPayload | null }) {
  const rows = (payload?.items || []) as Row[]
  if (!rows.length) return <EmptyState loading={false} error={null} />
  return (
    <div className="review-module-grid">
      {rows.map(tier => (
        <section key={`${tier.label}-${tier.level}`} className="review-module-card">
          <div className="review-module-card-head">
            <div>
              <h3>{formatTierLabel(tier.label, tier.level)}</h3>
              <span>{formatValue(tier.count)} 只</span>
            </div>
          </div>
          <div className="review-stock-list">
            {(tier.stocks || []).map((stock: Row) => (
              <span key={stock.stock_code}>
                <b>{stock.stock_name}</b>
                <small>{stock.stock_code}</small>
                <em>{formatValue(stock.final_limit_up_time || stock.first_limit_up_time)}</em>
              </span>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

function PriceTierPage({ payload }: { payload: ReviewPayload | null }) {
  const rows = (payload?.items || []) as Row[]
  if (!rows.length) return <EmptyState loading={false} error={null} />
  return (
    <div className="review-module-grid">
      {rows.map(tier => (
        <section key={tier.label} className="review-module-card">
          <div className="review-module-card-head">
            <div>
              <h3>{tier.label}</h3>
              <span>{formatValue(tier.count)} 只</span>
            </div>
            <strong>{formatPercent(tier.avg_change_pct)}</strong>
          </div>
          <div className="review-table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>名称</th>
                  <th>代码</th>
                  <th>区间涨幅</th>
                  <th>起始日</th>
                  <th>结束日</th>
                  <th>样本天数</th>
                </tr>
              </thead>
              <tbody>
                {(tier.stocks || []).map((stock: Row) => (
                  <tr key={stock.stock_code}>
                    <td>{stock.stock_name}</td>
                    <td className="mono">{stock.stock_code}</td>
                    <td className="red">{formatPercent(stock.change_pct)}</td>
                    <td>{formatValue(stock.start_date)}</td>
                    <td>{formatValue(stock.end_date)}</td>
                    <td>{formatValue(stock.sample_days)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  )
}

function PromotionPage({ payload }: { payload: ReviewPayload | null }) {
  const rows = (payload?.items || []) as Row[]
  const [advancedOnly, setAdvancedOnly] = useState(false)
  const visibleRows = useMemo(() => {
    return rows
      .filter(row => !advancedOnly || numberValue(row.advanced) > 0)
      .sort((left, right) => numberValue(right.level) - numberValue(left.level))
  }, [rows, advancedOnly])

  if (!rows.length) return <EmptyState loading={false} error={null} />
  return (
    <>
      <div className="review-filter-bar review-filter-bar-compact">
        <label className="review-check-option">
          <input
            type="checkbox"
            checked={advancedOnly}
            onChange={event => setAdvancedOnly(event.target.checked)}
          />
          只看晋级成功
        </label>
        <span>显示 {visibleRows.length} / {rows.length} 个昨日梯队</span>
      </div>
      {!visibleRows.length ? <EmptyState loading={false} error={null} /> : null}
      <div className="review-promotion-matrix">
        {visibleRows.map(row => {
          const total = numberValue(row.total)
          const advanced = numberValue(row.advanced)
          const maintained = numberValue(row.maintained)
          const failed = numberValue(row.failed)
          const advancedWidth = total ? Math.round((advanced / total) * 100) : 0
          const maintainedWidth = total ? Math.round((maintained / total) * 100) : 0
          const failedWidth = Math.max(0, 100 - advancedWidth - maintainedWidth)
          const failedNames = Array.isArray(row.failed_names) ? row.failed_names : []

          return (
            <section key={row.level} className="review-promotion-card">
              <div className="review-module-card-head">
                <div>
                  <h3>昨日梯队：{formatValue(row.level)}板</h3>
                  <span>
                    今日结果：晋级 {formatValue(advanced)}，保持 {formatValue(maintained)}，断板 {formatValue(failed)}
                  </span>
                </div>
                <strong>{formatPercent(row.advancement_rate)}</strong>
              </div>
              <div className="review-promotion-flow">
                <span className="up" style={{ width: `${advancedWidth}%` }} />
                <span className="flat" style={{ width: `${maintainedWidth}%` }} />
                <span className="down" style={{ width: `${failedWidth}%` }} />
              </div>
              <div className="review-promotion-stats">
                <div>
                  <span>样本</span>
                  <strong>{formatValue(total)}</strong>
                </div>
                <div>
                  <span>晋级</span>
                  <strong>{formatValue(advanced)}</strong>
                </div>
                <div>
                  <span>保持</span>
                  <strong>{formatValue(maintained)}</strong>
                </div>
                <div>
                  <span>断板</span>
                  <strong>{formatValue(failed)}</strong>
                </div>
              </div>
              <div className="review-promotion-failed">
                <span>断板名单</span>
                <p>{failedNames.length ? failedNames.join('、') : '无'}</p>
              </div>
            </section>
          )
        })}
      </div>
    </>
  )
}

function PlateRotationPage({ payload }: { payload: ReviewPayload | null }) {
  const rows = (payload?.items || []) as Row[]
  const firstPlateCode = String(rows[0]?.plates?.[0]?.plate_code || payload?.summary?.selected_plate_code || '')
  const [selectedCode, setSelectedCode] = useState('')
  const activeCode = selectedCode || firstPlateCode
  const detailQuery = useReviewSubmodule('plate-rotation', payload?.date || '', {
    days: 8,
    top_n: 12,
    plate_code: activeCode || undefined,
  })
  const detailPayload = detailQuery.data || payload
  const detail = ((detailPayload as ReviewPayload & { detail?: Row | null })?.detail || null) as Row | null

  if (!rows.length) return <EmptyState loading={false} error={null} />
  return (
    <div className="review-rotation-layout">
      <div className="review-rotation-list">
        {rows.map(day => (
          <section key={day.date} className="review-module-card">
            <div className="review-module-card-head">
              <div>
                <h3>{day.date}</h3>
                <span>{(day.plates || []).length} 个题材</span>
              </div>
            </div>
            <div className="review-plate-tags">
              {(day.plates || []).map((plate: Row) => {
                const plateCode = String(plate.plate_code || '')
                return (
                  <button
                    key={`${day.date}-${plate.plate_code}`}
                    type="button"
                    className={plateCode === activeCode ? 'active' : ''}
                    onClick={() => setSelectedCode(plateCode)}
                  >
                    <b>{formatValue(plate.rank_no)}</b>
                    {plate.plate_name}
                    <em>{formatPercent(plate.rate)}</em>
                  </button>
                )
              })}
            </div>
          </section>
        ))}
      </div>

      <aside className="review-rotation-detail-panel">
        <div className="review-module-card-head">
          <div>
            <h3>{detail?.plate_name || '题材详情'}</h3>
            <span>{detail?.plate_code || activeCode || '-'}</span>
          </div>
          {detailQuery.loading ? <strong>加载中</strong> : null}
        </div>

        {!detail ? (
          <EmptyState loading={detailQuery.loading} error={detailQuery.error} />
        ) : (
          <>
            <section>
              <h4>趋势</h4>
              <div className="review-mini-table-wrap">
                <table className="review-mini-table">
                  <thead>
                    <tr>
                      <th>日期</th>
                      <th>涨幅</th>
                      <th>评分</th>
                      <th>速度</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(detail.trend || []).map((item: Row) => (
                      <tr key={`${detail.plate_code}-${item.trade_date}`}>
                        <td>{formatValue(item.trade_date)}</td>
                        <td className="red">{formatPercent(item.rate)}</td>
                        <td>{formatValue(item.score)}</td>
                        <td>{formatValue(item.speed)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section>
              <h4>入选原因</h4>
              {(detail.reasons || []).length ? (
                <div className="review-reason-list">
                  {(detail.reasons || []).map((reason: Row) => (
                    <article key={reason.msg_id || reason.title}>
                      <strong>{formatValue(reason.title)}</strong>
                      <p>{formatValue(reason.boomreason || reason.reason)}</p>
                      <span>涨停 {formatValue(reason.limit_up_count)} 家，强度 {formatValue(reason.strength_score)}</span>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="review-empty">暂无原因明细</div>
              )}
            </section>

            <section>
              <h4>代表个股</h4>
              <div className="review-mini-table-wrap">
                <table className="review-mini-table">
                  <thead>
                    <tr>
                      <th>排名</th>
                      <th>名称</th>
                      <th>代码</th>
                      <th>涨幅</th>
                      <th>换手</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(detail.stocks || []).map((stock: Row) => (
                      <tr key={stock.stock_code}>
                        <td>{formatValue(stock.rank_no)}</td>
                        <td>{stock.stock_name}</td>
                        <td className="mono">{stock.stock_code}</td>
                        <td className="red">{formatPercent(stock.change_pct)}</td>
                        <td>{formatPercent(stock.turnover_ratio)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </aside>
    </div>
  )
}

function LhbPage({ payload }: { payload: ReviewPayload | null }) {
  const rows = (payload?.items || []) as Row[]
  const [search, setSearch] = useState('')
  const [direction, setDirection] = useState('all')
  const [page, setPage] = useState(1)

  const filteredRows = useMemo(() => {
    return rows.filter(row => {
      const netBuy = Number(row.net_buy_amount || 0)
      const directionMatched =
        direction === 'all' ||
        (direction === 'buy' && netBuy >= 0) ||
        (direction === 'sell' && netBuy < 0)
      return directionMatched && rowMatches(row, search, ['stock_name', 'stock_code', 'reason', 'concepts'])
    })
  }, [rows, search, direction])

  const pageCount = Math.max(1, Math.ceil(filteredRows.length / PAGE_SIZE))
  const currentPage = Math.min(page, pageCount)
  const visibleRows = filteredRows.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  if (!rows.length) return <EmptyState loading={false} error={null} />
  return (
    <>
      <div className="review-filter-bar">
        <input
          type="search"
          value={search}
          placeholder="搜索股票、代码、原因、题材"
          onChange={event => { setSearch(event.target.value); setPage(1) }}
        />
        <select value={direction} onChange={event => { setDirection(event.target.value); setPage(1) }}>
          <option value="all">全部方向</option>
          <option value="buy">净买入</option>
          <option value="sell">净卖出</option>
        </select>
        <span>显示 {visibleRows.length} / {filteredRows.length} 条</span>
      </div>
      <div className="review-table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>名称</th>
              <th>代码</th>
              <th>上榜原因</th>
              <th>买入</th>
              <th>卖出</th>
              <th>净买</th>
              <th>题材</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map(row => (
              <tr key={`${row.stock_code}-${row.reason}`}>
                <td>{row.stock_name}</td>
                <td className="mono">{row.stock_code}</td>
                <td>{formatValue(row.reason)}</td>
                <td>{formatMoney(row.buy_amount)}</td>
                <td>{formatMoney(row.sell_amount)}</td>
                <td className={Number(row.net_buy_amount || 0) >= 0 ? 'red' : 'green'}>{formatMoney(row.net_buy_amount)}</td>
                <td>{formatValue(row.concepts)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={currentPage} pageCount={pageCount} onChange={setPage} />
    </>
  )
}

function AlertsPage({ payload }: { payload: ReviewPayload | null }) {
  const rows = (payload?.items || []) as Row[]
  const [search, setSearch] = useState('')
  const [alertType, setAlertType] = useState('all')
  const [page, setPage] = useState(1)
  const alertTypes = useMemo(() => {
    return Array.from(new Set(rows.map(row => String(row.alert_type || '')).filter(Boolean))).sort()
  }, [rows])
  const filteredRows = useMemo(() => {
    return rows.filter(row => {
      const typeMatched = alertType === 'all' || String(row.alert_type || '') === alertType
      return typeMatched && rowMatches(row, search, ['stock_name', 'stock_code', 'alert_type', 'alert_message'])
    })
  }, [rows, search, alertType])

  const pageCount = Math.max(1, Math.ceil(filteredRows.length / ALERT_PAGE_SIZE))
  const currentPage = Math.min(page, pageCount)
  const visibleRows = filteredRows.slice((currentPage - 1) * ALERT_PAGE_SIZE, currentPage * ALERT_PAGE_SIZE)

  if (!rows.length) return <EmptyState loading={false} error={null} />
  return (
    <>
      <div className="review-filter-bar">
        <input
          type="search"
          value={search}
          placeholder="搜索股票、代码、异动内容"
          onChange={event => { setSearch(event.target.value); setPage(1) }}
        />
        <select value={alertType} onChange={event => { setAlertType(event.target.value); setPage(1) }}>
          <option value="all">全部类型</option>
          {alertTypes.map(type => <option key={type} value={type}>{type}</option>)}
        </select>
        <span>显示 {visibleRows.length} / {filteredRows.length} 条</span>
      </div>
      <div className="review-table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>时间</th>
              <th>名称</th>
              <th>代码</th>
              <th>类型</th>
              <th>内容</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, index) => (
              <tr key={`${row.stock_code}-${row.alert_time}-${index}`}>
                <td>{formatValue(row.alert_time)}</td>
                <td>{row.stock_name}</td>
                <td className="mono">{row.stock_code}</td>
                <td>{formatValue(row.alert_type)}</td>
                <td>{formatValue(row.alert_message)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={currentPage} pageCount={pageCount} onChange={setPage} />
    </>
  )
}

function ModuleBody({
  activeKey,
  payload,
  loading,
  error,
}: {
  activeKey: ReviewSubmoduleKey
  payload: ReviewPayload | null
  loading: boolean
  error: string | null
}) {
  if (loading || error || !payload) return <EmptyState loading={loading} error={error} />
  if (activeKey === 'limit-up-reasons') return <ReasonPage payload={payload} />
  if (activeKey === 'limit-up-tiers') return <LimitUpTierPage payload={payload} />
  if (activeKey === 'price-tiers') return <PriceTierPage payload={payload} />
  if (activeKey === 'promotions') return <PromotionPage payload={payload} />
  if (activeKey === 'plate-rotation') return <PlateRotationPage payload={payload} />
  if (activeKey === 'lhb') return <LhbPage payload={payload} />
  return <AlertsPage payload={payload} />
}

export function ReviewWorkbench({ date }: Props) {
  const [activeKey, setActiveKey] = useState<ReviewSubmoduleKey>('limit-up-reasons')
  const active = useMemo(() => MODULES.find(item => item.key === activeKey) || MODULES[0], [activeKey])
  const { data, loading, error } = useReviewSubmodule(active.key, date, active.params || {})

  return (
    <div className="review-workbench">
      <div className="review-subtabs">
        {MODULES.map(item => (
          <button
            key={item.key}
            type="button"
            className={item.key === activeKey ? 'active' : ''}
            onClick={() => setActiveKey(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <section className="review-module-shell">
        <div className="review-module-top">
          <div>
            <h2>{active.label}</h2>
            <span>{date}</span>
          </div>
          <span className={`review-status review-status-${data?.status || 'empty'}`}>{formatStatus(data?.status)}</span>
        </div>
        <SummaryStrip payload={data} />
        <WarningList warnings={data?.warnings || []} />
        <ModuleBody activeKey={active.key} payload={data} loading={loading} error={error} />
      </section>
    </div>
  )
}
