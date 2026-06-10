import type { HotData, HotStockRank, HotBoardRank, MultiSourceHotStockRank } from '../types'

interface Props {
  data: HotData
}

export function HotView({ data }: Props) {
  return (
    <div className="insight-container">
      <HotStocksTable stocks={data.hot_stocks} />
      <div className="insight-row">
        <ThsHotTable stocks={data.ths_hot ?? []} title="同花顺热榜 Top 30" />
        <ThsHotTable stocks={data.ths_skyrocket ?? []} title="同花顺飙升榜 Top 30" />
      </div>
      <div className="insight-row">
        <HotBoardsTable boards={data.industry_boards} title="行业板块" />
        <HotBoardsTable boards={data.concept_boards} title="概念板块" />
      </div>
    </div>
  )
}

function HotStocksTable({ stocks }: { stocks: HotStockRank[] }) {
  if (stocks.length === 0) {
    return (
      <div className="card" style={{ marginBottom: '16px' }}>
        <div className="card-header">人气股票 Top 30</div>
        <div className="card-body" style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '40px' }}>
          无数据
        </div>
      </div>
    )
  }

  return (
    <div className="card" style={{ marginBottom: '16px' }}>
      <div className="card-header">人气股票 Top 30</div>
      <div className="card-body" style={{ padding: 0, maxHeight: '500px', overflowY: 'auto' }}>
        <table className="table">
          <thead>
            <tr>
              <th>#</th>
              <th>代码</th>
              <th>名称</th>
              <th>最新价</th>
              <th>涨跌幅</th>
              <th>涨跌额</th>
            </tr>
          </thead>
          <tbody>
            {stocks.map(s => (
              <tr key={s.stock_code}>
                <td style={{
                  color: s.rank_no <= 3 ? 'var(--color-red)' : 'var(--text-secondary)',
                  fontWeight: s.rank_no <= 3 ? 700 : 400,
                }}>
                  {s.rank_no}
                </td>
                <td style={{ fontFamily: 'monospace', fontSize: '12px' }}>{s.stock_code}</td>
                <td style={{ fontWeight: 600 }}>{s.stock_name ?? '-'}</td>
                <td style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {s.latest_price != null ? s.latest_price.toFixed(2) : '-'}
                </td>
                <td style={{
                  fontVariantNumeric: 'tabular-nums',
                  fontWeight: 600,
                  color: s.change_pct != null
                    ? s.change_pct > 0 ? 'var(--color-red)'
                    : s.change_pct < 0 ? 'var(--color-green)'
                    : 'var(--text-secondary)'
                    : 'var(--text-secondary)',
                }}>
                  {s.change_pct != null ? `${s.change_pct > 0 ? '+' : ''}${s.change_pct.toFixed(2)}%` : '-'}
                </td>
                <td style={{
                  fontVariantNumeric: 'tabular-nums',
                  color: s.change_amount != null
                    ? s.change_amount > 0 ? 'var(--color-red)'
                    : s.change_amount < 0 ? 'var(--color-green)'
                    : 'var(--text-secondary)'
                    : 'var(--text-secondary)',
                }}>
                  {s.change_amount != null ? `${s.change_amount > 0 ? '+' : ''}${s.change_amount.toFixed(2)}` : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ThsHotTable({ stocks, title }: { stocks: MultiSourceHotStockRank[]; title: string }) {
  if (stocks.length === 0) {
    return (
      <div className="card insight-card">
        <div className="card-header">{title}</div>
        <div className="card-body" style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '40px' }}>
          无数据
        </div>
      </div>
    )
  }

  return (
    <div className="card insight-card">
      <div className="card-header">{title}</div>
      <div className="card-body" style={{ padding: 0, maxHeight: '500px', overflowY: 'auto' }}>
        <table className="table">
          <thead>
            <tr>
              <th>#</th>
              <th>名称</th>
              <th>涨跌幅</th>
              <th>热度</th>
              <th>变化</th>
              <th>标签</th>
            </tr>
          </thead>
          <tbody>
            {stocks.map(s => (
              <tr key={`${s.period}-${s.list_type}-${s.stock_code}`}>
                <td style={{
                  color: s.rank_no <= 3 ? 'var(--color-red)' : 'var(--text-secondary)',
                  fontWeight: s.rank_no <= 3 ? 700 : 400,
                }}>
                  {s.rank_no}
                </td>
                <td>
                  <div style={{ fontWeight: 700 }}>{s.stock_name ?? '-'}</div>
                  <div style={{ fontFamily: 'monospace', fontSize: '11px', color: 'var(--text-tertiary)' }}>
                    {s.stock_code}
                  </div>
                </td>
                <td style={{
                  fontVariantNumeric: 'tabular-nums',
                  fontWeight: 600,
                  color: s.change_pct != null
                    ? s.change_pct > 0 ? 'var(--color-red)'
                    : s.change_pct < 0 ? 'var(--color-green)'
                    : 'var(--text-secondary)'
                    : 'var(--text-secondary)',
                }}>
                  {s.change_pct != null ? `${s.change_pct > 0 ? '+' : ''}${s.change_pct.toFixed(2)}%` : '-'}
                </td>
                <td style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {s.hot_value != null ? Math.round(s.hot_value).toLocaleString('zh-CN') : '-'}
                </td>
                <td style={{
                  fontVariantNumeric: 'tabular-nums',
                  color: s.rank_change != null && s.rank_change > 0
                    ? 'var(--color-red)'
                    : s.rank_change != null && s.rank_change < 0
                    ? 'var(--color-green)'
                    : 'var(--text-secondary)',
                }}>
                  {s.rank_change != null ? `${s.rank_change > 0 ? '+' : ''}${s.rank_change}` : '-'}
                </td>
                <td>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                    {s.popularity_tag && <span className="tag tag-blue">{s.popularity_tag}</span>}
                    {s.concept_tags.slice(0, 2).map(tag => (
                      <span className="tag" key={tag}>{tag}</span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function HotBoardsTable({ boards, title }: { boards: HotBoardRank[]; title: string }) {
  if (boards.length === 0) {
    return (
      <div className="card insight-card">
        <div className="card-header">{title}</div>
        <div className="card-body" style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '40px' }}>
          无数据
        </div>
      </div>
    )
  }

  return (
    <div className="card insight-card">
      <div className="card-header">{title} Top 20</div>
      <div className="card-body" style={{ padding: 0, maxHeight: '500px', overflowY: 'auto' }}>
        <table className="table">
          <thead>
            <tr>
              <th>#</th>
              <th>板块</th>
              <th>涨跌幅</th>
              <th>领涨股</th>
              <th>上涨</th>
              <th>下跌</th>
            </tr>
          </thead>
          <tbody>
            {boards.map(b => (
              <tr key={b.board_code || b.rank_no}>
                <td style={{
                  color: b.rank_no <= 3 ? 'var(--color-red)' : 'var(--text-secondary)',
                  fontWeight: b.rank_no <= 3 ? 700 : 400,
                }}>
                  {b.rank_no}
                </td>
                <td style={{ fontWeight: 600 }}>{b.board_name ?? '-'}</td>
                <td style={{
                  fontVariantNumeric: 'tabular-nums',
                  fontWeight: 600,
                  color: b.change_pct != null
                    ? b.change_pct > 0 ? 'var(--color-red)'
                    : b.change_pct < 0 ? 'var(--color-green)'
                    : 'var(--text-secondary)'
                    : 'var(--text-secondary)',
                }}>
                  {b.change_pct != null ? `${b.change_pct > 0 ? '+' : ''}${b.change_pct.toFixed(2)}%` : '-'}
                </td>
                <td>
                  {b.leading_stock ? (
                    <span>
                      {b.leading_stock}
                      {b.leading_stock_change != null && (
                        <span style={{
                          marginLeft: '4px',
                          fontSize: '11px',
                          color: b.leading_stock_change > 0 ? 'var(--color-red)' : 'var(--color-green)',
                        }}>
                          {b.leading_stock_change > 0 ? '+' : ''}{b.leading_stock_change.toFixed(2)}%
                        </span>
                      )}
                    </span>
                  ) : '-'}
                </td>
                <td style={{ color: 'var(--color-red)', fontVariantNumeric: 'tabular-nums' }}>
                  {b.up_count ?? '-'}
                </td>
                <td style={{ color: 'var(--color-green)', fontVariantNumeric: 'tabular-nums' }}>
                  {b.down_count ?? '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
