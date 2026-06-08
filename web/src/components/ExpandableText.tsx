import { useState, type CSSProperties } from 'react'

interface Props {
  text?: string | null
  className?: string
  lines?: number
  emptyText?: string
}

export function ExpandableText({ text, className = '', lines = 2, emptyText = '-' }: Props) {
  const [expanded, setExpanded] = useState(false)
  const value = (text ?? '').trim()

  if (!value) {
    return <span className={className}>{emptyText}</span>
  }

  return (
    <button
      type="button"
      className={`expandable-text ${expanded ? 'expanded' : ''} ${className}`.trim()}
      style={{ '--line-count': lines } as CSSProperties}
      aria-expanded={expanded}
      onClick={() => setExpanded(open => !open)}
      title={expanded ? '点击收起' : '点击展开全文'}
    >
      <span>{value}</span>
      <em>{expanded ? '收起' : '展开'}</em>
    </button>
  )
}
