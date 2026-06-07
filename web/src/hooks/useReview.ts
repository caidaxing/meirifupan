import { useState, useEffect } from 'react'
import { fetchReview, fetchEmotionTrend, fetchDates, fetchInsights, fetchHot, fetchHotDates } from '../api/client'
import type { ReviewData, EmotionTrendItem, MarketInsights, HotData } from '../types'

export function useReview(date: string) {
  const [data, setData] = useState<ReviewData | null>(null)
  const [trend, setTrend] = useState<EmotionTrendItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!date) {
      setData(null)
      setTrend([])
      setLoading(false)
      setError(null)
      return
    }
    const ctrl = new AbortController()
    setLoading(true)
    Promise.all([fetchReview(date, ctrl.signal), fetchEmotionTrend(date, 5, ctrl.signal)])
      .then(([review, trend]) => {
        setData(review)
        setTrend(trend)
        setError(null)
      })
      .catch(e => {
        if (e.name !== 'AbortError') setError(e.message)
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [date])

  return { data, trend, loading, error }
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
