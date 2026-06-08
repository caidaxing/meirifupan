import { useState, type ReactNode } from 'react'

interface Props {
  title: string
  children: ReactNode
  defaultOpen?: boolean
  summary?: string
  flush?: boolean
}

export function CollapsibleSection({ title, children, defaultOpen = false, summary, flush = false }: Props) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <section className={`collapsible-section ${flush ? 'flush' : ''} ${open ? 'open' : ''}`.trim()}>
      <button
        type="button"
        className="collapsible-header"
        aria-expanded={open}
        onClick={() => setOpen(value => !value)}
      >
        <span>{title}</span>
        {summary && <small>{summary}</small>}
        <strong>{open ? '收起' : '展开'}</strong>
      </button>
      {open && <div className="collapsible-body">{children}</div>}
    </section>
  )
}
