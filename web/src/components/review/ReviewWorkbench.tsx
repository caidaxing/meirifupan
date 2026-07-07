import { useMemo, useState } from 'react'
import { useReviewSubmodule } from '../../hooks/useReview'
import type { ReactNode } from 'react'
import type { ReviewPayload } from '../../types'

type Row = Record<string, any>

interface Props {
  date: string
}

const LHB_PAGE_SIZE = 50
const ALERT_PAGE_SIZE = 50
const MODULE_TABS = [
  { key: 'limit-up-reasons', label: '题材涨停', desc: '按题材和涨停原因归类，先看当天主线在哪里。' },
  { key: 'limit-up-tiers', label: '空间梯队', desc: '把涨停股按首板、连板和空间高度展开。' },
  { key: 'promotions', label: '晋级断板', desc: '看昨日梯队今天的晋级、保持和失败情况。' },
  { key: 'plate-rotation', label: '题材轮动', desc: '跟踪近几日题材强弱变化和代表个股。' },
  { key: 'lhb', label: '资金验证', desc: '用龙虎榜验证涨停主线、净买方向和风险释放。' },
  { key: 'movement-alerts', label: '异动补充', desc: '补充盘中异动，辅助理解强势股和题材催化。' },
] as const

type ModuleTabKey = typeof MODULE_TABS[number]['key']

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
  distinct_stock_count: '上榜股',
  limit_up_stock_count: '涨停上榜',
  net_buy_count: '净买数',
  net_sell_count: '净卖数',
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
                <i title={formatValue(stock.reason)}>
                  <strong>涨停原因</strong>
                  {formatValue(stock.reason)}
                </i>
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
  const [viewMode, setViewMode] = useState<'mindmap' | 'table'>('mindmap')
  const [search, setSearch] = useState('')
  const [direction, setDirection] = useState('all')
  const [scope, setScope] = useState('all')
  const [reason, setReason] = useState('all')
  const [page, setPage] = useState(1)
  const reasons = useMemo(() => {
    return Array.from(new Set(rows.map(row => String(row.reason || '')).filter(Boolean))).sort()
  }, [rows])
  const reasonStats = useMemo(() => {
    const counts = new Map<string, number>()
    rows.forEach(row => {
      const key = String(row.reason || '未分类')
      counts.set(key, (counts.get(key) || 0) + 1)
    })
    return Array.from(counts.entries())
      .sort((left, right) => right[1] - left[1])
      .slice(0, 8)
      .map(([name, count]) => ({ name, count }))
  }, [rows])

  const filteredRows = useMemo(() => {
    return rows.filter(row => {
      const netBuy = Number(row.net_buy_amount || 0)
      const directionMatched =
        direction === 'all' ||
        (direction === 'buy' && netBuy >= 0) ||
        (direction === 'sell' && netBuy < 0)
      const scopeMatched =
        scope === 'all' ||
        (scope === 'limit-up' && row.is_limit_up) ||
        (scope === 'normal' && !row.is_limit_up)
      const reasonMatched = reason === 'all' || String(row.reason || '') === reason
      return directionMatched && scopeMatched && reasonMatched && rowMatches(row, search, [
        'stock_name',
        'stock_code',
        'reason',
        'concepts',
        'interpretation',
      ])
    })
  }, [rows, search, direction, scope, reason])
  const mindMapSections = useMemo(() => buildLhbMindMap(filteredRows), [filteredRows])

  const pageCount = Math.max(1, Math.ceil(filteredRows.length / LHB_PAGE_SIZE))
  const currentPage = Math.min(page, pageCount)
  const visibleRows = filteredRows.slice((currentPage - 1) * LHB_PAGE_SIZE, currentPage * LHB_PAGE_SIZE)

  if (!rows.length) return <EmptyState loading={false} error={null} />
  return (
    <>
      <div className="lhb-reason-strip">
        {reasonStats.map(item => (
          <button
            key={item.name}
            type="button"
            className={reason === item.name ? 'active' : ''}
            onClick={() => { setReason(reason === item.name ? 'all' : item.name); setPage(1) }}
          >
            <strong>{item.name}</strong>
            <span>{item.count}</span>
          </button>
        ))}
      </div>
      <div className="lhb-view-switch">
        <button
          type="button"
          className={viewMode === 'mindmap' ? 'active' : ''}
          onClick={() => setViewMode('mindmap')}
        >
          思维导图
        </button>
        <button
          type="button"
          className={viewMode === 'table' ? 'active' : ''}
          onClick={() => setViewMode('table')}
        >
          明细表
        </button>
      </div>
      <div className="review-filter-bar">
        <input
          type="search"
          value={search}
          placeholder="搜索股票、代码、原因、解读、题材"
          onChange={event => { setSearch(event.target.value); setPage(1) }}
        />
        <select value={direction} onChange={event => { setDirection(event.target.value); setPage(1) }}>
          <option value="all">全部方向</option>
          <option value="buy">净买入</option>
          <option value="sell">净卖出</option>
        </select>
        <select value={scope} onChange={event => { setScope(event.target.value); setPage(1) }}>
          <option value="all">全部股票</option>
          <option value="limit-up">只看涨停上榜</option>
          <option value="normal">非涨停上榜</option>
        </select>
        <select value={reason} onChange={event => { setReason(event.target.value); setPage(1) }}>
          <option value="all">全部原因</option>
          {reasons.map(item => <option key={item} value={item}>{item}</option>)}
        </select>
        <span>{viewMode === 'mindmap' ? `导图覆盖 ${filteredRows.length} 条` : `显示 ${visibleRows.length} / ${filteredRows.length} 条`}</span>
      </div>
      {viewMode === 'mindmap' ? (
        <LhbMindMap
          summary={(payload?.summary || {}) as Row}
          total={filteredRows.length}
          sections={mindMapSections}
        />
      ) : (
        <>
      <div className="review-table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>名称</th>
              <th>代码</th>
              <th>状态</th>
              <th>上榜原因</th>
              <th>涨幅</th>
              <th>换手</th>
              <th>买入</th>
              <th>卖出</th>
              <th>净买</th>
              <th>解读</th>
              <th>题材</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map(row => (
              <tr key={`${row.stock_code}-${row.reason}`}>
                <td>{row.stock_name}</td>
                <td className="mono">{row.stock_code}</td>
                <td>{row.is_limit_up ? formatTierLabel(row.board_label, row.board_level) : '-'}</td>
                <td>{formatValue(row.reason)}</td>
                <td className={Number(row.change_pct || 0) >= 0 ? 'red' : 'green'}>{formatPercent(row.change_pct)}</td>
                <td>{formatPercent(row.turnover_rate)}</td>
                <td>{formatMoney(row.buy_amount)}</td>
                <td>{formatMoney(row.sell_amount)}</td>
                <td className={Number(row.net_buy_amount || 0) >= 0 ? 'red' : 'green'}>{formatMoney(row.net_buy_amount)}</td>
                <td>{formatValue(row.interpretation)}</td>
                <td>{formatValue(row.concepts)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={currentPage} pageCount={pageCount} onChange={setPage} />
        </>
      )}
    </>
  )
}

function buildLhbMindMap(rows: Row[]) {
  const byNetBuy = [...rows].sort((left, right) => numberValue(right.net_buy_amount) - numberValue(left.net_buy_amount))
  const byNetSell = [...rows].sort((left, right) => numberValue(left.net_buy_amount) - numberValue(right.net_buy_amount))
  const byLimitUp = rows
    .filter(row => row.is_limit_up)
    .sort((left, right) => (
      numberValue(right.board_level) - numberValue(left.board_level) ||
      numberValue(right.net_buy_amount) - numberValue(left.net_buy_amount)
    ))
  const reasonMap = new Map<string, { count: number; net: number; examples: Row[] }>()
  rows.forEach(row => {
    const key = String(row.reason || '未分类')
    const current = reasonMap.get(key) || { count: 0, net: 0, examples: [] }
    current.count += 1
    current.net += numberValue(row.net_buy_amount)
    if (current.examples.length < 3) current.examples.push(row)
    reasonMap.set(key, current)
  })
  const reasonGroups = Array.from(reasonMap.entries())
    .sort((left, right) => right[1].count - left[1].count)
    .slice(0, 6)

  return [
    {
      key: 'buy',
      title: '净买入主线',
      tone: 'red',
      meta: `${rows.filter(row => numberValue(row.net_buy_amount) >= 0).length} 条`,
      items: byNetBuy.filter(row => numberValue(row.net_buy_amount) > 0).slice(0, 6).map(row => ({
        title: `${row.stock_name} ${row.stock_code}`,
        meta: `净买 ${formatMoney(row.net_buy_amount)} · 涨幅 ${formatPercent(row.change_pct)}`,
        desc: row.interpretation || row.reason,
      })),
    },
    {
      key: 'sell',
      title: '净卖出压力',
      tone: 'green',
      meta: `${rows.filter(row => numberValue(row.net_buy_amount) < 0).length} 条`,
      items: byNetSell.filter(row => numberValue(row.net_buy_amount) < 0).slice(0, 6).map(row => ({
        title: `${row.stock_name} ${row.stock_code}`,
        meta: `净卖 ${formatMoney(Math.abs(numberValue(row.net_buy_amount)))} · 涨幅 ${formatPercent(row.change_pct)}`,
        desc: row.interpretation || row.reason,
      })),
    },
    {
      key: 'limit-up',
      title: '涨停上榜',
      tone: 'blue',
      meta: `${byLimitUp.length} 条`,
      items: byLimitUp.slice(0, 8).map(row => ({
        title: `${row.stock_name} ${row.stock_code}`,
        meta: `${formatTierLabel(row.board_label, row.board_level)} · 净买 ${formatMoney(row.net_buy_amount)}`,
        desc: row.reason,
      })),
    },
    {
      key: 'reason',
      title: '上榜原因分布',
      tone: 'yellow',
      meta: `${reasonMap.size} 类`,
      items: reasonGroups.map(([name, item]) => ({
        title: name,
        meta: `${item.count} 条 · 净额 ${formatMoney(item.net)}`,
        desc: item.examples.map(row => row.stock_name).filter(Boolean).join('、'),
      })),
    },
  ]
}

function LhbMindMap({
  summary,
  total,
  sections,
}: {
  summary: Row
  total: number
  sections: Array<{
    key: string
    title: string
    tone: string
    meta: string
    items: Array<{ title: string; meta: string; desc?: unknown }>
  }>
}) {
  return (
    <div className="lhb-mindmap">
      <div className="lhb-mindmap-root">
        <span>当日龙虎榜</span>
        <strong>{formatValue(summary.distinct_stock_count || total)} 只上榜股</strong>
        <em>涨停上榜 {formatValue(summary.limit_up_stock_count)} · 净买 {formatMoney(summary.net_buy_amount)}</em>
      </div>
      <div className="lhb-mindmap-branches">
        {sections.map(section => (
          <section className={`lhb-mindmap-branch lhb-mindmap-${section.tone}`} key={section.key}>
            <div className="lhb-mindmap-branch-head">
              <strong>{section.title}</strong>
              <span>{section.meta}</span>
            </div>
            <div className="lhb-mindmap-items">
              {section.items.length ? section.items.map(item => (
                <article key={`${section.key}-${item.title}`}>
                  <strong>{item.title}</strong>
                  <span>{item.meta}</span>
                  {item.desc ? <p>{formatValue(item.desc)}</p> : null}
                </article>
              )) : <div className="review-empty">暂无匹配数据</div>}
            </div>
          </section>
        ))}
      </div>
    </div>
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

function ReviewSection({
  id,
  title,
  desc,
  payload,
  loading,
  error,
  children,
}: {
  id: string
  title: string
  desc: string
  payload: ReviewPayload | null
  loading: boolean
  error: string | null
  children: ReactNode
}) {
  return (
    <section id={id} className="review-module-shell review-tab-panel">
      <div className="review-module-top">
        <div>
          <h2>{title}</h2>
          <span>{desc}</span>
        </div>
        <span className={`review-status review-status-${payload?.status || 'empty'}`}>{formatStatus(payload?.status)}</span>
      </div>
      <SummaryStrip payload={payload} />
      <WarningList warnings={payload?.warnings || []} />
      {loading || error || !payload ? <EmptyState loading={loading} error={error} /> : children}
    </section>
  )
}

function LimitUpOverview({
  date,
  reasonPayload,
  tierPayload,
  promotionPayload,
  lhbPayload,
}: {
  date: string
  reasonPayload: ReviewPayload | null
  tierPayload: ReviewPayload | null
  promotionPayload: ReviewPayload | null
  lhbPayload: ReviewPayload | null
}) {
  const reasonSummary = (reasonPayload?.summary || {}) as Row
  const tierSummary = (tierPayload?.summary || {}) as Row
  const promotionSummary = (promotionPayload?.summary || {}) as Row
  const lhbSummary = (lhbPayload?.summary || {}) as Row
  const topPlate = ((reasonPayload?.items || []) as Row[])[0]

  return (
    <section className="review-limitup-brief">
      <div>
        <span className="section-kicker">涨停复盘</span>
        <h2>{date}</h2>
        <p>
          当日涨停 {formatValue(reasonSummary.limit_up_count)} 只，
          最高 {formatValue(reasonSummary.highest_board || tierSummary.highest_board)} 板。
          {topPlate?.plate_name ? ` 题材上先看 ${topPlate.plate_name}，` : ' '}
          龙虎榜里涨停上榜 {formatValue(lhbSummary.limit_up_stock_count)} 只，净买合计 {formatMoney(lhbSummary.net_buy_amount)}。
        </p>
      </div>
      <div className="review-limitup-metrics">
        <MetricCard label="涨停数" value={formatValue(reasonSummary.limit_up_count)} />
        <MetricCard label="首板" value={formatValue(reasonSummary.first_board_count)} />
        <MetricCard label="连板" value={formatValue(reasonSummary.multi_board_count)} />
        <MetricCard label="最高板" value={formatValue(reasonSummary.highest_board || tierSummary.highest_board)} />
        <MetricCard label="晋级" value={formatValue(promotionSummary.advanced)} />
        <MetricCard label="涨停龙虎" value={formatValue(lhbSummary.limit_up_stock_count)} />
      </div>
    </section>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="review-limitup-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

export function ReviewWorkbench({ date }: Props) {
  const [activeModule, setActiveModule] = useState<ModuleTabKey>('limit-up-reasons')
  const reasons = useReviewSubmodule('limit-up-reasons', date)
  const tiers = useReviewSubmodule('limit-up-tiers', date)
  const promotions = useReviewSubmodule('promotions', date)
  const rotation = useReviewSubmodule('plate-rotation', date, { days: 8, top_n: 12 })
  const lhb = useReviewSubmodule('lhb', date)
  const alerts = useReviewSubmodule('movement-alerts', date)
  const activeTab = MODULE_TABS.find(tab => tab.key === activeModule) || MODULE_TABS[0]

  const renderActiveModule = () => {
    if (activeModule === 'limit-up-tiers') {
      return (
        <ReviewSection
          id={activeTab.key}
          title={activeTab.label}
          desc={activeTab.desc}
          payload={tiers.data}
          loading={tiers.loading}
          error={tiers.error}
        >
          <LimitUpTierPage payload={tiers.data} />
        </ReviewSection>
      )
    }
    if (activeModule === 'promotions') {
      return (
        <ReviewSection
          id={activeTab.key}
          title={activeTab.label}
          desc={activeTab.desc}
          payload={promotions.data}
          loading={promotions.loading}
          error={promotions.error}
        >
          <PromotionPage payload={promotions.data} />
        </ReviewSection>
      )
    }
    if (activeModule === 'plate-rotation') {
      return (
        <ReviewSection
          id={activeTab.key}
          title={activeTab.label}
          desc={activeTab.desc}
          payload={rotation.data}
          loading={rotation.loading}
          error={rotation.error}
        >
          <PlateRotationPage payload={rotation.data} />
        </ReviewSection>
      )
    }
    if (activeModule === 'lhb') {
      return (
        <ReviewSection
          id={activeTab.key}
          title={activeTab.label}
          desc={activeTab.desc}
          payload={lhb.data}
          loading={lhb.loading}
          error={lhb.error}
        >
          <LhbPage payload={lhb.data} />
        </ReviewSection>
      )
    }
    if (activeModule === 'movement-alerts') {
      return (
        <ReviewSection
          id={activeTab.key}
          title={activeTab.label}
          desc={activeTab.desc}
          payload={alerts.data}
          loading={alerts.loading}
          error={alerts.error}
        >
          <AlertsPage payload={alerts.data} />
        </ReviewSection>
      )
    }
    return (
      <ReviewSection
        id={activeTab.key}
        title={activeTab.label}
        desc={activeTab.desc}
        payload={reasons.data}
        loading={reasons.loading}
        error={reasons.error}
      >
        <ReasonPage payload={reasons.data} />
      </ReviewSection>
    )
  }

  return (
    <div className="review-workbench review-integrated">
      <LimitUpOverview
        date={date}
        reasonPayload={reasons.data}
        tierPayload={tiers.data}
        promotionPayload={promotions.data}
        lhbPayload={lhb.data}
      />
      <div className="review-module-tabs" role="tablist" aria-label="涨停复盘模块">
        {MODULE_TABS.map(item => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={activeModule === item.key}
            className={activeModule === item.key ? 'active' : ''}
            onClick={() => setActiveModule(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {renderActiveModule()}
    </div>
  )
}
