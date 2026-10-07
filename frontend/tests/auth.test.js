import assert from 'node:assert/strict'
import { afterEach, mock, test } from 'node:test'
import { ApiError, authReducer, createAuthApi, initialAuthState, loadAuth } from '../src/auth.js'

const api = createAuthApi('http://localhost:8000/api/')
const profile = { id: 1, email: 'test@example.com', base_currency: 'USD', timezone: 'Africa/Lagos' }
afterEach(() => mock.restoreAll())

function responses(...values) {
  return mock.method(globalThis, 'fetch', async () => {
    const value = values.shift()
    if (value instanceof Error) throw value
    return new Response(JSON.stringify(value.body), { status: value.status || 200 })
  })
}

test('load distinguishes anonymous, authenticated, unavailable and abort states', async () => {
  responses({status:403,body:{detail:'denied'}}, {body:profile}, new TypeError('offline'), {status:503,body:{}})
  assert.deepEqual(await loadAuth(api), {type:'unauthenticated'})
  assert.deepEqual(await loadAuth(api), {type:'authenticated',user:profile})
  assert.deepEqual(await loadAuth(api), {type:'unavailable'})
  assert.deepEqual(await loadAuth(api), {type:'unavailable'})
  const controller = new AbortController()
  mock.method(globalThis, 'fetch', async () => { throw new DOMException('aborted', 'AbortError') })
  await assert.rejects(loadAuth(api, controller.signal), {name:'AbortError'})
})

test('login uses credentialed POST with freshly bootstrapped CSRF', async () => {
  const fetch = responses({body:{csrfToken:'test-only-csrf'}}, {body:profile})
  const data = {email:profile.email,password:'obvious-test-only-password'}
  assert.deepEqual(await api.login(data), profile)
  const [bootstrap, login] = fetch.mock.calls.map((call) => call.arguments)
  assert.equal(bootstrap[0], 'http://localhost:8000/api/auth/csrf/')
  assert.equal(bootstrap[1].credentials, 'include')
  assert.equal(login[0], 'http://localhost:8000/api/auth/login/')
  assert.equal(login[1].method, 'POST')
  assert.equal(login[1].credentials, 'include')
  assert.equal(login[1].headers['X-CSRFToken'], 'test-only-csrf')
  assert.deepEqual(JSON.parse(login[1].body), data)
})

test('failed login preserves generic server feedback', async () => {
  responses({body:{csrfToken:'test-only'}}, {status:400,body:{detail:['Invalid email or password.']}})
  await assert.rejects(api.login({email:profile.email,password:'wrong-test-only'}), (error) => {
    assert.ok(error instanceof ApiError)
    assert.equal(error.status,400)
    assert.deepEqual(error.errors,{detail:['Invalid email or password.']})
    return true
  })
})

test('registration and logout refresh CSRF separately and use POST', async () => {
  const fetch = responses({body:{csrfToken:'before-test'}}, {status:201,body:profile},
                          {body:{csrfToken:'after-test'}}, {body:{detail:'Logged out.'}})
  assert.deepEqual(await api.register({base_currency:'USD'}), profile)
  assert.deepEqual(await api.logout(), {detail:'Logged out.'})
  const calls = fetch.mock.calls.map((call) => call.arguments)
  assert.ok(calls[1][0].endsWith('/register/'))
  assert.ok(calls[3][0].endsWith('/logout/'))
  assert.equal(calls[3][1].headers['X-CSRFToken'], 'after-test')
  assert.equal(calls[3][1].method, 'POST')
})

test('CSRF denial does not issue the state-changing request', async () => {
  const fetch = responses({status:403,body:{detail:'denied'}})
  await assert.rejects(api.logout(), {status:403})
  assert.equal(fetch.mock.callCount(), 1)
})

test('auth transitions discard profile after logout or backend loss', () => {
  assert.equal(initialAuthState.status,'checking')
  const signedIn = authReducer(initialAuthState, {type:'authenticated',user:profile})
  assert.equal(signedIn.user,profile)
  assert.deepEqual(authReducer(signedIn, {type:'unauthenticated'}), {status:'unauthenticated',user:null})
  assert.deepEqual(authReducer(signedIn, {type:'unavailable'}), {status:'unavailable',user:null})
})

test('auth does not write browser storage or read session cookies', async () => {
  const fail = () => { throw new Error('Browser auth persistence is forbidden') }
  const names = ['localStorage', 'sessionStorage', 'document']
  const originals = names.map((name) => Object.getOwnPropertyDescriptor(globalThis, name))
  for (const name of names) Object.defineProperty(globalThis, name, { configurable: true, get: fail })
  responses({body:profile}, {body:{csrfToken:'test-only'}}, {body:profile},
            {body:{csrfToken:'test-only'}}, {body:{detail:'Logged out.'}})
  try {
    await api.me()
    await api.login({email:profile.email,password:'test-only'})
    await api.logout()
  } finally {
    names.forEach((name, index) => {
      if (originals[index]) Object.defineProperty(globalThis, name, originals[index])
      else delete globalThis[name]
    })
  }
})

test('missing API config fails before sending credentials', async () => {
  const fetch = mock.method(globalThis, 'fetch', () => { throw new Error('should not fetch') })
  await assert.rejects(createAuthApi('').login({password:'test-only'}))
  assert.equal(fetch.mock.callCount(), 0)
})
