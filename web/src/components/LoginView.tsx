import { useState } from 'react'
import type { FormEvent } from 'react'
import { login } from '../api/client'
import type { AuthUser } from '../types'

interface Props {
  onLogin: (user: AuthUser) => void
  onCancel?: () => void
}

export function LoginView({ onLogin, onCancel }: Props) {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const session = await login(username, password)
      onLogin(session.user)
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="login-brand">
          <span className="section-kicker">发家致富</span>
          <h1>登录复盘系统</h1>
          <p>使用本地账号进入复盘、公告、新闻和后续个人关注模块。</p>
        </div>
        {onCancel ? (
          <button type="button" className="login-close" onClick={onCancel} aria-label="关闭登录">
            ×
          </button>
        ) : null}
        <form className="login-form" onSubmit={submit}>
          <label>
            <span>账号</span>
            <input
              value={username}
              autoComplete="username"
              onChange={event => setUsername(event.target.value)}
            />
          </label>
          <label>
            <span>密码</span>
            <input
              value={password}
              type="password"
              autoComplete="current-password"
              placeholder="请输入密码"
              onChange={event => setPassword(event.target.value)}
            />
          </label>
          {error ? <div className="login-error">{error}</div> : null}
          <button type="submit" disabled={loading || !username || !password}>
            {loading ? '登录中...' : '登录'}
          </button>
        </form>
      </section>
    </main>
  )
}
