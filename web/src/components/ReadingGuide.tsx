import type { TabKey } from './TabBar'

interface Props {
  active: TabKey
}

const guide: Record<TabKey, { title: string; steps: string[] }> = {
  'limit-up-review': {
    title: '先判断短线接力强不强',
    steps: ['看涨停总数和最高板', '看主线板块有没有扩散', '看连板梯队是否断层', '最后翻涨停原因明细'],
  },
  'emotion-review': {
    title: '再看资金注意力在哪里',
    steps: ['先看人气核心是不是涨停', '再看热门板块涨跌', '对照核心板块真实走势', '找非涨停但高人气的票'],
  },
  'profit-effect': {
    title: '然后判断今天好不好赚钱',
    steps: ['看红盘率和涨跌停比', '看炸板和跌停压力', '看封板质量', '最后看明天计划'],
  },
  'data-overview': {
    title: '最后用原始数据复核',
    steps: ['指数和统计先过一遍', '看市场环境', '看情绪趋势', '需要细查再翻全量涨停表'],
  },
}

export function ReadingGuide({ active }: Props) {
  const item = guide[active]
  return (
    <section className="reading-guide-wrap">
      <div className="reading-route">
        <span>读盘顺序</span>
        <strong>涨停复盘</strong>
        <span>看接力</span>
        <strong>情绪复盘</strong>
        <span>看注意力</span>
        <strong>赚钱效应</strong>
        <span>看风险收益</span>
        <strong>数据总览</strong>
        <span>最后复核</span>
      </div>
      <div className="reading-guide">
        <div className="reading-guide-title">{item.title}</div>
        <div className="reading-guide-steps">
          {item.steps.map((step, index) => (
            <span key={step}>
              <strong>{index + 1}</strong>
              {step}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}
