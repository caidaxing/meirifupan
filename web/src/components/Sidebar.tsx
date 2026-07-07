import { useState } from 'react'
import type { AuthUser } from '../types'

export type ModuleKey = 'review' | 'emotion' | 'news' | 'social' | 'data-overview'

interface Props {
  active: ModuleKey
  onChange: (key: ModuleKey) => void
  collapsed: boolean
  onToggle: () => void
  user: AuthUser | null
  onLoginClick: () => void
  onLogout: () => void
}

const modules: { key: ModuleKey; icon: string; label: string; disabled?: boolean }[] = [
  { key: 'review', icon: '📊', label: '复盘' },
  { key: 'emotion', icon: '🔥', label: '盘中情绪' },
  { key: 'news', icon: '📰', label: '新闻资讯' },
  { key: 'social', icon: '💬', label: '社媒舆情', disabled: true },
]

export function Sidebar({ active, onChange, collapsed, onToggle, user, onLoginClick, onLogout }: Props) {
  const [hovered, setHovered] = useState<string | null>(null)

  return (
    <nav className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''}`}>
      <div className="sidebar-top">
        {!collapsed && <span className="sidebar-logo">发家致富</span>}
        <button className="sidebar-toggle" onClick={onToggle} title={collapsed ? '展开' : '折叠'}>
          {collapsed ? '▶' : '◀'}
        </button>
      </div>

      <div className="sidebar-modules">
        {modules.map(mod => (
          <button
            key={mod.key}
            className={`sidebar-item ${active === mod.key ? 'active' : ''} ${mod.disabled ? 'disabled' : ''}`}
            onClick={() => !mod.disabled && onChange(mod.key)}
            onMouseEnter={() => setHovered(mod.key)}
            onMouseLeave={() => setHovered(null)}
            disabled={mod.disabled}
          >
            <span className="sidebar-icon">{mod.icon}</span>
            <span className="sidebar-label">{mod.label}</span>
            {collapsed && hovered === mod.key && (
              <span className="sidebar-tooltip">{mod.label}{mod.disabled ? ' (即将上线)' : ''}</span>
            )}
            {mod.disabled && !collapsed && <span className="sidebar-badge">即将上线</span>}
          </button>
        ))}
      </div>

      <div className="sidebar-bottom">
        {user ? (
          <div className="sidebar-user">
            <span>{user.username}</span>
          </div>
        ) : null}
        <button
          className={`sidebar-item ${active === 'data-overview' ? 'active' : ''}`}
          onClick={() => onChange('data-overview' as ModuleKey)}
          onMouseEnter={() => setHovered('data-overview')}
          onMouseLeave={() => setHovered(null)}
        >
          <span className="sidebar-icon">📋</span>
          <span className="sidebar-label">数据总览</span>
          {collapsed && hovered === 'data-overview' && (
            <span className="sidebar-tooltip">数据总览</span>
          )}
        </button>
        {user ? (
          <button className="sidebar-item sidebar-logout" onClick={onLogout}>
            <span className="sidebar-icon">↩</span>
            <span className="sidebar-label">退出</span>
          </button>
        ) : (
          <button className="sidebar-item sidebar-login" onClick={onLoginClick}>
            <span className="sidebar-icon">🔐</span>
            <span className="sidebar-label">登录</span>
          </button>
        )}
      </div>
    </nav>
  )
}
