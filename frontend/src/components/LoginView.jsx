import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

/** Pantalla de acceso Control Tower — autenticación contra la API corporativa (api-int.yego.pro). */
export default function LoginView () {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const from = location.state?.from?.pathname || '/'

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!username.trim() || !password) {
      setError('Introduce usuario y contraseña.')
      return
    }
    setLoading(true)
    try {
      await login(username.trim(), password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err.message || 'No se pudo iniciar sesión.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-600 shadow-lg shadow-blue-900/40 mb-4">
            <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            <span className="text-white">YEGO</span>
            <span className="text-slate-400 font-normal ml-1.5">Control Tower</span>
          </h1>
          <p className="text-slate-400 text-sm mt-2">Visibilidad operativa y toma de decisiones</p>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl shadow-black/30 p-8 border border-slate-200/80">
          <h2 className="text-lg font-semibold text-slate-800 mb-6 text-center">Iniciar sesión</h2>
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="ct-user" className="block text-sm font-medium text-slate-600 mb-1.5">
                Usuario
              </label>
              <input
                id="ct-user"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-slate-900 placeholder-slate-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
                placeholder="tu.usuario"
                disabled={loading}
              />
            </div>
            <div>
              <label htmlFor="ct-pass" className="block text-sm font-medium text-slate-600 mb-1.5">
                Contraseña
              </label>
              <input
                id="ct-pass"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-slate-900 placeholder-slate-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
                placeholder="••••••••"
                disabled={loading}
              />
            </div>
            {error && (
              <div className="rounded-lg bg-red-50 border border-red-100 text-red-700 text-sm px-4 py-3" role="alert">
                {error}
              </div>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold text-sm transition shadow-md"
            >
              {loading ? 'Entrando…' : 'Entrar'}
            </button>
          </form>
          <p className="mt-6 text-center text-xs text-slate-500">
            ¿Problemas con tu cuenta corporativa?{' '}
            <a
              href="https://integral.yego.pro/login"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-700 font-medium"
            >
              Portal de empresa
            </a>
          </p>
        </div>
        <p className="text-center text-slate-600 text-xs mt-8">
          Acceso con tu <span className="text-slate-500">usuario y contraseña corporativos YEGO</span>.
        </p>
        {import.meta.env.DEV && (
          <p className="text-center text-slate-500 text-[11px] mt-3 max-w-sm mx-auto leading-relaxed">
            El login va en <span className="text-slate-400">HTTPS</span> directo a la API corporativa
            (configurable con <code className="text-slate-400">VITE_INTEGRAL_AUTH_LOGIN_URL</code>). Si el navegador
            bloquea la petición, la API debe permitir CORS desde este origen.
          </p>
        )}
      </div>
    </div>
  )
}
