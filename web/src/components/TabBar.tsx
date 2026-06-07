export type TabKey = 'report' | 'plate' | 'tier' | 'emotion' | 'insight' | 'hot' | 'overview'

interface Props {
  active: TabKey
  onChange: (tab: TabKey) => void
}

const tabs: { key: TabKey; label: string }[] = [
  { key: 'report', label: '复盘报告' },
  { key: 'plate', label: '涨停原因' },
  { key: 'tier', label: '连板梯队' },
  { key: 'emotion', label: '情绪分析' },
  { key: 'insight', label: '市场洞察' },
  { key: 'hot', label: '热门' },
  { key: 'overview', label: '数据总览' },
]

export function TabBar({ active, onChange }: Props) {
  return (
    <div className="tab-bar">
      {tabs.map(tab => (
        <button
          key={tab.key}
          className={`tab-btn ${active === tab.key ? 'active' : ''}`}
          onClick={() => onChange(tab.key)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
