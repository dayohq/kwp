import { useEffect, useReducer, useState } from 'react'
import { checkHealth } from './api'
import { authReducer, createAuthApi, initialAuthState, loadAuth } from './auth'
import './App.css'

const api = createAuthApi()

function App() {
  const [status, setStatus] = useState('Checking...')
  const [auth, dispatch] = useReducer(authReducer, initialAuthState)
  const [mode, setMode] = useState('login')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    checkHealth({ signal: controller.signal })
      .then(() => { if (!controller.signal.aborted) setStatus('Connected') })
      .catch(() => { if (!controller.signal.aborted) setStatus('Unavailable') })
    loadAuth(api, controller.signal)
      .then((action) => { if (!controller.signal.aborted) dispatch(action) })
      .catch(() => {}) // An aborted unmounted request has no UI to update.
    return () => controller.abort()
  }, [])

  async function submit(event) {
    event.preventDefault()
    const form = event.currentTarget
    const data = Object.fromEntries(new FormData(form))
    setBusy(true)
    setMessage('')
    try {
      if (mode === 'register') {
        await api.register(data)
        setMode('login')
        dispatch({ type: 'unauthenticated' })
        setMessage('Registration successful. Sign in with your email and password.')
      } else {
        const user = await api.login(data)
        dispatch({ type: 'authenticated', user })
      }
    } catch (error) {
      const details = Object.entries(error.errors || {})
        .map(([field, errors]) => `${field === 'detail' ? '' : `${field}: `}${Array.isArray(errors) ? errors.join(' ') : errors}`)
        .join(' ')
      setMessage(details || error.message)
      if (!error.status || error.status >= 500) dispatch({ type: 'unavailable' })
    } finally {
      // Passwords exist only in the submitted form/request; clear on all outcomes.
      form.reset()
      setBusy(false)
    }
  }

  async function logout() {
    setBusy(true)
    setMessage('')
    try {
      await api.logout()
      dispatch({ type: 'unauthenticated' })
      setMessage('Logged out.')
    } catch (error) {
      setMessage(error.message)
      // An expired session is already signed out; network failure is distinct.
      if (error.status === 401 || error.status === 403) dispatch(await loadAuth(api))
      else if (!error.status || error.status >= 500) dispatch({ type: 'unavailable' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <main id="center">
      <h1>KWP</h1>
      <p role="status">API status: {status}</p>
      <p>Development authentication: email verification is pending.</p>
      {auth.status === 'checking' && <p role="status">Checking authentication...</p>}
      {auth.status === 'unavailable' && <p role="alert">API unavailable. Check the backend and reload.</p>}
      {auth.status === 'authenticated' && <section>
        <p>Signed in as {auth.user.email}</p>
        <p>Currency: {auth.user.base_currency} · Timezone: {auth.user.timezone}</p>
        <button disabled={busy} onClick={logout}>Logout</button>
      </section>}
      {auth.status === 'unauthenticated' && <section>
        <p role="status">Signed out</p>
        <button disabled={busy} onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setMessage('') }}>
          {mode === 'login' ? 'Create an account' : 'Go to login'}
        </button>
        <form key={mode} onSubmit={submit} aria-label={mode === 'login' ? 'Login' : 'Register'}>
          <label>Email<input name="email" type="email" autoComplete="email" required disabled={busy} /></label>
          {mode === 'register' && <label>Base currency (three uppercase letters)
            <input name="base_currency" pattern="[A-Z]{3}" maxLength={3} required disabled={busy} />
          </label>}
          <label>Password<input name="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required disabled={busy} /></label>
          {mode === 'register' && <label>Confirm password
            <input name="password_confirmation" type="password" autoComplete="new-password" required disabled={busy} />
          </label>}
          <button disabled={busy} type="submit">{busy ? 'Submitting...' : mode === 'login' ? 'Login' : 'Register'}</button>
        </form>
      </section>}
      {message && <p role="alert">{message}</p>}
    </main>
  )
}

export default App
