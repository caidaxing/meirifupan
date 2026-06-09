import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'
import type { EmotionTrendItem, MarketOverviewTrendItem } from '../types'

interface Props {
  emotionTrend: EmotionTrendItem[]
  marketTrend: MarketOverviewTrendItem[]
}

export function EmotionCycleChart({ emotionTrend, marketTrend }: Props) {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!chartRef.current || emotionTrend.length === 0) return
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current)
    }
    const chart = chartInstance.current
    const marketByDate = new Map(marketTrend.map(item => [item.date, item]))
    const dates = emotionTrend.map(item => item.date)
    const labels = dates.map(date => date.slice(5))
    const scores = emotionTrend.map(item => item.total_score)
    const limitUps = emotionTrend.map(item => item.scores.limit_up_count.value)
    const highBoards = emotionTrend.map(item => item.scores.board_height.value)
    const riskBars = dates.map(date => {
      const item = marketByDate.get(date)
      if (!item || item.has_limit_up_events === false) return null
      return (item.limit_down_count || 0) + (item.broken_limit_up_count || 0)
    })

    chart.setOption({
      animation: false,
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#1e2330',
        borderColor: '#30363d',
        textStyle: { color: '#e6edf3', fontSize: 12 },
      },
      legend: {
        data: ['情绪分', '涨停家数', '亏钱反馈', '连板高度'],
        top: 0,
        right: 0,
        textStyle: { color: '#8b949e', fontSize: 11 },
        itemWidth: 14,
        itemHeight: 8,
      },
      grid: { top: 34, right: 46, bottom: 26, left: 38 },
      xAxis: {
        type: 'category',
        data: labels,
        axisLine: { lineStyle: { color: '#30363d' } },
        axisLabel: { color: '#8b949e', fontSize: 10 },
        axisTick: { show: false },
      },
      yAxis: [
        {
          type: 'value',
          name: '情绪',
          min: 0,
          max: 3,
          interval: 0.75,
          nameTextStyle: { color: '#8b949e', fontSize: 10 },
          axisLabel: { color: '#8b949e', fontSize: 10 },
          splitLine: { lineStyle: { color: '#21262d', type: 'dashed' } },
        },
        {
          type: 'value',
          name: '数量',
          nameTextStyle: { color: '#8b949e', fontSize: 10 },
          axisLabel: { color: '#8b949e', fontSize: 10 },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: '亏钱反馈',
          type: 'bar',
          yAxisIndex: 1,
          data: riskBars,
          barMaxWidth: 12,
          itemStyle: { color: '#2ea043', borderRadius: [2, 2, 0, 0] },
        },
        {
          name: '涨停家数',
          type: 'bar',
          yAxisIndex: 1,
          data: limitUps,
          barMaxWidth: 12,
          itemStyle: { color: 'rgba(248,81,73,0.55)', borderRadius: [2, 2, 0, 0] },
        },
        {
          name: '情绪分',
          type: 'line',
          data: scores,
          smooth: false,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { width: 2, color: '#f0883e' },
          itemStyle: { color: '#f0883e', borderColor: '#fff', borderWidth: 1 },
          markLine: {
            symbol: 'none',
            label: { show: false },
            lineStyle: { color: '#58a6ff', width: 1, type: 'solid', opacity: 0.45 },
            data: [{ yAxis: 0.75 }, { yAxis: 2.25 }],
          },
        },
        {
          name: '连板高度',
          type: 'line',
          yAxisIndex: 1,
          data: highBoards,
          symbol: 'diamond',
          symbolSize: 6,
          lineStyle: { width: 1.5, color: '#bc8cff', type: 'dashed' },
          itemStyle: { color: '#bc8cff' },
        },
      ],
    })
  }, [emotionTrend, marketTrend])

  useEffect(() => {
    const handleResize = () => chartInstance.current?.resize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  if (emotionTrend.length === 0) {
    return <div className="home-chart-empty">暂无情绪数据</div>
  }

  return <div ref={chartRef} className="home-chart home-chart-emotion" />
}
