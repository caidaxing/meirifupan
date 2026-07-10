import { useEffect, useState } from 'react'
import { DateSelector } from './DateSelector'
import { useResearchReportDetail, useResearchReports } from '../hooks/useReview'
import type { ResearchReportItem } from '../types'

interface Props {
  date: string
  dates: string[]
  onDateChange: (date: string) => void
}

export function ResearchReportView({ date, dates, onDateChange }: Props) {
  const [query, setQuery] = useState('')
  const [rating, setRating] = useState('')
  const [org, setOrg] = useState('')
  const [selectedCode, setSelectedCode] = useState<string | null>(null)
  const { data, loading, error } = useResearchReports(date, { q: query, rating, org })
  const detail = useResearchReportDetail(selectedCode)

  useEffect(() => {
    setSelectedCode(null)
  }, [date, query, rating, org])

  return (
    <section className="research-report-page">
      <div className="announcement-controls">
        <div className="announcement-summary">
          <span className="section-kicker">个股研报</span>
          <strong>{data?.summary.total ?? 0}</strong>
          <span>篇</span>
        </div>
        <DateSelector dates={dates} value={date} onChange={onDateChange} />
        <input
          className="announcement-search"
          value={query}
          onChange={event => setQuery(event.target.value)}
          placeholder="搜代码、名称、标题、行业"
        />
        <select className="announcement-select" value={rating} onChange={event => setRating(event.target.value)}>
          <option value="">全部评级</option>
          {(data?.summary.ratings ?? []).map(item => (
            <option key={item.rating_name} value={item.rating_name}>{item.rating_name}（{item.count}）</option>
          ))}
        </select>
        <select className="announcement-select" value={org} onChange={event => setOrg(event.target.value)}>
          <option value="">全部机构</option>
          {(data?.summary.organizations ?? []).map(item => (
            <option key={item.org_name} value={item.org_name}>{item.org_name}（{item.count}）</option>
          ))}
        </select>
      </div>

      {error && <div className="error">研报列表加载失败：{error}</div>}
      <div className="research-report-layout">
        <div className="research-report-list">
          {loading && <div className="loading-inline">研报加载中...</div>}
          {!loading && (data?.items.length ?? 0) === 0 && <div className="empty-state">当前日期没有匹配的个股研报。</div>}
          {(data?.items ?? []).map(item => (
            <ResearchReportCard
              key={item.info_code}
              item={item}
              active={item.info_code === selectedCode}
              onClick={() => setSelectedCode(item.info_code)}
            />
          ))}
        </div>
        <aside className="research-report-detail">
          {!selectedCode && <div className="empty-state">选择一篇研报查看摘要和 PDF。</div>}
          {selectedCode && detail.loading && <div className="loading-inline">研报详情加载中...</div>}
          {selectedCode && detail.error && <div className="error">研报详情加载失败：{detail.error}</div>}
          {detail.data && !detail.loading && <ResearchReportDetail data={detail.data} />}
        </aside>
      </div>
    </section>
  )
}

function ResearchReportCard({ item, active, onClick }: { item: ResearchReportItem; active: boolean; onClick: () => void }) {
  return (
    <button className={`announcement-card ${active ? 'active' : ''}`} onClick={onClick}>
      <div className="announcement-card-top">
        <span className="announcement-code">{item.stock_code || '--'}</span>
        <span>{item.stock_name || '未知股票'}</span>
        {item.rating_name && <span className="announcement-type">{item.rating_name}</span>}
        <span className={`research-pdf-status ${item.pdf_status}`}>{item.pdf_status === 'downloaded' ? 'PDF已下载' : item.pdf_status === 'unavailable' ? '无PDF附件' : item.pdf_status === 'failed' ? 'PDF失败' : 'PDF待取'}</span>
      </div>
      <div className="announcement-title">{item.title}</div>
      <div className="announcement-card-bottom">
        <span>{item.org_short_name || item.org_name || '未知机构'}</span>
        <span>{item.industry_name || '未分类'}</span>
        <span>{item.publish_date}</span>
      </div>
    </button>
  )
}

function ResearchReportDetail({ data }: { data: NonNullable<ReturnType<typeof useResearchReportDetail>['data']> }) {
  const targetPrice = data.target_price_low || data.target_price_high
    ? `${data.target_price_low ?? '-'} - ${data.target_price_high ?? '-'}`
    : '未提供'
  return (
    <>
      <div className="announcement-detail-head">
        <span className="announcement-type">{data.rating_name || '未评级'}</span>
        <span className={`research-pdf-status ${data.pdf_status}`}>{data.pdf_status === 'downloaded' ? '本地 PDF 已就绪' : data.pdf_status === 'unavailable' ? '源站无 PDF 附件' : data.pdf_status}</span>
      </div>
      <h2>{data.title}</h2>
      <div className="announcement-meta">
        <span>{data.stock_name} {data.stock_code}</span>
        <span>{data.org_short_name || data.org_name || '未知机构'}</span>
        <span>{data.publish_date}</span>
      </div>
      <div className="research-report-metrics">
        <div><span>评级变化</span><strong>{data.rating_change_name || '-'}</strong></div>
        <div><span>目标价</span><strong>{targetPrice}</strong></div>
        <div><span>行业</span><strong>{data.industry_name || '-'}</strong></div>
        <div><span>页数</span><strong>{data.attach_pages ?? '-'}</strong></div>
      </div>
      <div className="research-report-authors">
        <span className="research-report-label">分析师</span>
        {data.authors.length ? data.authors.map(author => <span key={author.author_id} className="announcement-type">{author.author_name}</span>) : <span className="report-muted">未提供</span>}
      </div>
      <div className="announcement-actions">
        {data.local_pdf_url ? <a href={data.local_pdf_url} target="_blank" rel="noreferrer">查看本地 PDF</a> : <span className="report-muted">PDF 尚未下载完成</span>}
        {data.source_url && <a href={data.source_url} target="_blank" rel="noreferrer">来源页面</a>}
      </div>
      <div className="research-report-section">
        <h3>研报摘要</h3>
        <pre className="announcement-content">{data.summary_text || '暂未取到研报摘要。'}</pre>
      </div>
      <div className="research-report-section">
        <h3>盈利预测</h3>
        {data.forecasts.length ? (
          <div className="review-table-wrap">
            <table className="review-mini-table">
              <thead><tr><th>年度</th><th>EPS</th><th>PE</th></tr></thead>
              <tbody>{data.forecasts.map(item => <tr key={item.forecast_year}><td>{item.forecast_year}</td><td>{item.eps ?? '-'}</td><td>{item.pe ?? '-'}</td></tr>)}</tbody>
            </table>
          </div>
        ) : <div className="report-muted">暂无盈利预测</div>}
      </div>
    </>
  )
}
