// npm run demo: make sure the page (and, if the answers are not recorded yet, the API) is running, then record, build and verify.
import { execFileSync, spawn, spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { API, APP, isUp, sleep } from './flow.js'

const here = fileURLToPath(new URL('.', import.meta.url))
const repo = fileURLToPath(new URL('..', import.meta.url))
const started = []

async function ensure(name, url, command, args, cwd, env = {}) {
  if (await isUp(url)) {
    console.log(`${name} is already running at ${url}`)
    return
  }
  console.log(`Starting ${name}...`)
  const child = spawn(command, args, { cwd, env: { ...process.env, ...env }, stdio: 'ignore', shell: process.platform === 'win32' && command === 'npm' })
  started.push(child)
  for (let i = 0; i < 90; i++) {
    if (await isUp(url)) return console.log(`${name} is up`)
    await sleep(1000)
  }
  throw new Error(`${name} did not start at ${url}`)
}

// A started server is a shell plus the real process under it: on Windows killing only the shell would leave the server running.
function stop(child) {
  if (process.platform === 'win32') spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' })
  else child.kill()
}

const pythonCandidates = [`${repo}.venv/Scripts/python.exe`, `${repo}.venv/bin/python`]
const python = pythonCandidates.find(existsSync) ?? 'python'
const step = (script) => execFileSync(process.execPath, [script], { cwd: here, stdio: 'inherit' })

try {
  await ensure('the frontend', APP, 'npm', ['run', 'dev'], `${repo}frontend`, { VITE_API_BASE_URL: API })
  if (!existsSync(`${here}fixtures/responses.json`)) {
    console.log('No recorded answers yet: capturing them from the real backend (real model calls).')
    await ensure('the API', `${API}/health`, python, ['-m', 'uvicorn', 'app.api.main:app', '--port', new URL(API).port || '8010'], repo)
    step('capture-fixtures.js')
  }
  step('record.js')
  step('build.js')
  step('verify.js')
  console.log('\nDone: demo/output/demo.mp4 and demo/output/demo.srt')
} finally {
  for (const child of started) stop(child)
}
