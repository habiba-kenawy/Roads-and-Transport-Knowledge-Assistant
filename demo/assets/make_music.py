"""Generate demo/assets/music.mp3: an original, quiet ambient loop (soft pad + gentle plucks + echo), 48 s, seamless when looped.

Written for the demo video so there is no third-party licence to track: the audio is original and released as CC0 (public domain).
To use another track, just replace music.mp3 (the build trims or loops it to the video length).

Usage (needs numpy and ffmpeg on the PATH or via ../node_modules): python make_music.py
"""
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 78
BEAT = 60 / BPM
BAR = 4 * BEAT                       # 4 beats per chord
CHORDS = [                           # Cmaj7  Am7  Fmaj7  G6 : MIDI notes (root first)
    [48, 55, 59, 64],
    [45, 52, 55, 60],
    [41, 48, 52, 57],
    [43, 50, 55, 59],
]
CYCLES = 4                           # 4 chords x 4 cycles = 16 bars = about 49 s
TOTAL = BAR * len(CHORDS) * CYCLES
TAIL = 4.0                           # reverb/echo tail that is folded back onto the start so the loop has no seam


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def envelope(n: int, attack: float, release: float) -> np.ndarray:
    t = np.arange(n) / SR
    env = np.minimum(1.0, t / attack) * np.minimum(1.0, (n / SR - t) / release)
    return env ** 1.5


def pad(notes: list[int], seconds: float) -> np.ndarray:
    """A slow, soft chord: each note is two slightly detuned triangle-ish waves."""
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = np.zeros((2, n))
    for i, midi in enumerate(notes):
        for side, detune in ((0, 0.997), (1, 1.003)):
            f = hz(midi) * detune
            wave_ = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t) + 0.12 * np.sin(2 * np.pi * 3 * f * t)
            out[side] += wave_ * (0.55 if i == 0 else 0.4)
    return out * envelope(n, 1.6, 1.8)


def pluck(midi: int, seconds: float = 1.4) -> np.ndarray:
    n = int(seconds * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    tone = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t) + 0.1 * np.sin(2 * np.pi * 3 * f * t)
    return tone * np.exp(-t * 3.2) * np.minimum(1.0, t / 0.008)


def render() -> np.ndarray:
    length = int((TOTAL + TAIL) * SR)
    mix = np.zeros((2, length))
    for bar_index in range(len(CHORDS) * CYCLES):
        chord = CHORDS[bar_index % len(CHORDS)]
        start = int(bar_index * BAR * SR)
        p = pad(chord, BAR + 1.2)                                  # overlaps the next chord a little
        end = min(length, start + p.shape[1])
        mix[:, start:end] += p[:, : end - start] * 0.55
        # gentle eighth-note arpeggio: a different pattern each cycle keeps it from sounding mechanical
        pattern = [(0, 2), (1, 2), (2, 2), (3, 2), (2, 2), (1, 2), (3, 2), (2, 2)] if (bar_index // len(CHORDS)) % 2 == 0 else [(3, 2), (2, 2), (1, 2), (2, 2), (3, 2), (1, 2), (2, 2), (0, 2)]
        for step, (idx, octave) in enumerate(pattern):
            if step % 2 == 1 and bar_index % 2 == 0:
                continue                                            # leave air every other bar
            note = chord[idx] + 12 * octave - 12
            at = start + int(step * BEAT / 2 * SR)
            pl = pluck(note) * 0.20
            end = min(length, at + len(pl))
            pan = 0.35 + 0.3 * ((step * 3 + bar_index) % 5) / 4
            mix[0, at:end] += pl[: end - at] * (1 - pan)
            mix[1, at:end] += pl[: end - at] * pan
    # soft stereo echo (feedback delay) for space
    delay = int(BEAT * 0.75 * SR)
    for channel, shift in ((0, delay), (1, int(delay * 1.33))):
        out = mix[channel].copy()
        for k in range(1, 5):
            offset = shift * k
            out[offset:] += mix[channel][: length - offset] * (0.38 ** k)
        mix[channel] = out
    # one-pole low-pass: takes the edge off the bright partials
    alpha = 0.18
    for channel in (0, 1):
        y = np.zeros(length)
        acc = 0.0
        x = mix[channel]
        for i in range(length):
            acc += alpha * (x[i] - acc)
            y[i] = acc
        mix[channel] = y
    # fold the tail onto the start so the end flows into the beginning when looped
    loop = mix[:, : int(TOTAL * SR)].copy()
    tail = mix[:, int(TOTAL * SR):]
    loop[:, : tail.shape[1]] += tail
    loop /= np.max(np.abs(loop)) * 1.05
    return loop


def main() -> None:
    here = Path(__file__).parent
    wav_path, mp3_path = here / "music_raw.wav", here / "music.mp3"
    data = (render().T * 32767).astype(np.int16)
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    ffmpeg = subprocess.run(["node", "-e", "import('@ffmpeg-installer/ffmpeg').then(m => console.log(m.default.path))"], cwd=here.parent, capture_output=True, text=True).stdout.strip() or "ffmpeg"
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(wav_path), "-c:a", "libmp3lame", "-q:a", "3", str(mp3_path)], check=True)
    wav_path.unlink()
    print(f"wrote {mp3_path} ({mp3_path.stat().st_size // 1024} KB, {TOTAL:.1f} s)")


if __name__ == "__main__":
    main()
