// Turns work/recording.webm into output/demo.mp4 (1280x720, 30 fps, H.264 + AAC) and writes output/demo.srt from captions.json.
//  - captions are burned into the bottom strip with ffmpeg's subtitle renderer (Roboto Medium from assets/fonts)
//  - the music (assets/music.mp3) is looped or trimmed to the video length, levelled to about -18 LUFS, faded in over 2 s and out over the last 3 s
import { execFileSync, spawnSync } from 'node:child_process'
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import ffmpegInstaller from '@ffmpeg-installer/ffmpeg'

const FADE_IN = 2
const FADE_OUT = 3
const TAIL = 0.8 // seconds of picture after the last caption ends

const captions = JSON.parse(readFileSync('captions.json', 'utf-8'))
const { lead: fallbackLead } = JSON.parse(readFileSync('work/timing.json', 'utf-8'))
const duration = Math.max(...captions.map((c) => c.end)) + TAIL

// ---- where the timeline starts in the recording: the moment the black sync square (top-left corner) disappears
function findTimelineStart() {
  const run = spawnSync(ffmpegInstaller.path, ['-hide_banner', '-i', 'work/recording.webm', '-vf', 'crop=30:30:10:10,scale=1:1,showinfo', '-f', 'null', '-'], { encoding: 'utf-8', maxBuffer: 1 << 28 })
  const frames = [...run.stderr.matchAll(/pts_time:([\d.]+).*?mean:\[(\d+) /g)].map((m) => ({ time: Number(m[1]), luma: Number(m[2]) }))
  const first = frames.findIndex((f) => f.luma < 60) // marker on
  const gone = first < 0 ? undefined : frames.slice(first).find((f) => f.luma >= 60) // marker off again
  return gone?.time
}
const markerEnd = findTimelineStart()
const lead = markerEnd ?? fallbackLead
console.log(markerEnd === undefined ? `Sync marker not found: using the estimate ${fallbackLead.toFixed(2)} s` : `Sync marker found: the timeline starts ${markerEnd.toFixed(2)} s into the recording (estimate was ${fallbackLead.toFixed(2)} s)`)

// ---- the .srt (the same captions that are burned in)
const stamp = (seconds) => {
  const ms = Math.round(seconds * 1000)
  const pad = (n, width = 2) => String(n).padStart(width, '0')
  return `${pad(Math.floor(ms / 3600000))}:${pad(Math.floor(ms / 60000) % 60)}:${pad(Math.floor(ms / 1000) % 60)},${pad(ms % 1000, 3)}`
}
const srt = captions.map((c, i) => `${i + 1}\n${stamp(c.start)} --> ${stamp(c.end)}\n${c.text}\n`).join('\n')
mkdirSync('output', { recursive: true })
writeFileSync('output/demo.srt', srt)
console.log(`Wrote output/demo.srt (${captions.length} captions)`)

// ---- ffmpeg (run inside work/ so the subtitle and font paths stay simple on every platform)
mkdirSync('work/fonts', { recursive: true })
copyFileSync('output/demo.srt', 'work/captions.srt')
copyFileSync('assets/fonts/Roboto-Medium.ttf', 'work/fonts/Roboto-Medium.ttf')

// Subtitle sizes are in the renderer's own units: an SRT file is laid out on a 384x288 canvas that is then scaled to the video,
// so on 1280x720 one unit is 2.5 px. FontSize 12 is about 30 px; margins and outline follow the same scale.
const style = [
  'FontName=Roboto Medium', 'FontSize=12', 'PrimaryColour=&H00FFFFFF', 'OutlineColour=&H00201008', 'BorderStyle=1',
  'Outline=0.8', 'Shadow=0', 'Alignment=2', 'MarginV=9', 'MarginL=24', 'MarginR=24',
].join(',')
const video = `[0:v]fps=30,scale=1280:720:flags=lanczos,subtitles=captions.srt:fontsdir=fonts:original_size=1280x720:force_style='${style}',format=yuv420p[v]`
const audio = `[1:a]atrim=0:${duration},asetpts=N/SR/TB,loudnorm=I=-18:LRA=7:TP=-2,afade=t=in:st=0:d=${FADE_IN},afade=t=out:st=${(duration - FADE_OUT).toFixed(3)}:d=${FADE_OUT}[a]`

const args = [
  '-y', '-hide_banner', '-loglevel', 'error',
  '-ss', lead.toFixed(3), '-i', 'recording.webm',
  '-stream_loop', '-1', '-i', '../assets/music.mp3',
  '-filter_complex', `${video};${audio}`,
  '-map', '[v]', '-map', '[a]', '-t', duration.toFixed(3),
  '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-r', '30', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
  '-c:a', 'aac', '-b:a', '160k', '-ar', '44100',
  '../output/demo.mp4',
]
execFileSync(ffmpegInstaller.path, args, { cwd: 'work', stdio: 'inherit' })
console.log(`Wrote output/demo.mp4 (${duration.toFixed(1)} s)`)
