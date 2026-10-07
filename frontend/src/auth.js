export class ApiError extends Error {
  constructor(message, status, errors = {}) {
    super(message)
    this.status = status
    this.errors = errors
  }
}

export function createAuthApi(baseUrl = import.meta.env?.VITE_API_BASE_URL) {
  async function request(path, { method = 'GET', data, signal, csrfToken } = {}) {
    if (!baseUrl?.trim()) throw new Error('API base URL is not configured')
    let response
    try {
      response = await fetch(`${baseUrl.trim().replace(/\/+$/, '')}/auth/${path}/`, {
        method, credentials: 'include', signal,
        headers: data ? { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken } : {},
        ...(data ? { body: JSON.stringify(data) } : {}),
      })
    } catch (error) {
      if (error.name === 'AbortError') throw error
      throw new Error('API unavailable. Check the backend and reload.')
    }
    const body = await response.json().catch(() => ({}))
    if (!response.ok) {
      const message = response.status >= 500 ? 'API unavailable. Try again later.'
        : response.status === 403 ? 'Request denied. Sign in or reload to refresh CSRF protection.'
        : 'Check the submitted fields.'
      throw new ApiError(message, response.status, body)
    }
    return body
  }
  async function write(path, data) {
    // Bootstrap before every write so login's CSRF rotation and other tabs work.
    // Neither session identifiers nor CSRF tokens enter browser storage.
    const { csrfToken } = await request('csrf')
    return request(path, { method: 'POST', data, csrfToken })
  }
  return {
    me: (signal) => request('me', { signal }),
    register: (data) => write('register', data),
    login: (data) => write('login', data),
    logout: () => write('logout', {}),
  }
}

export const initialAuthState = { status: 'checking', user: null }
export function authReducer(state, action) {
  switch (action.type) {
    case 'authenticated': return { status: 'authenticated', user: action.user }
    case 'unauthenticated': return { status: 'unauthenticated', user: null }
    case 'unavailable': return { status: 'unavailable', user: null }
    default: return state
  }
}

export async function loadAuth(api, signal) {
  try {
    return { type: 'authenticated', user: await api.me(signal) }
  } catch (error) {
    if (error.name === 'AbortError') throw error
    return { type: error.status === 401 || error.status === 403 ? 'unauthenticated' : 'unavailable' }
  }
}
