import type {
  ReviewData,
  EmotionTrendItem,
  MarketInsights,
  HotData,
  DataJob,
  MarketOverviewTrendItem,
  PremarketGuide,
  PlateRotationData,
  QuantzzDailyOverview,
  ReviewPayload,
  ReviewSubmoduleKey,
} from '../types'

const BASE = '/api'

export async function fetchDates(signal?: AbortSignal): Promise<string[]> {
  const res = await fetch(`${BASE}/dates`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch dates: ${res.statusText}`)
  }
  const json = await res.json()
  return json.dates
}

export async function fetchReview(date: string, signal?: AbortSignal): Promise<ReviewData> {
  const res = await fetch(`${BASE}/review?date=${date}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch review: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchReviewSubmodule(
  key: ReviewSubmoduleKey,
  date: string,
  params: Record<string, string | number | undefined> = {},
  signal?: AbortSignal,
): Promise<ReviewPayload> {
  const query = new URLSearchParams({ date })
  Object.entries(params).forEach(([name, value]) => {
    if (value !== undefined) query.set(name, String(value))
  })
  const res = await fetch(`${BASE}/review/${key}?${query.toString()}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch review module ${key}: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchEmotionTrend(date: string, days = 5, signal?: AbortSignal): Promise<EmotionTrendItem[]> {
  const res = await fetch(`${BASE}/emotion/trend?date=${date}&days=${days}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch emotion trend: ${res.statusText}`)
  }
  const json = await res.json()
  return json.trend
}

export async function fetchMarketOverviewTrend(date: string, days = 5, signal?: AbortSignal): Promise<MarketOverviewTrendItem[]> {
  const res = await fetch(`${BASE}/market/overview-trend?date=${date}&days=${days}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch market overview trend: ${res.statusText}`)
  }
  const json = await res.json()
  return json.trend
}

export async function fetchQuantzzDaily(date: string, days = 60, signal?: AbortSignal): Promise<QuantzzDailyOverview> {
  const res = await fetch(`${BASE}/quantzz/daily?date=${date}&days=${days}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch quantzz daily: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchPlateRotation(
  date?: string,
  days = 8,
  topN = 12,
  plateCode?: string,
  signal?: AbortSignal,
): Promise<PlateRotationData> {
  const params = new URLSearchParams({
    days: String(days),
    top_n: String(topN),
  })
  if (date) params.set('date', date)
  if (plateCode) params.set('plate_code', plateCode)
  const res = await fetch(`${BASE}/plate-rotation?${params.toString()}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch plate rotation: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchPremarketGuide(date?: string, signal?: AbortSignal): Promise<PremarketGuide> {
  const query = date ? `?date=${date}` : ''
  const res = await fetch(`${BASE}/premarket${query}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch premarket guide: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchInsights(date: string, signal?: AbortSignal): Promise<MarketInsights> {
  const res = await fetch(`${BASE}/insights?date=${date}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch insights: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchHot(date: string, signal?: AbortSignal): Promise<HotData> {
  const res = await fetch(`${BASE}/hot?date=${date}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch hot data: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchHotDates(signal?: AbortSignal): Promise<string[]> {
  const res = await fetch(`${BASE}/hot/dates`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch hot dates: ${res.statusText}`)
  }
  const json = await res.json()
  return json.dates
}

export async function fetchLatestJob(signal?: AbortSignal): Promise<DataJob | null> {
  const res = await fetch(`${BASE}/jobs/latest?job_name=daily_update`, { signal })
  if (res.status === 404) {
    return null
  }
  if (!res.ok) {
    throw new Error(`Failed to fetch latest job: ${res.statusText}`)
  }
  return res.json()
}
