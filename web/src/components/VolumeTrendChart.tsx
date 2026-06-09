import { useEffect, useMemo, useRef } from 'react'
import * as echarts from 'echarts'
import type { MarketOverviewTrendItem } from '../types'

interface Props {
  trend: MarketOverviewTrendItem[]
}

function amountToYi(value: number | null) {
  return value == null ? null : Math.round(value / 100000000)
}

function movingAverage(values: Array<number | null>, windowSize: number) {
  return values.map((_, index) => {
    const window = values.slice(Math.max(0, index - windowSize + 1), index + 1).filter((item): item is number => item != null)
    if (window.length === 0) return null
    return Math.round(window.reduce((sum, item) => sum + item, 0) / window.length)
  })
}

export function VolumeTrendChart({ trend }: Props) {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts | null>(null)
  const volumeTrend = useMemo(() => trend.filter(item => item.amount != null), [trend])

  useEffect(() => {
    if (!chartRef.current || volumeTrend.length === 0) return
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current)
    }
    const chart = chartInstance.current

    const dates = volumeTrend.map(item => item.date.slice(5))
    const amounts = volumeTrend.map(item => amountToYi(item.amount))
    const avg = movingAverage(amounts, 5)
    const validAmounts = amounts.filter((item): item is number => item != null)
    const minAmount = Math.min(...validAmounts)
    const maxAmount = Math.max(...validAmounts)
    const yMin = Math.max(0, Math.floor((minAmount * 0.55) / 1000) * 1000)
    const yMax = Math.ceil((maxAmount * 1.08) / 1000) * 1000

    chart.setOption({
      animation: false,
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#1e2330',
        borderColor: '#30363d',
        textStyle: { color: '#e6edf3', fontSize: 12 },
        valueFormatter: (value: number | string) => (value == null || value === '-' ? '-' : `${value}亿`),
      },
      legend: {
        data: ['成交额', '5日均量'],
        top: 0,
        right: 0,
        textStyle: { color: '#8b949e', fontSize: 11 },
        itemWidth: 14,
        itemHeight: 8,
      },
      grid: { top: 34, right: 14, bottom: 26, left: 52 },
      xAxis: {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: '#30363d' } },
        axisLabel: { color: '#8b949e', fontSize: 10 },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        name: '亿',
        min: yMin,
        max: yMax,
        nameTextStyle: { color: '#8b949e', fontSize: 10 },
        axisLabel: { color: '#8b949e', fontSize: 10 },
        splitLine: { lineStyle: { color: '#21262d', type: 'dashed' } },
      },
      series: [
        {
          name: '成交额',
          type: 'bar',
          data: amounts.map((value, index) => ({
            value,
            itemStyle: {
              color: index === 0 || value == null || amounts[index - 1] == null || value >= (amounts[index - 1] ?? 0)
                ? '#f85149'
                : '#2ea043',
            },
          })),
          barMaxWidth: 16,
          itemStyle: { borderRadius: [2, 2, 0, 0] },
        },
        {
          name: '5日均量',
          type: 'line',
          data: avg,
          symbol: 'none',
          smooth: true,
          lineStyle: { width: 2, color: '#d29922' },
        },
      ],
    })
  }, [volumeTrend])

  useEffect(() => {
    const handleResize = () => chartInstance.current?.resize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  if (volumeTrend.length === 0) {
    return <div className="home-chart-empty">暂无量能数据</div>
  }

  return <div ref={chartRef} className="home-chart home-chart-volume" />
}
