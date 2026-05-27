/**
 * SafeFetch — FASE H1 Drivers Operational Hardening
 *
 * Wrapper sobre axios para peticiones seguras con:
 *  - timeout configurable (default 30s)
 *  - retries opcionales (default 0)
 *  - error normalizado
 *  - fallback data opcional
 *  - status mapping (ok, warning, blocked)
 *
 * Uso inicial: componentes Drivers.
 * No refactor global agresivo. Adopción progresiva.
 */
import api from '../services/api'

const DEFAULT_TIMEOUT = 30000
const DEFAULT_RETRIES = 0

/**
 * Normaliza un error de axios a un objeto plano.
 */
function normalizeError (err, url) {
  if (err?.response) {
    return {
      status: err.response.status,
      statusText: err.response.statusText,
      data: err.response.data,
      detail: err.response.data?.detail || err.response.statusText || 'Server error',
      url,
    }
  }
  if (err?.request) {
    return {
      status: 0,
      statusText: 'Network Error',
      detail: err.message || 'Network request failed',
      url,
    }
  }
  return {
    status: -1,
    statusText: 'Request Error',
    detail: err?.message || 'Unknown error',
    url,
  }
}

/**
 * safeFetch(url, options)
 *
 * Options:
 *  - method: 'GET' (default)
 *  - params: query params object
 *  - data: request body (for POST)
 *  - timeout: ms (default 30000)
 *  - retries: 0|1 (default 0)
 *  - fallback: valor a devolver si falla
 *
 * Returns { ok, data, error, status }
 *  - ok: true si la petición tuvo éxito
 *  - data: response data
 *  - error: null o error normalizado { status, statusText, detail, url }
 *  - status: 'ok' | 'warning' | 'blocked' | 'error'
 */
export async function safeFetch (url, options = {}) {
  const {
    method = 'GET',
    params,
    data,
    timeout = DEFAULT_TIMEOUT,
    retries = DEFAULT_RETRIES,
    fallback,
  } = options

  let lastError = null
  const maxAttempts = 1 + Math.min(retries || 0, 1)

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      const config = {
        method,
        url,
        timeout,
      }
      if (params) config.params = params
      if (data) config.data = data

      const res = await api(config)

      // Map HTTP status to operational status
      let opStatus = 'ok'
      if (res.status >= 500) opStatus = 'blocked'
      else if (res.status >= 400) opStatus = 'warning'

      return {
        ok: true,
        data: res.data,
        error: null,
        status: res.data?.status || opStatus,
      }
    } catch (err) {
      lastError = normalizeError(err, url)
      // Only retry on network errors (status 0) or 5xx
      if (attempt < maxAttempts - 1 && (lastError.status === 0 || lastError.status >= 500)) {
        await new Promise((resolve) => setTimeout(resolve, 1000 * (attempt + 1)))
        continue
      }
      break
    }
  }

  // All attempts failed
  if (fallback !== undefined) {
    return {
      ok: false,
      data: fallback,
      error: lastError,
      status: 'warning',
      _fallback: true,
    }
  }

  return {
    ok: false,
    data: null,
    error: lastError,
    status: lastError?.status === 0 ? 'blocked' : 'error',
  }
}

/**
 * safeFetchMulti(urls, options)
 *
 * Ejecuta múltiples safeFetch en paralelo con Promise.allSettled.
 * Cada URL puede ser string o { url, options }.
 *
 * Returns { results: [...] } donde cada item es { url, ...safeFetchResult }
 */
export async function safeFetchMulti (urls, baseOptions = {}) {
  const requests = urls.map((item) => {
    const url = typeof item === 'string' ? item : item.url
    const opts = typeof item === 'string' ? baseOptions : { ...baseOptions, ...item.options }
    return safeFetch(url, opts).then((result) => ({ url, ...result }))
  })

  const results = await Promise.allSettled(requests)

  return {
    results: results.map((r) =>
      r.status === 'fulfilled'
        ? r.value
        : {
            url: 'unknown',
            ok: false,
            data: null,
            error: { status: -1, detail: 'Promise rejected unexpectedly', url: 'unknown' },
            status: 'blocked',
          }
    ),
  }
}

export default safeFetch
