import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'
import type { MarketOverviewTrendItem } from '../types'

interface Props {
  trend: MarketOverviewTrendItem[]
}

function amountToYi(value: number | null) {
  return value == null ? null : Number((value / 100000000).toFixed(0))
}

export function MarketOverviewTrend({ trend }: Props) {
  const amountRef = useRef<HTMLDivElement>(null)
  const breadthRef = useRef<HTMLDivElement>(null)
  const amountChart = useRef<echarts.ECharts | null>(null)
  const breadthChart = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!amountRef.current || !breadthRef.current || trend.length === 0) return
    if (!amountChart.current) amountChart.current = echarts.init(amountRef.current)
    if (!breadthChart.current) breadthChart.current = echarts.init(breadthRef.current)

    const dates = trend.map(item => item.date.slice(5))
    const amounts = trend.map(item => amountToYi(item.amount))
    const upRates = trend.map(item => item.up_rate)

    const common = {
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#1e2330',
        borderColor: '#30363d',
        textStyle: { color: '#e6edf3', fontSize: 12 },
      },
      grid: { top: 34, right: 44, bottom: 24, left: 48 },
      xAxis: {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: '#30363d' } },
        axisLabel: { color: '#8b949e', fontSize: 11 },
        axisTick: { show: false },
      },
    }

    amountChart.current.setOption({
      ...common,
      legend: {
        data: ['成交额', '红盘率'],
        textStyle: { color: '#8b949e', fontSize: 11 },
        top: 0,
        right: 0,
        itemWidth: 14,
        itemHeight: 8,
      },
      yAxis: [
        {
          type: 'value',
          name: '亿',
          nameTextStyle: { color: '#8b949e', fontSize: 10 },
          axisLabel: { color: '#8b949e', fontSize: 11 },
          splitLine: { lineStyle: { color: '#21262d' } },
        },
        {
          type: 'value',
          name: '%',
          min: 0,
          max: 100,
          nameTextStyle: { color: '#8b949e', fontSize: 10 },
          axisLabel: { color: '#8b949e', fontSize: 11 },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: '成交额',
          type: 'bar',
          data: amounts,
          barWidth: 22,
          itemStyle: {
            color: '#58a6ff',
            borderRadius: [2, 2, 0, 0],
          },
        },
        {
          name: '红盘率',
          type: 'line',
          yAxisIndex: 1,
          data: upRates,
          smooth: true,
          symbolSize: 6,
          lineStyle: { width: 2, color: '#d29922' },
          itemStyle: { color: '#d29922' },
        },
      ],
    })

    breadthChart.current.setOption({
      ...common,
      legend: {
        data: ['涨停', '跌停', '炸板'],
        textStyle: { color: '#8b949e', fontSize: 11 },
        top: 0,
        right: 0,
        itemWidth: 14,
        itemHeight: 8,
      },
      yAxis: {
        type: 'value',
        name: '只',
        nameTextStyle: { color: '#8b949e', fontSize: 10 },
        axisLabel: { color: '#8b949e', fontSize: 11 },
        splitLine: { lineStyle: { color: '#21262d' } },
      },
      series: [
        {
          name: '涨停',
          type: 'line',
          data: trend.map(item => item.limit_up_count),
          smooth: true,
          symbolSize: 6,
          lineStyle: { width: 2, color: '#f85149' },
          itemStyle: { color: '#f85149' },
        },
        {
          name: '跌停',
          type: 'line',
          data: trend.map(item => item.limit_down_count),
          smooth: true,
          symbolSize: 6,
          lineStyle: { width: 2, color: '#3fb950' },
          itemStyle: { color: '#3fb950' },
        },
        {
          name: '炸板',
          type: 'bar',
          data: trend.map(item => item.broken_limit_up_count),
          barWidth: 16,
          itemStyle: { color: '#d29922', borderRadius: [2, 2, 0, 0] },
        },
      ],
    })

    return () => { /* keep charts mounted */ }
  }, [trend])

  useEffect(() => {
    const handleResize = () => {
      amountChart.current?.resize()
      breadthChart.current?.resize()
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const latest = trend.at(-1)

  return (
    <div className="market-trend">
      <div className="market-trend-summary">
        <span>近{trend.length}日</span>
        <strong>{latest?.amount != null ? `${amountToYi(latest.amount)}亿` : '-'}</strong>
        <small>最新成交额</small>
        <strong>{latest?.up_rate != null ? `${latest.up_rate.toFixed(1)}%` : '-'}</strong>
        <small>红盘率</small>
      </div>
      <div className="market-trend-grid">
        <div ref={amountRef} className="market-trend-chart" />
        <div ref={breadthRef} className="market-trend-chart" />
      </div>
    </div>
  )
}
