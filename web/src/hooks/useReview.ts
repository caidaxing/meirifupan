import { useState, useEffect } from 'react'
import {
  fetchReview,
  fetchEmotionTrend,
  fetchEmotionModules,
  fetchEmotionRealtime,
  fetchDates,
  fetchMarketOverviewTrend,
  fetchPremarketGuide,
  fetchPlateRotation,
  fetchQuantzzDaily,
  fetchInsights,
  fetchHot,
  fetchHotDates,
  fetchLatestJob,
  fetchReviewSubmodule,
  fetchAnnouncements,
  fetchAnnouncementDetail,
  fetchNews,
  fetchNewsDates,
  fetchResearchReportDates,
  fetchResearchReports,
  fetchResearchReportDetail,
} from '../api/client'
import type {
  ReviewData,
  EmotionTrendItem,
  EmotionModulesData,
  EmotionRealtimeData,
  MarketInsights,
  HotData,
  DataJob,
  MarketOverviewTrendItem,
  PremarketGuide,
  PlateRotationData,
  QuantzzDailyOverview,
  ReviewPayload,
  ReviewSubmoduleKey,
  AnnouncementDetail,
  AnnouncementListData,
  NewsListData,
  ResearchReportListData,
  ResearchReportDetail,
} from '../types'

export function useReview(date: string) {
  const [data, setData] = useState<ReviewData | null>(null)
  const [trend, setTrend] = useState<EmotionTrendItem[]>([])
  const [marketTrend, setMarketTrend] = useState<MarketOverviewTrendItem[]>([])
  const [plateRotation, setPlateRotation] = useState<PlateRotationData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!date) {
      setData(null)
      setTrend([])
      setMarketTrend([])
      setPlateRotation(null)
      setLoading(false)
      setError(null)
      return
    }
    const ctrl = new AbortController()
    setLoading(true)

    const safe = <T>(p: Promise<T>, fallback: T): Promise<T> =>
      p.catch(e => { if (e.name !== 'AbortError') console.error(e); return fallback })

    Promise.all([
      fetchReview(date, ctrl.signal),  // critical — no fallback
      safe(fetchEmotionTrend(date, 60, ctrl.signal), []),
      safe(fetchMarketOverviewTrend(date, 60, ctrl.signal), []),
      safe(fetchPlateRotation(date, 8, 12, undefined, ctrl.signal), null),
    ])
      .then(([review, trend, marketTrend, plateRotation]) => {
        setData(review)
        setTrend(trend)
        setMarketTrend(marketTrend)
        setPlateRotation(plateRotation)
        setError(null)
      })
      .catch(e => {
        if (e.name !== 'AbortError') setError(e.message)
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [date])

  return { data, trend, marketTrend, plateRotation, loading, error }
}

export function useReviewSubmodule(
  key: ReviewSubmoduleKey,
  date: string,
  params: Record<string, string | number | undefined> = {},
) {
  const [data, setData] = useState<ReviewPayload | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!date) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }
    const ctrl = new AbortController()
    setLoading(true)
    fetchReviewSubmodule(key, date, params, ctrl.signal)
      .then(d => { setData(d); setError(null) })
      .catch(e => {
        if (e.name !== 'AbortError') setError(e.message)
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [key, date, JSON.stringify(params)])

  return { data, loading, error }
}

export function useEmotionModules(date: string) {
  const [data, setData] = useState<EmotionModulesData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!date) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }
    const ctrl = new AbortController()
    setLoading(true)
    fetchEmotionModules(date, 60, ctrl.signal)
      .then(d => { setData(d); setError(null) })
      .catch(e => {
        if (e.name !== 'AbortError') setError(e.message)
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [date])

  return { data, loading, error }
}

export function useEmotionRealtime(enabled: boolean, date?: string, refreshMs = 45000) {
  const [data, setData] = useState<EmotionRealtimeData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }
    let disposed = false
    let timer: number | undefined
    let activeCtrl: AbortController | null = null

    const load = (showLoading: boolean) => {
      activeCtrl?.abort()
      activeCtrl = new AbortController()
      if (showLoading) setLoading(true)
      fetchEmotionRealtime(date, activeCtrl.signal)
        .then(d => {
          if (disposed) return
          setData(d)
          setError(null)
          const nextMs = Math.max((d.refresh_seconds || refreshMs / 1000) * 1000, 15000)
          window.clearInterval(timer)
          timer = window.setInterval(() => load(false), nextMs)
        })
        .catch(e => {
          if (!disposed && e.name !== 'AbortError') setError(e.message)
        })
        .finally(() => {
          if (!disposed) setLoading(false)
        })
    }

    load(true)
    // Interval is scheduled inside load()'s .then() handler after first response
    return () => {
      disposed = true
      activeCtrl?.abort()
      window.clearInterval(timer)
    }
  }, [enabled, date, refreshMs])

  return { data, loading, error }
}

export function useDates() {
  const [dates, setDates] = useState<string[]>([])
  useEffect(() => {
    const ctrl = new AbortController()
    fetchDates(ctrl.signal).then(setDates).catch(e => {
      if (e.name !== 'AbortError') console.error(e)
    })
    return () => ctrl.abort()
  }, [])
  return dates
}

export function useInsights(date: string) {
  const [data, setData] = useState<MarketInsights | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!date) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }
    const ctrl = new AbortController()
    setLoading(true)
    fetchInsights(date, ctrl.signal)
      .then(d => { setData(d); setError(null) })
      .catch(e => {
        if (e.name !== 'AbortError') setError(e.message)
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [date])

  return { data, loading, error }
}

export function useHot(date: string) {
  const [data, setData] = useState<HotData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!date) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }
    const ctrl = new AbortController()
    setLoading(true)
    fetchHot(date, ctrl.signal)
      .then(d => { setData(d); setError(null) })
      .catch(e => {
        if (e.name !== 'AbortError') setError(e.message)
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [date])

  return { data, loading, error }
}

export function useHotDates() {
  const [dates, setDates] = useState<string[]>([])
  useEffect(() => {
    const ctrl = new AbortController()
    fetchHotDates(ctrl.signal).then(setDates).catch(e => {
      if (e.name !== 'AbortError') console.error(e)
    })
    return () => ctrl.abort()
  }, [])
  return dates
}

export function useNewsDates() {
  const [dates, setDates] = useState<string[]>([])
  useEffect(() => {
    const ctrl = new AbortController()
    fetchNewsDates(ctrl.signal).then(setDates).catch(e => {
      if (e.name !== 'AbortError') console.error(e)
    })
    return () => ctrl.abort()
  }, [])
  return dates
}

export function useLatestJob() {
  const [job, setJob] = useState<DataJob | null>(null)
  useEffect(() => {
    const ctrl = new AbortController()
    fetchLatestJob(ctrl.signal).then(setJob).catch(e => {
      if (e.name !== 'AbortError') console.error(e)
    })
    return () => ctrl.abort()
  }, [])
  return job
}

export function useQuantzzDaily(date: string) {
  const [data, setData] = useState<QuantzzDailyOverview | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!date) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }
    const ctrl = new AbortController()
    setLoading(true)
    fetchQuantzzDaily(date, 60, ctrl.signal)
      .then(d => { setData(d); setError(null) })
      .catch(e => {
        if (e.name !== 'AbortError') setError(e.message)
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [date])

  return { data, loading, error }
}

export function usePremarketGuide(enabled: boolean) {
  const [data, setData] = useState<PremarketGuide | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      setError(null)
      return
    }
    const ctrl = new AbortController()
    setLoading(true)
    fetchPremarketGuide(undefined, ctrl.signal)
      .then(d => { setData(d); setError(null) })
      .catch(e => {
        if (e.name !== 'AbortError') setError(e.message)
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [enabled])

  return { data, loading, error }
}

export function useAnnouncements(date: string, noticeType?: string, q?: string) {
  const [data, setData] = useState<AnnouncementListData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!date) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }
    const ctrl = new AbortController()
    setLoading(true)
    fetchAnnouncements(date, { noticeType, q }, ctrl.signal)
      .then(d => { setData(d); setError(null) })
      .catch(e => {
        if (e.name !== 'AbortError') setError(e.message)
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [date, noticeType, q])

  return { data, loading, error }
}

export function useAnnouncementDetail(artCode: string | null) {
  const [data, setData] = useState<AnnouncementDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!artCode) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }
    const ctrl = new AbortController()
    setLoading(true)
    fetchAnnouncementDetail(artCode, ctrl.signal)
      .then(d => { setData(d); setError(null) })
      .catch(e => {
        if (e.name !== 'AbortError') setError(e.message)
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [artCode])

  return { data, loading, error }
}

export function useNews(date: string, source?: string, q?: string) {
  const [data, setData] = useState<NewsListData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!date) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }
    const ctrl = new AbortController()
    setLoading(true)
    fetchNews(date, { source, q }, ctrl.signal)
      .then(d => { setData(d); setError(null) })
      .catch(e => {
        if (e.name !== 'AbortError') setError(e.message)
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [date, source, q])

  return { data, loading, error }
}

export function useResearchReportDates() {
  const [dates, setDates] = useState<string[]>([])
  useEffect(() => {
    const ctrl = new AbortController()
    fetchResearchReportDates(ctrl.signal).then(setDates).catch(e => {
      if (e.name !== 'AbortError') console.error(e)
    })
    return () => ctrl.abort()
  }, [])
  return dates
}

export function useResearchReports(
  date: string,
  filters: { q?: string; rating?: string; org?: string } = {},
) {
  const [data, setData] = useState<ResearchReportListData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!date) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }
    const ctrl = new AbortController()
    setLoading(true)
    fetchResearchReports(date, filters, ctrl.signal)
      .then(d => { setData(d); setError(null) })
      .catch(e => {
        if (e.name !== 'AbortError') setError(e.message)
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [date, filters.q, filters.rating, filters.org])

  return { data, loading, error }
}

export function useResearchReportDetail(infoCode: string | null) {
  const [data, setData] = useState<ResearchReportDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!infoCode) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }
    const ctrl = new AbortController()
    setLoading(true)
    fetchResearchReportDetail(infoCode, ctrl.signal)
      .then(d => { setData(d); setError(null) })
      .catch(e => {
        if (e.name !== 'AbortError') setError(e.message)
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [infoCode])

  return { data, loading, error }
}
