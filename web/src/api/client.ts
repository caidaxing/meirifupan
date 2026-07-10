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
  AuthSession,
  AuthUser,
} from '../types'

const BASE = '/api'
const AUTH_TOKEN_KEY = 'fajiazhifu_auth_token'

export function getAuthToken() {
  return window.localStorage.getItem(AUTH_TOKEN_KEY)
}

export function setAuthToken(token: string | null) {
  if (token) {
    window.localStorage.setItem(AUTH_TOKEN_KEY, token)
  } else {
    window.localStorage.removeItem(AUTH_TOKEN_KEY)
  }
}

function authHeaders(): HeadersInit {
  const token = getAuthToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function apiFetch(input: string, init: RequestInit = {}) {
  return fetch(input, {
    ...init,
    headers: {
      ...authHeaders(),
      ...(init.headers || {}),
    },
  })
}

export async function login(username: string, password: string): Promise<AuthSession> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    throw new Error('账号或密码不正确')
  }
  const session = await res.json()
  setAuthToken(session.token)
  return session
}

export async function logout(): Promise<void> {
  const res = await apiFetch(`${BASE}/auth/logout`, { method: 'POST' })
  setAuthToken(null)
  if (!res.ok && res.status !== 401) {
    throw new Error(`Failed to logout: ${res.statusText}`)
  }
}

export async function fetchCurrentUser(signal?: AbortSignal): Promise<AuthUser> {
  const res = await apiFetch(`${BASE}/auth/me`, { signal })
  if (!res.ok) {
    setAuthToken(null)
    throw new Error('登录已失效')
  }
  const json = await res.json()
  return json.user
}

export async function fetchDates(signal?: AbortSignal): Promise<string[]> {
  const res = await apiFetch(`${BASE}/dates`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch dates: ${res.statusText}`)
  }
  const json = await res.json()
  return json.dates
}

export async function fetchReview(date: string, signal?: AbortSignal): Promise<ReviewData> {
  const res = await apiFetch(`${BASE}/review?date=${date}`, { signal })
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
  const res = await apiFetch(`${BASE}/review/${key}?${query.toString()}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch review module ${key}: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchEmotionTrend(date: string, days = 5, signal?: AbortSignal): Promise<EmotionTrendItem[]> {
  const res = await apiFetch(`${BASE}/emotion/trend?date=${date}&days=${days}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch emotion trend: ${res.statusText}`)
  }
  const json = await res.json()
  return json.trend
}

export async function fetchEmotionModules(date: string, days = 60, signal?: AbortSignal): Promise<EmotionModulesData> {
  const res = await apiFetch(`${BASE}/emotion/modules?date=${date}&days=${days}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch emotion modules: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchEmotionRealtime(date?: string, signal?: AbortSignal): Promise<EmotionRealtimeData> {
  const query = date ? `?date=${encodeURIComponent(date)}` : ''
  const res = await apiFetch(`${BASE}/emotion/realtime${query}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch realtime emotion: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchMarketOverviewTrend(date: string, days = 5, signal?: AbortSignal): Promise<MarketOverviewTrendItem[]> {
  const res = await apiFetch(`${BASE}/market/overview-trend?date=${date}&days=${days}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch market overview trend: ${res.statusText}`)
  }
  const json = await res.json()
  return json.trend
}

export async function fetchQuantzzDaily(date: string, days = 60, signal?: AbortSignal): Promise<QuantzzDailyOverview> {
  const res = await apiFetch(`${BASE}/quantzz/daily?date=${date}&days=${days}`, { signal })
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
  const res = await apiFetch(`${BASE}/plate-rotation?${params.toString()}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch plate rotation: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchPremarketGuide(date?: string, signal?: AbortSignal): Promise<PremarketGuide> {
  const query = date ? `?date=${date}` : ''
  const res = await apiFetch(`${BASE}/premarket${query}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch premarket guide: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchInsights(date: string, signal?: AbortSignal): Promise<MarketInsights> {
  const res = await apiFetch(`${BASE}/insights?date=${date}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch insights: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchHot(date: string, signal?: AbortSignal): Promise<HotData> {
  const res = await apiFetch(`${BASE}/hot?date=${date}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch hot data: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchHotDates(signal?: AbortSignal): Promise<string[]> {
  const res = await apiFetch(`${BASE}/hot/dates`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch hot dates: ${res.statusText}`)
  }
  const json = await res.json()
  return json.dates
}

export async function fetchLatestJob(signal?: AbortSignal): Promise<DataJob | null> {
  const res = await apiFetch(`${BASE}/jobs/latest?job_name=daily_update`, { signal })
  if (res.status === 404) {
    return null
  }
  if (!res.ok) {
    throw new Error(`Failed to fetch latest job: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchAnnouncements(
  date: string,
  params: { noticeType?: string; q?: string } = {},
  signal?: AbortSignal,
): Promise<AnnouncementListData> {
  const query = new URLSearchParams({ date })
  if (params.noticeType) query.set('notice_type', params.noticeType)
  if (params.q) query.set('q', params.q)
  const res = await apiFetch(`${BASE}/announcements?${query.toString()}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch announcements: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchAnnouncementDetail(artCode: string, signal?: AbortSignal): Promise<AnnouncementDetail> {
  const res = await apiFetch(`${BASE}/announcements/${encodeURIComponent(artCode)}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch announcement detail: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchNews(
  date: string,
  params: { source?: string; q?: string } = {},
  signal?: AbortSignal,
): Promise<NewsListData> {
  const query = new URLSearchParams({ date })
  if (params.source) query.set('source', params.source)
  if (params.q) query.set('q', params.q)
  const res = await apiFetch(`${BASE}/news?${query.toString()}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch news: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchNewsDates(signal?: AbortSignal): Promise<string[]> {
  const res = await apiFetch(`${BASE}/news/dates`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch news dates: ${res.statusText}`)
  }
  const json = await res.json()
  return json.dates
}

export async function fetchResearchReportDates(signal?: AbortSignal): Promise<string[]> {
  const res = await apiFetch(`${BASE}/research-reports/dates`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch research report dates: ${res.statusText}`)
  }
  const json = await res.json()
  return json.dates
}

export async function fetchResearchReports(
  date: string,
  params: { q?: string; rating?: string; org?: string } = {},
  signal?: AbortSignal,
): Promise<ResearchReportListData> {
  const query = new URLSearchParams({ date })
  if (params.q) query.set('q', params.q)
  if (params.rating) query.set('rating', params.rating)
  if (params.org) query.set('org', params.org)
  const res = await apiFetch(`${BASE}/research-reports?${query.toString()}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch research reports: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchResearchReportDetail(infoCode: string, signal?: AbortSignal): Promise<ResearchReportDetail> {
  const res = await apiFetch(`${BASE}/research-reports/${encodeURIComponent(infoCode)}`, { signal })
  if (!res.ok) {
    throw new Error(`Failed to fetch research report detail: ${res.statusText}`)
  }
  return res.json()
}
