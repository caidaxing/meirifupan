import { useEffect, useMemo, useState } from 'react'
import { DateSelector } from './DateSelector'
import { useAnnouncementDetail, useAnnouncements, useNews, useResearchReportDates } from '../hooks/useReview'
import { ResearchReportView } from './ResearchReportView'
import type { AnnouncementItem, NewsItem } from '../types'

type NewsTab = 'announcements' | 'flash' | 'policy' | 'overnight' | 'research'
type QuickFilterKey = 'all' | 'important' | 'performance' | 'research' | 'holding' | 'buyback' | 'incentive' | 'abnormal' | 'restructure'

interface Props {
  date: string
  dates: string[]
  onDateChange: (date: string) => void
}

const tabs: { key: NewsTab; label: string; desc: string }[] = [
  { key: 'announcements', label: '公告速递', desc: '已接入列表和原文' },
  { key: 'flash', label: '7x24 快讯', desc: '财联社、东财、新浪' },
  { key: 'policy', label: '政策日历', desc: '重要会议和政策发布' },
  { key: 'overnight', label: '海外隔夜', desc: '美股核心股和外盘事件' },
  { key: 'research', label: '个股研报', desc: '基础信息和本地PDF' },
]

const quickFilters: { key: QuickFilterKey; label: string; keywords: string[] }[] = [
  { key: 'all', label: '全部', keywords: [] },
  { key: 'important', label: '重点', keywords: ['业绩', '调研', '投资者关系', '增持', '减持', '回购', '股权激励', '异常波动', '重组', '并购', '收购', '资产出售', '重大合同', '诉讼', '处罚', '风险提示'] },
  { key: 'performance', label: '业绩', keywords: ['业绩预告', '业绩快报', '定期报告', '年度报告', '半年度报告', '季度报告', '盈利', '亏损', '净利润'] },
  { key: 'research', label: '调研', keywords: ['调研', '投资者关系', '机构调研'] },
  { key: 'holding', label: '增减持', keywords: ['增持', '减持', '持股变动', '权益变动'] },
  { key: 'buyback', label: '回购', keywords: ['回购'] },
  { key: 'incentive', label: '股权激励', keywords: ['股权激励', '员工持股'] },
  { key: 'abnormal', label: '异常波动', keywords: ['异常波动', '风险提示', '监管', '关注函', '问询函', '处罚'] },
  { key: 'restructure', label: '重组并购', keywords: ['重组', '并购', '收购', '资产出售', '股权转让', '重大资产'] },
]

const placeholders: Record<Exclude<NewsTab, 'announcements' | 'research'>, {
  title: string
  sources: string[]
  storedIn: string
  firstFields: string[]
  nextStep: string
}> = {
  flash: {
    title: '7x24 快讯',
    sources: ['财联社电报', '东财全球快讯', '新浪财经', 'CCTV 新闻联播'],
    storedIn: 'premarket_news',
    firstFields: ['source', 'published_at', 'title', 'content', 'url', 'raw_payload'],
    nextStep: '先展示盘前采集到的新闻，再补实时滚动刷新。',
  },
  policy: {
    title: '政策日历',
    sources: ['交易所公告', '证监会发布', '国务院/部委公开信息'],
    storedIn: '待新增 policy_events',
    firstFields: ['event_date', 'source', 'title', 'content', 'url', 'importance'],
    nextStep: '先按日期沉淀事件，再关联到题材和行业。',
  },
  overnight: {
    title: '海外隔夜',
    sources: ['东财美股核心股', '腾讯美股行情备用源', '全球快讯'],
    storedIn: 'us_stock_quotes + premarket_news',
    firstFields: ['symbol', 'stock_name', 'sector', 'latest_price', 'change_pct', 'raw_payload'],
    nextStep: '先展示大涨大跌美股，再映射到 A 股题材。',
  },
}

export function AnnouncementView({ date, dates, onDateChange }: Props) {
  const [activeTab, setActiveTab] = useState<NewsTab>('announcements')
  const [selectedType, setSelectedType] = useState('')
  const [quickFilter, setQuickFilter] = useState<QuickFilterKey>('all')
  const [keyword, setKeyword] = useState('')
  const [newsKeyword, setNewsKeyword] = useState('')
  const [selectedNewsSource, setSelectedNewsSource] = useState('')
  const [selectedArtCode, setSelectedArtCode] = useState<string | null>(null)
  const [researchDate, setResearchDate] = useState('')
  const researchDates = useResearchReportDates()
  const { data, loading, error } = useAnnouncements(date)
  const news = useNews(date, selectedNewsSource, newsKeyword)
  const detail = useAnnouncementDetail(selectedArtCode)
  const effectiveResearchDate = researchDates.includes(researchDate) ? researchDate : researchDates[0] ?? ''
  const totalCount = data?.summary.total ?? 0
  const returnedCount = data?.summary.returned ?? data?.items.length ?? 0
  const isLimited = totalCount > returnedCount

  const items = useMemo(() => {
    const q = keyword.trim().toLowerCase()
    const activeQuickFilter = quickFilters.find(filter => filter.key === quickFilter)
    return (data?.items ?? []).filter(item => {
      if (selectedType && item.notice_type !== selectedType) return false
      if (activeQuickFilter && activeQuickFilter.key !== 'all' && !matchesQuickFilter(item, activeQuickFilter.key)) {
        return false
      }
      if (!q) return true
      return [item.stock_code, item.stock_name, item.notice_type, item.title]
        .join(' ')
        .toLowerCase()
        .includes(q)
    })
  }, [data, selectedType, quickFilter, keyword])

  useEffect(() => {
    if (selectedArtCode && !items.some(item => item.art_code === selectedArtCode)) {
      setSelectedArtCode(null)
    }
  }, [items, selectedArtCode])

  return (
    <section className="announcement-page">
      <div className="news-tabs">
        {tabs.map(tab => (
          <button
            key={tab.key}
            className={`news-tab ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            <strong>{tab.label}</strong>
            <span>{tab.desc}</span>
          </button>
        ))}
      </div>

      {activeTab === 'announcements' && (
        <div className="announcement-controls">
          <div className="announcement-summary">
            <span className="section-kicker">公告速递</span>
            <strong>{isLimited ? `${returnedCount}/${totalCount}` : totalCount}</strong>
            <span>{isLimited ? '已展示/总数' : '条公告'}</span>
          </div>
          <DateSelector dates={dates} value={date} onChange={onDateChange} />
          <input
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            placeholder="搜代码、名称、标题"
            className="announcement-search"
          />
          <select
            value={selectedType}
            onChange={e => setSelectedType(e.target.value)}
            className="announcement-select"
          >
            <option value="">全部类型</option>
            {(data?.summary.types ?? []).map(type => (
              <option key={type.notice_type} value={type.notice_type}>
                {type.notice_type}（{type.count}）
              </option>
            ))}
          </select>
          <div className="announcement-quick-filters">
            {quickFilters.map(filter => (
              <button
                key={filter.key}
                className={`announcement-quick-filter ${quickFilter === filter.key ? 'active' : ''}`}
                onClick={() => setQuickFilter(filter.key)}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'flash' && (
        <div className="announcement-controls">
          <div className="announcement-summary">
            <span className="section-kicker">7x24 快讯</span>
            <strong>{news.data?.summary.total ?? 0}</strong>
            <span>条新闻</span>
            {news.data?.summary.date_mode === 'next_available' && (
              <span className="news-date-note">取 {news.data.summary.data_date}</span>
            )}
          </div>
          <DateSelector dates={dates} value={date} onChange={onDateChange} />
          <input
            value={newsKeyword}
            onChange={e => setNewsKeyword(e.target.value)}
            placeholder="搜标题、内容"
            className="announcement-search"
          />
          <select
            value={selectedNewsSource}
            onChange={e => setSelectedNewsSource(e.target.value)}
            className="announcement-select"
          >
            <option value="">全部来源</option>
            {(news.data?.summary.sources ?? []).map(source => (
              <option key={source.source} value={source.source}>
                {sourceLabel(source.source)}（{source.count}）
              </option>
            ))}
          </select>
        </div>
      )}

      {activeTab !== 'announcements' && activeTab !== 'flash' && activeTab !== 'research' && (
        <NewsPlaceholder config={placeholders[activeTab]} />
      )}

      {activeTab === 'research' && (
        <ResearchReportView date={effectiveResearchDate} dates={researchDates} onDateChange={setResearchDate} />
      )}

      {activeTab === 'flash' && (
        <NewsFeed data={news.data?.items ?? []} loading={news.loading} error={news.error} />
      )}

      {activeTab === 'announcements' && (
        <>
      {error && <div className="error">公告列表加载失败：{error}</div>}

      <div className="announcement-layout">
        <div className="announcement-list">
          {loading && <div className="loading-inline">公告加载中...</div>}
          {!loading && items.length === 0 && (
            <div className="empty-state">当前日期没有匹配的公告。</div>
          )}
          {items.map(item => (
            <AnnouncementCard
              key={`${item.notice_date}-${item.title}`}
              item={item}
              active={item.art_code === selectedArtCode}
              onClick={() => item.art_code && setSelectedArtCode(item.art_code)}
            />
          ))}
        </div>

        <aside className="announcement-detail">
          {!selectedArtCode && <div className="empty-state">选择一条公告后查看原文。</div>}
          {selectedArtCode && detail.loading && <div className="loading-inline">原文加载中...</div>}
          {selectedArtCode && detail.error && (
            <div className="error">原文加载失败：{detail.error}</div>
          )}
          {detail.data && !detail.loading && (
            <>
              <div className="announcement-detail-head">
                <span className="announcement-type">{detail.data.notice_type}</span>
                <span className="announcement-cache">{detail.data.cache_status === 'cached' ? '已读缓存' : '已新取回'}</span>
              </div>
              <h2>{detail.data.notice_title || detail.data.title}</h2>
              <div className="announcement-meta">
                <span>{detail.data.stock_name} {detail.data.stock_code}</span>
                <span>{detail.data.published_at || detail.data.notice_date}</span>
                <span>{detail.data.content_chars} 字</span>
              </div>
              <div className="announcement-actions">
                {detail.data.source_url && (
                  <a href={detail.data.source_url} target="_blank" rel="noreferrer">原网页</a>
                )}
                {detail.data.pdf_url && (
                  <a href={detail.data.pdf_url} target="_blank" rel="noreferrer">PDF 链接</a>
                )}
              </div>
              <pre className="announcement-content">{detail.data.content_text || '暂未取到正文。'}</pre>
            </>
          )}
        </aside>
      </div>
        </>
      )}
    </section>
  )
}

function sourceLabel(source: string) {
  const labels: Record<string, string> = {
    cls: '财联社',
    eastmoney: '东财',
    sina: '新浪',
    cctv: 'CCTV',
  }
  return labels[source] ?? source
}

function matchesQuickFilter(item: AnnouncementItem, key: QuickFilterKey) {
  const filter = quickFilters.find(entry => entry.key === key)
  if (!filter) return true
  const text = [item.notice_type, item.title].join(' ')
  return filter.key === 'all' || filter.keywords.some(keyword => text.includes(keyword))
}

function AnnouncementCard({
  item,
  active,
  onClick,
}: {
  item: AnnouncementItem
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      className={`announcement-card ${active ? 'active' : ''}`}
      onClick={onClick}
      disabled={!item.art_code}
      title={item.art_code ? item.title : '缺少公告编号，暂不能打开原文'}
    >
      <div className="announcement-card-top">
        <span className="announcement-code">{item.stock_code || '--'}</span>
        <span>{item.stock_name || '未知股票'}</span>
        <span className="announcement-type">{item.notice_type}</span>
      </div>
      <div className="announcement-title">{item.title}</div>
      <div className="announcement-card-bottom">
        <span>{item.notice_date}</span>
        <span>{item.art_code ? '可看原文' : '缺少编号'}</span>
      </div>
    </button>
  )
}

function NewsFeed({ data, loading, error }: { data: NewsItem[]; loading: boolean; error: string | null }) {
  if (error) return <div className="error">新闻列表加载失败：{error}</div>
  const grouped = groupNewsBySource(data)

  return (
    <div className="news-feed">
      {loading && <div className="loading-inline">新闻加载中...</div>}
      {!loading && data.length === 0 && (
        <div className="empty-state">当前日期没有匹配的新闻。</div>
      )}
      {grouped.map(group => (
        <section className="news-source-group" key={group.source}>
          <div className="news-source-head">
            <strong>{sourceLabel(group.source)}</strong>
            <span>{group.items.length} 条</span>
          </div>
          {group.items.map((item, index) => (
            <a
              key={`${item.guide_date}-${item.source}-${item.title}-${index}`}
              className="news-feed-item"
              href={item.url || undefined}
              target="_blank"
              rel="noreferrer"
            >
              <div className="news-feed-meta">
                <span>{item.published_at || item.guide_date}</span>
              </div>
              <strong>{item.title}</strong>
              {item.content && <p>{item.content}</p>}
            </a>
          ))}
        </section>
      ))}
    </div>
  )
}

function groupNewsBySource(items: NewsItem[]) {
  const order = ['cls', 'eastmoney', 'sina', 'cctv']
  const groups = new Map<string, NewsItem[]>()
  items.forEach(item => {
    const source = item.source || 'unknown'
    groups.set(source, [...(groups.get(source) ?? []), item])
  })
  return Array.from(groups.entries())
    .sort(([a], [b]) => {
      const ai = order.indexOf(a)
      const bi = order.indexOf(b)
      if (ai === -1 && bi === -1) return a.localeCompare(b)
      if (ai === -1) return 1
      if (bi === -1) return -1
      return ai - bi
    })
    .map(([source, groupItems]) => ({ source, items: groupItems }))
}

function NewsPlaceholder({
  config,
}: {
  config: {
    title: string
    sources: string[]
    storedIn: string
    firstFields: string[]
    nextStep: string
  }
}) {
  return (
    <div className="news-placeholder">
      <div>
        <div className="section-kicker">占位模块</div>
        <h2>{config.title}</h2>
        <p>{config.nextStep}</p>
      </div>
      <div className="news-placeholder-grid">
        <div>
          <strong>数据源</strong>
          <ul>
            {config.sources.map(source => <li key={source}>{source}</li>)}
          </ul>
        </div>
        <div>
          <strong>落库位置</strong>
          <p>{config.storedIn}</p>
        </div>
        <div>
          <strong>第一批字段</strong>
          <p>{config.firstFields.join('、')}</p>
        </div>
      </div>
    </div>
  )
}
