// Requires running localhost Django/Vite and Chrome. Uses an isolated profile.
// Creates one disposable test user; reports only its email, never cookies/tokens.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const chrome = process.env.CHROME_BIN || (process.platform === 'darwin'
  ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' : 'google-chrome')
const frontend = 'http://localhost:5173'
const profile = await mkdtemp(join(tmpdir(), 'kwp-auth-browser-'))
const child = spawn(chrome, ['--headless', '--disable-gpu', '--no-first-run',
  '--no-default-browser-check', '--disable-background-networking',
  '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'],
  { stdio: ['ignore', 'ignore', 'pipe'] })
let socket
try {
  const browserUrl = await new Promise((resolve, reject) => {
    let output = ''
    const timeout = setTimeout(() => reject(new Error('Chrome startup timed out')), 15000)
    child.once('error', (error) => { clearTimeout(timeout); reject(error) })
    child.stderr.on('data', (chunk) => {
      output += chunk
      const match = output.match(/DevTools listening on (ws:\/\/\S+)/)
      if (match) { clearTimeout(timeout); resolve(match[1]) }
    })
  })
  const origin = browserUrl.replace(/^ws:/, 'http:').split('/devtools/')[0]
  const pages = await (await fetch(`${origin}/json/list`)).json()
  socket = new WebSocket(pages.find((page) => page.type === 'page').webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject })
  let nextId = 0
  const pending = new Map()
  socket.onmessage = ({ data }) => {
    const message = JSON.parse(data)
    const entry = pending.get(message.id)
    if (!entry) return
    pending.delete(message.id)
    clearTimeout(entry.timer)
    if (message.error) entry.reject(new Error(message.error.message))
    else entry.resolve(message.result)
  }
  function call(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++nextId
      const timer = setTimeout(() => { pending.delete(id); reject(new Error(`${method} timed out`)) }, 15000)
      pending.set(id, {resolve, reject, timer})
      socket.send(JSON.stringify({id, method, params}))
    })
  }
  async function evaluate(expression) {
    const result = await call('Runtime.evaluate', {expression, awaitPromise:true, returnByValue:true})
    if (result.exceptionDetails) throw new Error('Browser assertion or evaluation failed')
    return result.result.value
  }
  async function waitFor(text) {
    for (let attempt = 0; attempt < 100; attempt++) {
      if (await evaluate(`document.body.innerText.includes(${JSON.stringify(text)})`)) return
      await new Promise((resolve) => setTimeout(resolve,100))
    }
    throw new Error(`UI did not reach: ${text}`)
  }
  async function click(text) {
    assert.equal(await evaluate(`(() => {
      const button = [...document.querySelectorAll('button')].find(b => b.textContent === ${JSON.stringify(text)});
      if (!button || button.disabled) return false; button.click(); return true;
    })()`), true)
  }
  async function submit(fields) {
    assert.equal(await evaluate(`(() => {
      const form = document.querySelector('form');
      for (const [name,value] of Object.entries(${JSON.stringify(fields)})) form.elements[name].value = value;
      if (!form.checkValidity()) return false;
      form.requestSubmit(); return true;
    })()`), true)
  }
  async function meStatus() {
    return evaluate(`fetch('http://localhost:8000/api/auth/me/', {credentials:'include'}).then(r => r.status)`)
  }
  await call('Page.enable')
  await call('Page.navigate', {url:frontend})
  await waitFor('Signed out')
  await waitFor('API status: Connected')
  assert.equal(await meStatus(),403)
  console.log('PASS: unauthenticated UI and public health')
  const email = `packet5-browser-${Date.now()}@example.com`
  const password = 'Packet5-obvious-test-only-password!42'
  await click('Create an account')
  await submit({email,password,password_confirmation:password,base_currency:'USD'})
  await waitFor('Registration successful')
  assert.equal(await meStatus(),403)
  console.log(`PASS: registration requires explicit currency and remains signed out; test user: ${email}`)
  await submit({email:email.toUpperCase(),password})
  await waitFor(`Signed in as ${email}`)
  assert.equal(await meStatus(),200)
  const user = await evaluate(`fetch('http://localhost:8000/api/auth/me/', {credentials:'include'}).then(r => r.json())`)
  assert.deepEqual(Object.keys(user).sort(), ['base_currency','email','id','timezone'])
  assert.equal(user.email,email)
  const cookies = (await call('Network.getCookies', {urls:['http://localhost:8000']})).cookies
  const sessionCookie = cookies.find((cookie) => cookie.name === 'sessionid')
  assert.ok(sessionCookie?.httpOnly)
  assert.equal(sessionCookie.sameSite,'Lax')
  assert.equal(await evaluate(`localStorage.length === 0 && sessionStorage.length === 0 && !document.cookie.includes('sessionid=')`),true)
  console.log('PASS: login, safe current profile, HttpOnly session and empty browser storage')
  await call('Page.reload')
  await waitFor(`Signed in as ${email}`)
  console.log('PASS: reload restores authenticated session')
  await click('Logout')
  await waitFor('Signed out')
  assert.equal(await meStatus(),403)
  console.log('PASS: logout clears authentication')
  await submit({email,password:'wrong-test-only-password'})
  await waitFor('Invalid email or password.')
  assert.equal(await evaluate(`[...document.querySelectorAll('input[type=password]')].every(i => i.value === '')`),true)
  await submit({email:'missing-packet5@example.com',password:'wrong-test-only-password'})
  await waitFor('Invalid email or password.')
  console.log('PASS: generic failed-login feedback and password clearing')
  await click('Create an account')
  await submit({email:email.toUpperCase(),password,password_confirmation:password,base_currency:'EUR'})
  await waitFor('An account with this email already exists.')
  console.log('PASS: case-insensitive duplicate registration')
  assert.equal(await evaluate(`fetch('http://localhost:8000/api/auth/login/', {method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:'{}'}).then(r => r.status)`),403)
  console.log('PASS: anonymous login without CSRF rejected')
  await call('Network.enable')
  await call('Network.setBlockedURLs', {urls:['http://localhost:8000/*']})
  await call('Page.reload')
  await waitFor('API unavailable.')
  assert.equal(await evaluate(`document.body.innerText.includes('Signed out')`),false)
  console.log('PASS: unavailable backend distinguished from unauthenticated state')
  await call('Network.setBlockedURLs', {urls:[]})
  await call('Page.reload')
  await waitFor('Signed out')
  await waitFor('API status: Connected')
  console.log('PASS: backend recovery; all browser scenarios passed')
} finally {
  socket?.close()
  child.kill('SIGTERM')
  await new Promise((resolve) => {
    if (child.exitCode !== null) return resolve()
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolve() },2000)
    child.once('exit', () => { clearTimeout(timer); resolve() })
  })
  await rm(profile, {recursive:true,force:true,maxRetries:3,retryDelay:200})
}
