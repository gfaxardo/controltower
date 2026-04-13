import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { loginIntegral } from '../services/api'

const STORAGE_TOKEN = 'ct_integral_token'
const STORAGE_SESSION = 'ct_integral_session_ok'
const STORAGE_USER = 'ct_integral_username'
const STORAGE_ROLE = 'ct_integral_role'

/** Texto legible del rol desde la respuesta típica de api-int (role, roles[], user.role, data, etc.). */
function extractRoleLabel (data) {
  if (!data || typeof data !== 'object') return null
  const u = data.user || data.usuario || data.data?.user || data.data
  const direct =
    data.role ??
    data.rol ??
    data.perfil ??
    data.role_name ??
    (u && typeof u === 'object' ? (u.role ?? u.rol ?? u.perfil ?? u.role_name) : null)
  if (direct != null && direct !== '') {
    return String(direct)
  }
  const roles = data.roles ?? data.data?.roles ?? (u && u.roles)
  if (Array.isArray(roles) && roles.length > 0) {
    return roles.map((r) => (typeof r === 'string' ? r : r?.name || r?.role || String(r))).filter(Boolean).join(', ')
  }
  if (typeof roles === 'string' && roles.trim()) return roles.trim()
  return null
}

function tryRoleFromJwt (token) {
  if (!token || typeof token !== 'string') return null
  const parts = token.split('.')
  if (parts.length < 2) return null
  try {
    let b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const pad = b64.length % 4 === 0 ? '' : '='.repeat(4 - (b64.length % 4))
    const payload = JSON.parse(atob(b64 + pad))
    const r =
      payload.role ??
      payload.rol ??
      (Array.isArray(payload.roles) ? payload.roles.join(', ') : payload.roles) ??
      payload.authority
    return r != null && String(r).trim() ? String(r).trim() : null
  } catch {
    return null
  }
}

/** Si no es exactamente 'false', el login es obligatorio (producción). En .env local: VITE_AUTH_REQUIRED=false */
const AUTH_REQUIRED = import.meta.env.VITE_AUTH_REQUIRED !== 'false'

function extractToken (data) {
  if (!data || typeof data !== 'object') return null
  return (
    data.token ||
    data.access_token ||
    data.accessToken ||
    data.jwt ||
    (data.data && (data.data.token || data.data.access_token)) ||
    null
  )
}

function readAuthenticated () {
  if (!AUTH_REQUIRED) return true
  if (typeof window === 'undefined') return false
  return Boolean(
    window.sessionStorage.getItem(STORAGE_TOKEN) ||
      window.sessionStorage.getItem(STORAGE_SESSION)
  )
}

const AuthContext = createContext({
  authRequired: AUTH_REQUIRED,
  isAuthenticated: !AUTH_REQUIRED,
  username: null,
  role: null,
  login: async () => {},
  logout: () => {}
})

export function AuthProvider ({ children }) {
  const [tick, setTick] = useState(0)
  const isAuthenticated = useMemo(() => {
    void tick
    return readAuthenticated()
  }, [tick])

  const username = useMemo(() => {
    void tick
    if (typeof window === 'undefined') return null
    return window.sessionStorage.getItem(STORAGE_USER)
  }, [tick])

  const role = useMemo(() => {
    void tick
    if (typeof window === 'undefined') return null
    return window.sessionStorage.getItem(STORAGE_ROLE)
  }, [tick])

  const login = useCallback(async (user, password) => {
    const res = await loginIntegral(user, password)
    if (res.status !== 200) {
      const msg = res.data?.message || res.data?.error || `Error ${res.status}`
      throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    }
    const data = res.data
    const token = extractToken(data)
    if (token) {
      window.sessionStorage.setItem(STORAGE_TOKEN, token)
    } else {
      // Algunas respuestas solo confirman sesión sin JWT en body
      window.sessionStorage.setItem(STORAGE_SESSION, '1')
    }
    window.sessionStorage.setItem(STORAGE_USER, user.trim())
    let roleLabel = extractRoleLabel(data)
    if (!roleLabel && token) {
      roleLabel = tryRoleFromJwt(token)
    }
    if (roleLabel) {
      window.sessionStorage.setItem(STORAGE_ROLE, roleLabel)
    } else {
      window.sessionStorage.removeItem(STORAGE_ROLE)
    }
    setTick((t) => t + 1)
  }, [])

  const logout = useCallback(() => {
    window.sessionStorage.removeItem(STORAGE_TOKEN)
    window.sessionStorage.removeItem(STORAGE_SESSION)
    window.sessionStorage.removeItem(STORAGE_USER)
    window.sessionStorage.removeItem(STORAGE_ROLE)
    setTick((t) => t + 1)
  }, [])

  const value = useMemo(
    () => ({
      authRequired: AUTH_REQUIRED,
      isAuthenticated,
      username,
      role,
      login,
      logout
    }),
    [isAuthenticated, username, role, login, logout]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth () {
  return useContext(AuthContext)
}

export { AUTH_REQUIRED }
