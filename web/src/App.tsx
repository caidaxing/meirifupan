import { useState, useEffect, useMemo } from 'react'
import { useReview, useDates, useInsights, useHot, useHotDates, useNewsDates, useLatestJob, usePremarketGuide, useEmotionModules, useEmotionRealtime } from './hooks/useReview'
import { DateSelector } from './components/DateSelector'
import { Sidebar, type ModuleKey } from './components/Sidebar'
import { AnnouncementView } from './components/AnnouncementView'
import { DataOverview } from './components/DataOverview'
import { EmotionReview } from './components/EmotionReview'
import { LimitUpReview } from './components/LimitUpReview'
import { LoginView } from './components/LoginView'
import { PremarketGuideView } from './components/PremarketGuideView'
import { ProfitEffectReview } from './components/ProfitEffectReview'
import { ReviewHome } from './components/ReviewHome'
import { fetchCurrentUser, getAuthToken, logout } from './api/client'
import type { AuthUser } from './types'
import './styles/globals.css'

type ReviewSubTab = 'overview' | 'limit-up' | 'profit-effect' | 'premarket'

function PlaceholderView({ title, desc }: { title: string; desc: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '60vh', color: 'var(--text-secondary)' }}>
      <div style={{ fontSize: '48px', marginBottom: '16px' }}>🚧</div>
      <h2 style={{ fontSize: '20px', marginBottom: '8px', color: 'var(--text-primary)' }}>{title}</h2>
      <p>{desc}</p>
    </div>
  )
}

function MainApp({
  user,
  onLoginClick,
  onLogout,
}: {
  user: AuthUser | null
  onLoginClick: () => void
  onLogout: () => void
}) {
  const reviewDates = useDates()
  const hotDates = useHotDates()
  const newsDates = useNewsDates()
  const latestJob = useLatestJob()
  const [date, setDate] = useState('')
  const [newsDate, setNewsDate] = useState('')
  const [module, setModule] = useState<ModuleKey>('review')
  const [reviewSubTab, setReviewSubTab] = useState<ReviewSubTab>('overview')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const activeDates = reviewDates
  const activeNewsDates = newsDates.length ? newsDates : reviewDates

  const effectiveDate = useMemo(() => {
    if (activeDates.length === 0) return ''
    if (activeDates.includes(date)) return date
    return activeDates[0]
  }, [activeDates, date])

  const effectiveNewsDate = useMemo(() => {
    if (activeNewsDates.length === 0) return effectiveDate
    if (activeNewsDates.includes(newsDate)) return newsDate
    return activeNewsDates[0]
  }, [activeNewsDates, newsDate, effectiveDate])

  useEffect(() => {
    if (effectiveDate && effectiveDate !== date) {
      setDate(effectiveDate)
    }
  }, [effectiveDate, date])

  useEffect(() => {
    if (effectiveNewsDate && effectiveNewsDate !== newsDate) {
      setNewsDate(effectiveNewsDate)
    }
  }, [effectiveNewsDate, newsDate])

  const { data, trend, marketTrend, plateRotation, loading, error } = useReview(effectiveDate)
  const { data: insights, loading: insightLoading } = useInsights(effectiveDate)
  const hotDate = hotDates.includes(effectiveDate) ? effectiveDate : hotDates[0] ?? ''
  const { data: hotData, loading: hotLoading, error: hotError } = useHot(module === 'emotion' ? hotDate : '')
  const {
    data: emotionModules,
    loading: emotionModulesLoading,
    error: emotionModulesError,
  } = useEmotionModules(module === 'emotion' ? effectiveDate : '')
  const {
    data: emotionRealtime,
    loading: emotionRealtimeLoading,
    error: emotionRealtimeError,
  } = useEmotionRealtime(module === 'emotion')
  const {
    data: premarketGuide,
    loading: premarketLoading,
    error: premarketError,
  } = usePremarketGuide(module === 'review' && reviewSubTab === 'premarket')

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

  if (loading) return <div className="loading">加载中...</div>
  if (error) return <div className="error">{error}</div>

  return (
    <div className="app-layout">
      <Sidebar
        active={module}
        onChange={setModule}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        user={user}
        onLoginClick={onLoginClick}
        onLogout={onLogout}
      />
      <main className="main-content">
        {module === 'data-overview' && (
          <div className="main-header">
            <DateSelector dates={activeDates} value={date} onChange={setDate} />
          </div>
        )}

        {/* 复盘模块 */}
        {module === 'review' && (
          <div className="module-content">
            <div className="review-sub-tabs">
              {([
                ['overview', '总览'],
                ['limit-up', '涨停复盘'],
                ['profit-effect', '赚钱效应'],
                ['premarket', '盘前指引'],
              ] as [ReviewSubTab, string][]).map(([key, label]) => (
                <button
                  key={key}
                  className={`sub-tab ${reviewSubTab === key ? 'active' : ''}`}
                  onClick={() => setReviewSubTab(key)}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="module-controls">
              <div className="module-control-summary">
                <span className="section-kicker">复盘日期</span>
                <strong>{effectiveDate}</strong>
              </div>
              <DateSelector dates={activeDates} value={date} onChange={setDate} />
            </div>
            <div className="sub-tab-content">
              {reviewSubTab === 'overview' && data && (
                <ReviewHome
                  data={data}
                  emotionTrend={trend}
                  marketTrend={marketTrend}
                  plateRotation={plateRotation}
                  onOpenTab={(tab) => {
                    const map: Record<string, ReviewSubTab> = {
                      'premarket-guide': 'premarket',
                      'quantzz-daily': 'overview',
                      'limit-up-review': 'limit-up',
                      'emotion-review': 'profit-effect',
                      'profit-effect': 'profit-effect',
                      'data-overview': 'overview',
                    }
                    if (map[tab]) setReviewSubTab(map[tab])
                  }}
                />
              )}
              {reviewSubTab === 'limit-up' && data && <LimitUpReview data={data} />}
              {reviewSubTab === 'profit-effect' && data && (
                <ProfitEffectReview data={data} insights={insights} loading={insightLoading} />
              )}
              {reviewSubTab === 'premarket' && (
                <PremarketGuideView data={premarketGuide} loading={premarketLoading} error={premarketError} />
              )}
            </div>
          </div>
        )}

        {/* 盘中情绪模块 */}
        {module === 'emotion' && data && (
          <div className="module-content">
            <EmotionReview
              data={data}
              trend={trend}
              hotData={hotData}
              hotLoading={hotLoading}
              hotError={hotError}
              modules={emotionModules}
              modulesLoading={emotionModulesLoading}
              modulesError={emotionModulesError}
              realtime={emotionRealtime}
              realtimeLoading={emotionRealtimeLoading}
              realtimeError={emotionRealtimeError}
              controls={
                <div className="module-controls">
                  <div className="module-control-summary">
                    <span className="section-kicker">情绪日期</span>
                    <strong>{effectiveDate}</strong>
                  </div>
                  <DateSelector dates={activeDates} value={date} onChange={setDate} />
                </div>
              }
            />
          </div>
        )}

        {/* 新闻资讯 */}
        {module === 'news' && (
          <div className="module-content">
            <AnnouncementView date={effectiveNewsDate} dates={activeNewsDates} onDateChange={setNewsDate} />
          </div>
        )}

        {/* 社媒舆情 - 占位 */}
        {module === 'social' && (
          <div className="module-content">
            <PlaceholderView title="社媒舆情" desc="热度排行、论坛动态、舆情分析、KOL追踪 — 即将上线" />
          </div>
        )}

        {/* 数据总览 */}
        {module === 'data-overview' && data && (
          <div className="module-content">
            <DataOverview data={data} trend={trend} marketTrend={marketTrend} latestJob={latestJob} />
          </div>
        )}
      </main>
    </div>
  )
}

export default function App() {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [checking, setChecking] = useState(() => Boolean(getAuthToken()))
  const [showLogin, setShowLogin] = useState(false)

  useEffect(() => {
    if (!getAuthToken()) {
      setChecking(false)
      return
    }
    const ctrl = new AbortController()
    fetchCurrentUser(ctrl.signal)
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setChecking(false))
    return () => ctrl.abort()
  }, [])

  const handleLogout = async () => {
    await logout().catch(() => undefined)
    setUser(null)
  }

  return (
    <>
      {checking ? <div className="auth-checking">检查登录状态...</div> : null}
      <MainApp user={user} onLoginClick={() => setShowLogin(true)} onLogout={handleLogout} />
      {showLogin ? (
        <LoginView
          onLogin={(nextUser) => {
            setUser(nextUser)
            setShowLogin(false)
          }}
          onCancel={() => setShowLogin(false)}
        />
      ) : null}
    </>
  )
}
