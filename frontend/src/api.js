export async function checkHealth(
  { baseUrl = import.meta.env?.VITE_API_BASE_URL, signal } = {},
) {
  if (!baseUrl?.trim()) throw new Error('API base URL is not configured')
  const response = await fetch(`${baseUrl.trim().replace(/\/+$/, '')}/health/`, {
    signal,
  })
  if (!response.ok) throw new Error('Health request failed')
  const body = await response.json()
  if (body.status !== 'ok') throw new Error('Unexpected health response')
}
