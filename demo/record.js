// Records the demo with Playwright: drives the REAL React page (real clicks, real typing) at 1280x720, replays real backend answers
// from fixtures/responses.json, and follows the timeline in captions.json so the on-screen captions match what happens.
// Output: work/recording.webm and work/timing.json (how much to trim from the start).
import { mkdirSync, readFileSync, rmSync, writeFileSync, renameSync } from 'node:fs'
import { chromium } from 'playwright'

import { API, APP, QUESTIONS as Q, searchKey, sleep } from './flow.js'

const WIDTH = 1280
const HEIGHT = 720
const BAND = 100 // the strip at the bottom that the captions are burned into (ffmpeg draws the text; the page only leaves the room)

const fixtures = JSON.parse(readFileSync(new URL('./fixtures/responses.json', import.meta.url), 'utf-8'))
rmSync('work/video', { recursive: true, force: true })
mkdirSync('work/video', { recursive: true })

// ---------------------------------------------------------------------------------------------------------------- the page
const browser = await chromium.launch({ headless: true, args: ['--force-device-scale-factor=1'] })
const context = await browser.newContext({
  viewport: { width: WIDTH, height: HEIGHT },
  deviceScaleFactor: 1,
  recordVideo: { dir: 'work/video', size: { width: WIDTH, height: HEIGHT } },
})

// Cursor highlight, click ring and the empty caption strip, added to every page load.
await context.addInitScript(`(() => {
  const BAND = ${BAND}
  const start = () => {
    const css = document.createElement('style')
    css.textContent = '.h-dvh { height: calc(100dvh - ' + BAND + 'px) !important; }' +
      '#demo-band { position: fixed; left: 0; right: 0; bottom: 0; height: ' + BAND + 'px; background: #0b1b3a; border-top: 3px solid #0536a8; z-index: 2147483000; }' +
      '#demo-cursor { position: fixed; left: 0; top: 0; z-index: 2147483600; pointer-events: none; transform: translate(-100px, -100px); filter: drop-shadow(0 2px 3px rgba(0,0,0,.35)); }' +
      '#demo-ring { position: fixed; left: 0; top: 0; z-index: 2147483500; pointer-events: none; width: 44px; height: 44px; margin: -22px 0 0 -22px; border: 4px solid #e11d48; border-radius: 50%; opacity: 0; }'
    document.head.append(css)
    const band = document.createElement('div'); band.id = 'demo-band'; document.body.append(band)
    const cursor = document.createElement('div'); cursor.id = 'demo-cursor'
    cursor.innerHTML = '<svg width="30" height="30" viewBox="0 0 24 24"><path d="M3 2l7.5 19 2.6-7.7L21 10.8z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>'
    document.body.append(cursor)
    const ring = document.createElement('div'); ring.id = 'demo-ring'; document.body.append(ring)
    document.addEventListener('mousemove', (e) => { cursor.style.transform = 'translate(' + e.clientX + 'px,' + e.clientY + 'px)' }, true)
    document.addEventListener('mousedown', (e) => {
      ring.style.left = e.clientX + 'px'; ring.style.top = e.clientY + 'px'
      ring.animate([{ opacity: 0.95, transform: 'scale(0.5)' }, { opacity: 0, transform: 'scale(1.7)' }], { duration: 520, easing: 'ease-out' })
    }, true)
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start()
})()`)

const page = await context.newPage()
const pageCreated = performance.now()

// ---------------------------------------------------------------------------------------------------------------- the backend (replayed)
let delay = 1500 // how long the next answer "takes": long enough for the loading card to be seen
const corsHeaders = { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': 'GET,POST,OPTIONS' }

function recorded(pathname, body) {
  if (pathname === '/chat') return fixtures.chat[body.message]
  if (pathname === '/chat/resume') return fixtures.resume[body.message]
  if (pathname === '/search') return fixtures.search[searchKey(body.query, body.mode, body.filters?.year, body.filters?.doc_type)]
  return undefined
}

await page.route(`${API}/**`, async (route) => {
  const request = route.request()
  if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: corsHeaders })
  const answer = recorded(new URL(request.url()).pathname, request.postDataJSON())
  if (!answer) {
    console.error(`No recorded answer for ${request.method()} ${request.url()} ${request.postData()}`)
    return route.fulfill({ status: 500, headers: corsHeaders, contentType: 'application/json', body: '{"detail":"no recorded answer"}' })
  }
  await sleep(delay)
  return route.fulfill({ status: 200, headers: corsHeaders, contentType: 'application/json', body: JSON.stringify(answer) })
})

await page.goto(APP)
await page.getByRole('heading', { name: 'What would you like to know?' }).waitFor()
await sleep(600)
await page.mouse.move(640, 330)

// A black square in the corner for 0.45 s, removed exactly when the timeline starts. Playwright's video starts a little after the page
// is created, so the build finds the moment the square disappears in the video and trims there: that is where the captions begin.
await page.evaluate(() => {
  const marker = document.createElement('div')
  marker.id = 'demo-sync'
  Object.assign(marker.style, { position: 'fixed', left: '0', top: '0', width: '80px', height: '80px', background: '#000', zIndex: '2147483647' })
  document.body.append(marker)
})
await sleep(450)
await page.evaluate(() => document.getElementById('demo-sync')?.remove())

// ---------------------------------------------------------------------------------------------------------------- the clock and the helpers
const T0 = performance.now()
const lead = (T0 - pageCreated) / 1000 // only a fallback now: the build trims at the sync marker instead
const late = []
async function at(t, label = '') {
  const wait = t * 1000 - (performance.now() - T0)
  if (wait > 0) await sleep(wait)
  else if (wait < -400) late.push(`${label} ${(-wait / 1000).toFixed(2)} s late (wanted ${t})`)
}

let cursor = { x: 640, y: 330 }
// Moves in a smooth curve and takes exactly `ms`, however long each mouse event takes (the pace follows the clock, not a step count).
async function glide(x, y, ms = 520) {
  const from = cursor
  const began = performance.now()
  for (let elapsed = 0; elapsed < ms; elapsed = performance.now() - began) {
    const f = elapsed / ms
    const e = f * f * (3 - 2 * f) // ease in and out
    await page.mouse.move(from.x + (x - from.x) * e, from.y + (y - from.y) * e)
    await sleep(8)
  }
  await page.mouse.move(x, y)
  cursor = { x, y }
}
async function centre(locator) {
  await locator.scrollIntoViewIfNeeded()
  const box = await locator.boundingBox()
  if (!box) throw new Error('element has no box')
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 }
}
/** Move the cursor to the element so that the click lands at time t. */
async function clickAt(t, locator, label) {
  await at(t - 0.62, `${label} (move)`)
  const p = await centre(locator)
  await glide(p.x, p.y)
  await at(t, label)
  await page.mouse.down()
  await sleep(70)
  await page.mouse.up()
}
async function hoverAt(t, locator, label) {
  await at(t - 0.5, `${label} (move)`)
  const p = await centre(locator)
  await glide(p.x, p.y, 450)
}
// Types key by key so that the last character lands at `end`: each key has its own slot on the clock.
async function typeAt(t, end, text, label) {
  await at(t, label)
  const slot = ((end - t) * 1000) / text.length
  const began = performance.now()
  for (const [i, char] of [...text].entries()) {
    await page.keyboard.type(char)
    const wait = began + (i + 1) * slot - performance.now()
    if (wait > 0) await sleep(wait)
  }
}
async function pressAt(t, key, label) {
  await at(t, label)
  await page.keyboard.press(key)
}

const textbox = page.locator('textarea')
const ask = page.locator('form button[type="submit"]')
const newConversation = page.locator('aside').getByRole('button', { name: 'New conversation' })
const option = (name) => page.getByRole('option', { name })

// ---------------------------------------------------------------------------------------------------------------- the flow
// 1. start screen and the options
await at(0.4)
await clickAt(4.6, page.locator('button[aria-label="Search mode"]'), 'mode chip')
await hoverAt(5.7, option(/Lexical/), 'lexical option')
await hoverAt(6.3, option(/Semantic/), 'semantic option')
await pressAt(7.0, 'Escape', 'close mode')
await clickAt(7.5, page.locator('button[aria-label="Year"]'), 'year chip')
await hoverAt(8.6, option('2022'), 'year option')
await pressAt(9.5, 'Escape', 'close year')

// 2. ask an example question
await clickAt(10.9, page.getByRole('button', { name: /Airport departure fee/ }), 'example card')
delay = 2200
await clickAt(14.2, ask, 'ask')

// 3. sources
await clickAt(24.5, page.locator('main article p button').first(), 'source marker')
await pressAt(33.8, 'Escape', 'close drawer')

// 4. follow-up
await clickAt(35.0, textbox, 'message box')
await typeAt(35.4, 36.9, Q.followUp, 'type follow-up')
delay = 2000
await pressAt(37.2, 'Enter', 'send follow-up')

// 5. clarification
await clickAt(44.0, newConversation, 'new conversation')
await typeAt(44.7, 45.9, Q.vague, 'type vague question')
delay = 1500
await pressAt(46.1, 'Enter', 'send vague question')
await clickAt(53.7, page.locator('#clarification-answer'), 'answer box')
await typeAt(54.1, 56.5, Q.vagueReply, 'type reply')
delay = 1600
await clickAt(57.2, page.locator('main article button[type="submit"]'), 'answer button')

// 6. limits
await clickAt(63.0, newConversation, 'new conversation')
await typeAt(63.6, 65.6, Q.recipe, 'type recipe')
delay = 1000
await pressAt(65.9, 'Enter', 'send recipe')
await clickAt(68.6, newConversation, 'new conversation')
await typeAt(69.2, 71.7, Q.camel, 'type camel')
delay = 1400
await pressAt(72.0, 'Enter', 'send camel')

// 7. history
await clickAt(76.4, page.locator('nav[aria-label="Past conversations"] button', { hasText: 'How much is the departure' }), 'history row')
await clickAt(81.0, page.locator('nav[aria-label="Past conversations"] button[aria-label^="Delete conversation: What is a good recipe"]'), 'delete')
await clickAt(82.9, page.locator('[data-sonner-toast] button', { hasText: 'Undo' }), 'undo')

// 8. Search Inspector
await clickAt(85.7, page.locator('nav[aria-label="Pages"]').getByRole('button', { name: 'Search Inspector' }), 'inspector page')
await clickAt(86.3, textbox, 'search box')
await typeAt(86.7, 87.9, Q.search, 'type search')
delay = 1100
await pressAt(88.2, 'Enter', 'search')
await at(92.4, 'scroll')
for (let i = 0; i < 6; i++) { await page.mouse.wheel(0, 90); await sleep(130) }
await at(95.6, 'scroll back')
await page.evaluate(() => document.querySelector('main > div')?.scrollTo({ top: 0, behavior: 'smooth' }))
await clickAt(96.8, page.locator('button[aria-label="Search mode"]'), 'mode chip')
await clickAt(97.9, option(/Lexical/), 'lexical option')
delay = 1000
await clickAt(98.6, ask, 'search again')
await clickAt(101.9, page.locator('button[aria-label="Year"]'), 'year chip')
await clickAt(102.8, option('2026'), 'year 2026')
await clickAt(103.4, page.locator('button[aria-label="Document type"]'), 'type chip')
await clickAt(104.2, option('Law'), 'type Law')
await clickAt(104.9, ask, 'search with filters')

// 9. About
await clickAt(109.6, page.locator('aside nav[aria-label="Information"]').getByRole('button', { name: 'About' }), 'about page')
await at(115.0, 'end')

// ---------------------------------------------------------------------------------------------------------------- finish
const video = page.video()
await context.close() // the video file is finalised when the context closes
await browser.close()
renameSync(await video.path(), 'work/recording.webm')
writeFileSync('work/timing.json', JSON.stringify({ lead, timelineSeconds: (performance.now() - T0) / 1000 }, null, 2))
console.log(`Recorded work/recording.webm (lead ${lead.toFixed(2)} s, timeline ${((performance.now() - T0) / 1000).toFixed(1)} s)`)
if (late.length) console.log('Steps that ran late:\n  ' + late.join('\n  '))
