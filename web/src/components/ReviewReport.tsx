import type { SavedReview } from '../types'

interface Props {
  review: SavedReview | null
}

function fmtMoney(value: number | null | undefined) {
  if (value == null) return '-'
  if (Math.abs(value) >= 100000000) return `${(value / 100000000).toFixed(1)}亿`
  if (Math.abs(value) >= 10000) return `${(value / 10000).toFixed(0)}万`
  return value.toFixed(0)
}

export function ReviewReport({ review }: Props) {
  if (!review) {
    return (
      <div className="card">
        <div className="card-header">复盘报告</div>
        <div className="card-body">
          <div className="report-empty">这一天还没有生成复盘结论，先运行生成脚本。</div>
        </div>
      </div>
    )
  }

  return (
    <div className="report-page">
      <div className="report-summary">
        <div>
          <div className="report-kicker">{review.trade_date}</div>
          <h2>复盘结论</h2>
          <p>{review.summary}</p>
        </div>
        <div className="report-scoreboard">
          <Metric label="涨停" value={`${review.limit_up_stock_count}`} />
          <Metric label="首板/连板" value={`${review.first_board_count}/${review.multi_board_count}`} />
          <Metric label="最高板" value={`${review.highest_board}板`} />
          <Metric label="板块数" value={`${review.limit_up_plate_count}`} />
        </div>
      </div>

      <div className="report-grid">
        <section className="card">
          <div className="card-header">主线板块</div>
          <div className="card-body report-list">
            {review.strongest_plates.map(plate => (
              <div key={plate.plate_code ?? plate.plate_name} className="report-plate">
                <div className="report-plate-head">
                  <strong>{plate.plate_name}</strong>
                  <span className="tag tag-red">{plate.stage ?? '观察'}</span>
                </div>
                <div className="report-muted">{plate.limit_up_count ?? 0}只涨停 · 强度 {plate.score ?? '-'}</div>
                {plate.stocks && plate.stocks.length > 0 && (
                  <div className="report-tags">
                    {plate.stocks.slice(0, 8).map(stock => <span key={stock} className="tag">{stock}</span>)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        <section className="card">
          <div className="card-header">核心个股</div>
          <div className="card-body report-list">
            {review.core_stocks.slice(0, 10).map(stock => (
              <div key={stock.stock_code} className="report-stock-row">
                <div>
                  <strong>{stock.stock_name}</strong>
                  <small>{stock.stock_code} · {stock.primary_plate ?? '-'}</small>
                </div>
                <div className="report-stock-meta">
                  <span className="tag tag-yellow">{stock.up_limit_keep_times ?? 1}板</span>
                  <span>{fmtMoney(stock.fengdan_money)}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="report-three">
        <TextList title="风险点" items={review.risk_flags} tone="green" />
        <TextList title="机会观察" items={review.opportunities} tone="red" />
        <TextList title="明日计划" items={review.next_plan} tone="blue" />
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="report-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function TextList({ title, items, tone }: { title: string; items: string[]; tone: 'red' | 'green' | 'blue' }) {
  return (
    <section className="card">
      <div className="card-header">{title}</div>
      <div className="card-body">
        <ul className={`report-bullets report-bullets-${tone}`}>
          {items.map((item, index) => <li key={`${title}-${index}`}>{item}</li>)}
        </ul>
      </div>
    </section>
  )
}
