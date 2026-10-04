import assert from 'node:assert/strict'
import { afterEach, mock, test } from 'node:test'
import { checkHealth } from '../src/api.js'

afterEach(() => mock.restoreAll())

test('requests the configured health URL and accepts a healthy response', async () => {
  const fetchMock = mock.method(globalThis, 'fetch', async () =>
    new Response(JSON.stringify({ status: 'ok' }), { status: 200 }))
  const controller = new AbortController()
  await checkHealth({ baseUrl: 'http://backend.example/api/', signal: controller.signal })
  assert.equal(fetchMock.mock.calls[0].arguments[0], 'http://backend.example/api/health/')
  assert.equal(fetchMock.mock.calls[0].arguments[1].signal, controller.signal)
})

test('rejects missing API configuration without requesting another origin', async () => {
  const fetchMock = mock.method(globalThis, 'fetch', async () => {})
  await assert.rejects(checkHealth({ baseUrl: '' }))
  assert.equal(fetchMock.mock.callCount(), 0)
})

test('rejects network failure cleanly', async () => {
  mock.method(globalThis, 'fetch', async () => { throw new TypeError('Network unavailable') })
  await assert.rejects(checkHealth({ baseUrl: 'http://backend.example/api' }))
})

test('rejects HTTP errors, unexpected status and malformed JSON', async () => {
  for (const response of [new Response('{}', { status: 503 }),
    new Response('{"status":"unexpected"}'), new Response('invalid JSON')]) {
    mock.method(globalThis, 'fetch', async () => response)
    await assert.rejects(checkHealth({ baseUrl: 'http://backend.example/api' }))
    mock.restoreAll()
  }
})
