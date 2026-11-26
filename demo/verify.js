// Checks output/demo.mp4 against the brief with ffprobe/ffmpeg and pulls frames (work/frames/) for a visual check of the captions.
import { execFileSync, spawnSync } from 'node:child_process'
import { mkdirSync, readFileSync, rmSync } from 'node:fs'
import ffmpegInstaller from '@ffmpeg-installer/ffmpeg'
import ffprobeInstaller from '@ffprobe-installer/ffprobe'

const FILE = 'output/demo.mp4'
const captions = JSON.parse(readFileSync('captions.json', 'utf-8'))
const probe = JSON.parse(execFileSync(ffprobeInstaller.path, ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', FILE]).toString())
const video = probe.streams.find((s) => s.codec_type === 'video')
const audio = probe.streams.find((s) => s.codec_type === 'audio')
const duration = Number(probe.format.duration)
const [num, den] = video.avg_frame_rate.split('/').map(Number)
const fps = num / den

const meanVolume = (start, length) => {
  const run = spawnSync(ffmpegInstaller.path, ['-hide_banner', '-ss', String(start), '-t', String(length), '-i', FILE, '-vn', '-af', 'volumedetect', '-f', 'null', '-'], { encoding: 'utf-8' })
  const m = /mean_volume: (-?[\d.]+) dB/.exec(run.stderr)
  return m ? Number(m[1]) : NaN
}
const loudness = () => {
  const run = spawnSync(ffmpegInstaller.path, ['-hide_banner', '-i', FILE, '-vn', '-af', 'ebur128', '-f', 'null', '-'], { encoding: 'utf-8' })
  const m = [...run.stderr.matchAll(/I:\s+(-?[\d.]+) LUFS/g)].at(-1)
  return m ? Number(m[1]) : NaN
}

const checks = [
  ['resolution 1280x720', video.width === 1280 && video.height === 720, `${video.width}x${video.height}`],
  ['30 fps', Math.abs(fps - 30) < 0.01, `${fps.toFixed(2)} fps`],
  ['video H.264', video.codec_name === 'h264', video.codec_name],
  ['audio AAC present', audio?.codec_name === 'aac', audio ? `${audio.codec_name}, ${audio.channels} ch, ${audio.sample_rate} Hz` : 'no audio stream'],
  ['container MP4', probe.format.format_name.includes('mp4'), probe.format.format_name],
  ['duration 120 s or less', duration <= 120, `${duration.toFixed(1)} s`],
  ['duration near 1:50 (100-120 s)', duration >= 100 && duration <= 120, `${duration.toFixed(1)} s`],
]
const total = loudness()
const intro = meanVolume(0, 1)
const middle = meanVolume(50, 10)
const outro = meanVolume(duration - 1.2, 1.0)
checks.push(['music is quiet (integrated loudness between -24 and -14 LUFS)', total <= -14 && total >= -24, `${total} LUFS`])
checks.push(['fades in (first second quieter than the middle)', intro < middle - 3, `first second ${intro} dB, middle ${middle} dB`])
checks.push(['fades out (last second quieter than the middle)', outro < middle - 6, `last second ${outro} dB, middle ${middle} dB`])

let failed = 0
for (const [name, ok, detail] of checks) {
  if (!ok) failed++
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}: ${detail}`)
}

// frames in the middle of every caption, for a look at readability and cut-off text
rmSync('work/frames', { recursive: true, force: true })
mkdirSync('work/frames', { recursive: true })
captions.forEach((c, i) => {
  const t = ((c.start + c.end) / 2).toFixed(2)
  execFileSync(ffmpegInstaller.path, ['-y', '-loglevel', 'error', '-ss', t, '-i', FILE, '-frames:v', '1', `work/frames/caption_${String(i + 1).padStart(2, '0')}.png`])
})
console.log(`Extracted ${captions.length} frames to work/frames/`)
if (failed) {
  console.error(`${failed} check(s) failed`)
  process.exit(1)
}
