import type { MarketEnvironment as MarketEnvironmentType } from '../types'

interface Props {
  data: MarketEnvironmentType
}

function fmtMoney(value: number | null | undefined) {
  if (value == null) return '-'
  const abs = Math.abs(value)
  if (abs >= 100000000) return `${(value / 100000000).toFixed(1)}亿`
  if (abs >= 10000) return `${(value / 10000).toFixed(0)}万`
  return value.toFixed(0)
}

function fmtPct(value: number | null | undefined) {
  if (value == null) return '-'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

export function MarketEnvironment({ data }: Props) {
  const {
    breadth,
    limit_down_total,
    broken_limit_up_total,
    limit_down,
    broken_limit_up,
    lhb,
    movement_summary,
    market_hot,
  } = data
  const netBuy = lhb.filter(item => (item.net_buy_amount ?? 0) > 0).slice(0, 5)
  const netSell = lhb.filter(item => (item.net_buy_amount ?? 0) < 0).slice(0, 5)
  const limitDownCount = breadth.limit_down_count || limit_down_total

  return (
    <div className="market-env">
      <div className="market-env-strip">
        <Metric label="红盘率" value={`${breadth.up_rate.toFixed(1)}%`} sub={`${breadth.up_count}涨 / ${breadth.down_count}跌`} tone={breadth.up_rate >= 50 ? 'red' : 'green'} />
        <Metric label="全市场成交额" value={fmtMoney(breadth.amount)} sub={`${breadth.total_count}只参与统计`} tone="blue" />
        <Metric label="跌停" value={`${limitDownCount}只`} sub={`前排展示 ${limit_down.length}只`} tone="green" />
        <Metric label="炸板" value={`${broken_limit_up_total}只`} sub="打开涨停后未封住" tone="yellow" />
        <Metric label="涨跌停比" value={`${limitDownCount > 0 ? (breadth.limit_up_count / limitDownCount).toFixed(1) : breadth.limit_up_count}`} sub={`${breadth.limit_up_count}涨停 / ${limitDownCount}跌停`} tone="purple" />
      </div>

      <div className="market-env-grid">
        <SimpleList
          title="跌停前排"
          items={limit_down.slice(0, 6).map(item => ({
            key: item.stock_code,
            main: item.stock_name,
            meta: `${item.stock_code} · ${item.industry ?? '-'}`,
            value: fmtPct(item.change_pct),
            valueClass: 'text-green',
          }))}
        />
        <SimpleList
          title="炸板最多"
          items={broken_limit_up.slice(0, 6).map(item => ({
            key: item.stock_code,
            main: item.stock_name,
            meta: `${item.stock_code} · ${item.first_limit_up_time ?? '-'}`,
            value: `${item.open_count ?? 0}次`,
            valueClass: 'text-yellow',
          }))}
        />
        <SimpleList
          title="龙虎榜净买"
          items={netBuy.map(item => ({
            key: `${item.stock_code}-${item.reason}`,
            main: item.stock_name,
            meta: item.reason ?? item.stock_code,
            value: fmtMoney(item.net_buy_amount),
            valueClass: 'text-red',
          }))}
        />
        <SimpleList
          title="龙虎榜净卖"
          items={netSell.map(item => ({
            key: `${item.stock_code}-${item.reason}`,
            main: item.stock_name,
            meta: item.reason ?? item.stock_code,
            value: fmtMoney(item.net_buy_amount),
            valueClass: 'text-green',
          }))}
        />
      </div>

      <div className="market-env-row">
        <div className="card">
          <div className="card-header">盘中异动</div>
          <div className="card-body">
            <div className="movement-tags">
              {movement_summary.map(item => (
                <span key={item.alert_type} className="tag tag-blue">
                  {item.alert_type} {item.count}
                </span>
              ))}
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-header">板块异动热点</div>
          <div className="card-body">
            <div className="movement-tags">
              {market_hot.slice(0, 12).map(item => (
                <span key={item.item_name} className="tag tag-red">
                  {item.item_name} {item.score ?? '-'}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function Metric({ label, value, sub, tone }: { label: string; value: string; sub: string; tone: 'red' | 'green' | 'blue' | 'yellow' | 'purple' }) {
  return (
    <div className="market-metric">
      <div className="market-metric-label">{label}</div>
      <div className={`market-metric-value text-${tone}`}>{value}</div>
      <div className="market-metric-sub">{sub}</div>
    </div>
  )
}

function SimpleList({ title, items }: { title: string; items: Array<{ key: string; main: string; meta: string; value: string; valueClass: string }> }) {
  return (
    <div className="card market-list">
      <div className="card-header">{title}</div>
      <div className="card-body">
        {items.length === 0 ? (
          <div className="market-empty">无数据</div>
        ) : (
          items.map(item => (
            <div key={item.key} className="market-list-row">
              <div className="market-list-main">
                <span>{item.main}</span>
                <small>{item.meta}</small>
              </div>
              <div className={item.valueClass}>{item.value}</div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
