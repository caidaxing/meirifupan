import { useState, useEffect, useMemo } from 'react'
import { useReview, useDates, useInsights, useHot, useHotDates } from './hooks/useReview'
import { DateSelector } from './components/DateSelector'
import { TabBar, type TabKey } from './components/TabBar'
import { PlateGroupView } from './components/PlateGroupView'
import { BoardTiers } from './components/BoardTiers'
import { EmotionDetail } from './components/EmotionDetail'
import { InsightView } from './components/InsightView'
import { HotView } from './components/HotView'
import { Overview } from './components/Overview'
import { ReviewReport } from './components/ReviewReport'
import './styles/globals.css'

export default function App() {
  const reviewDates = useDates()
  const hotDates = useHotDates()
  const [date, setDate] = useState('')
  const [tab, setTab] = useState<TabKey>('report')

  const isHotTab = tab === 'hot'
  const activeDates = isHotTab ? hotDates : reviewDates

  // Compute effective date: if current date isn't in activeDates, pick the first available
  const effectiveDate = useMemo(() => {
    if (activeDates.length === 0) return ''
    if (activeDates.includes(date)) return date
    return activeDates[0]
  }, [activeDates, date])

  // Sync date state when effectiveDate changes
  useEffect(() => {
    if (effectiveDate && effectiveDate !== date) {
      setDate(effectiveDate)
    }
  }, [effectiveDate, date])

  const { data, trend, loading, error } = useReview(isHotTab ? '' : effectiveDate)
  const { data: insights, loading: insightLoading } = useInsights(isHotTab ? '' : effectiveDate)
  const { data: hotData, loading: hotLoading, error: hotError } = useHot(isHotTab ? effectiveDate : '')

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') {
        const idx = activeDates.indexOf(date)
        if (idx < activeDates.length - 1) setDate(activeDates[idx + 1])
      } else if (e.key === 'ArrowRight') {
        const idx = activeDates.indexOf(date)
        if (idx > 0) setDate(activeDates[idx - 1])
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [date, activeDates])

  if (!isHotTab && loading) return <div className="loading">加载中...</div>
  if (!isHotTab && error) return <div className="error">{error}</div>

  return (
    <div className="container">
      <div className="header">
        <h1>发家致富 · 每日复盘</h1>
        <DateSelector dates={activeDates} value={date} onChange={setDate} />
      </div>
      <TabBar active={tab} onChange={setTab} />
      <div className="tab-content">
        {tab === 'report' && data && <ReviewReport review={data.saved_review} />}
        {tab === 'plate' && data && <PlateGroupView stocks={data.all_stocks} />}
        {tab === 'tier' && data && <BoardTiers tiers={data.board_tiers} fullView />}
        {tab === 'emotion' && data && <EmotionDetail emotion={data.emotion} trend={trend} />}
        {tab === 'insight' && (insightLoading ? <div className="loading">加载洞察数据...</div> : insights ? <InsightView data={insights} /> : <div className="error">无数据</div>)}
        {tab === 'hot' && (hotLoading ? <div className="loading">加载热门数据...</div> : hotData ? <HotView data={hotData} /> : <div className="error">{hotError ?? '无数据'}</div>)}
        {tab === 'overview' && data && <Overview data={data} trend={trend} />}
      </div>
    </div>
  )
}
