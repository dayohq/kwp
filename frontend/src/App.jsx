import { useEffect, useState } from 'react'
import { checkHealth } from './api'
import './App.css'

function App() {
  const [status, setStatus] = useState('Checking...')

  useEffect(() => {
    const controller = new AbortController()
    checkHealth({ signal: controller.signal })
      .then(() => {
        if (!controller.signal.aborted) setStatus('Connected')
      })
      .catch(() => {
        if (!controller.signal.aborted) setStatus('Unavailable')
      })
    return () => controller.abort()
  }, [])

  return (
    <main id="center">
      <h1>KWP</h1>
      <p role="status">API status: {status}</p>
    </main>
  )
}

export default App
