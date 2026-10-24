"""Генерирует звуки пака в WAV (44.1 кГц, 16 бит, моно). Без зависимостей.

Запуск:  python generate_audio.py [имя ...]
Результат в audio/<имя>.wav.
"""
import math
import os
import struct
import sys
import wave

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio")
RATE = 44100


def save_wav(path, samples):
    """samples: список float в -1..1."""
    peak = max(1e-6, max(abs(s) for s in samples))
    scale = 0.9 / peak if peak > 0.9 else 1.0
    data = struct.pack(f"<{len(samples)}h", *(int(max(-1.0, min(1.0, s * scale)) * 32767) for s in samples))
    with wave.open(path, "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(RATE)
        fh.writeframes(data)


def tone(freq, seconds, decay, amp=1.0, attack=0.004):
    """Синус с экспоненциальным спадом; attack — короткий линейный вход против щелчка."""
    n = int(RATE * seconds)
    out = []
    for i in range(n):
        t = i / RATE
        env = math.exp(-t * decay) * min(1.0, t / attack)
        out.append(amp * env * math.sin(2 * math.pi * freq * t))
    return out


def add(*layers):
    n = max(len(l) for l in layers)
    return [sum(l[i] if i < len(l) else 0.0 for l in layers) for i in range(n)]


# ---------------------------------------------------------------- звуки

def ticket_pickup():
    """«Дзынь» 0.2 с: 1200 Гц + обертон 2400 + лёгкий третий, быстрый спад."""
    return add(
        tone(1200, 0.2, 18, 1.0),
        tone(2400, 0.2, 26, 0.35),
        tone(3600, 0.12, 40, 0.12),
    )


def noise_burst(seconds, rise, cutoff_from, cutoff_to, rng, amp=1.0):
    """Шум с огибающей «подъём–спад» и однополюсным ФНЧ, частота среза скользит от cutoff_from к cutoff_to."""
    n = int(RATE * seconds)
    out, y = [], 0.0
    for i in range(n):
        t = i / RATE
        env = (t / rise) if t < rise else max(0.0, 1 - (t - rise) / (seconds - rise))
        cutoff = cutoff_from + (cutoff_to - cutoff_from) * (i / n)
        k = 1 - math.exp(-2 * math.pi * cutoff / RATE)
        y += k * (rng.uniform(-1, 1) - y)
        out.append(amp * env * y)
    return out


def square(freq, seconds, amp=1.0, decay=3.0, detune_cents=0.0):
    """Мягкая квадратная волна (первые 7 нечётных гармоник) с расстройкой в центах и спадом."""
    f = freq * 2 ** (detune_cents / 1200)
    n = int(RATE * seconds)
    out = []
    for i in range(n):
        t = i / RATE
        v = sum(math.sin(2 * math.pi * f * k * t) / k for k in (1, 3, 5, 7, 9, 11, 13))
        env = math.exp(-t * decay) * min(1.0, t / 0.005)
        out.append(amp * env * v * 0.5)
    return out


def place(track, clip, start_seconds):
    start = int(RATE * start_seconds)
    end = start + len(clip)
    if end > len(track):
        track.extend([0.0] * (end - len(track)))
    for i, v in enumerate(clip):
        track[start + i] += v
    return track


def sweep():
    """«Вжух» 0.4 с: шум, фильтр открывается и закрывается."""
    import random
    return noise_burst(0.4, 0.12, 300, 2500, random.Random("sweep"))


def finish():
    """Три восходящие ноты C5–E5–G5 и финальный аккорд, 1 с."""
    track = []
    for i, f in enumerate((523.25, 659.25, 783.99)):
        place(track, tone(f, 0.25, 6, 0.8), 0.18 * i)
    for f in (523.25, 659.25, 783.99, 1046.5):
        place(track, tone(f, 0.5, 4, 0.4), 0.55)
    return track[: int(RATE * 1.0)]


def cart_rumble():
    """Низкий гул 2 с под луп: сумма тонов 60–120 Гц с дрожанием + фильтрованный шум; края сведены."""
    import random
    rng = random.Random("rumble")
    n = int(RATE * 2.0)
    out = []
    phases = [rng.uniform(0, 6.28) for _ in range(4)]
    for i in range(n):
        t = i / RATE
        v = 0.0
        for k, f in enumerate((60, 75, 95, 120)):
            v += math.sin(2 * math.pi * f * t + phases[k] + 0.4 * math.sin(2 * math.pi * 0.7 * t * (k + 1)))
        out.append(v / 4)
    low = noise_burst(2.0, 1.0, 150, 150, rng, amp=0.5)
    out = [a + b for a, b in zip(out, low)]
    fade = int(RATE * 0.05)
    for i in range(fade):
        g = i / fade
        out[i] *= g
        out[-1 - i] *= g
    return out


def carousel_music():
    """Расстроенная шарманка, 8 с луп при 120 BPM: мелодия двумя голосами с детюном ±15 центов, бас на долях."""
    beat = 0.5
    melody = [523.25, 659.25, 783.99, 659.25, 523.25, 587.33, 698.46, 587.33,
              523.25, 659.25, 783.99, 1046.5, 783.99, 698.46, 659.25, 587.33]
    bass = [261.63, 196.0, 261.63, 196.0, 174.61, 196.0, 261.63, 196.0] * 2
    track = [0.0] * int(RATE * 8.0)
    for i, f in enumerate(melody):
        place(track, square(f, beat * 0.9, 0.35, decay=2.5, detune_cents=15), i * beat)
        place(track, square(f, beat * 0.9, 0.35, decay=2.5, detune_cents=-15), i * beat)
    for i, f in enumerate(bass):
        place(track, square(f / 2, beat * 0.8, 0.3, decay=4), i * beat)
    return track[: int(RATE * 8.0)]


def creak():
    """Скрип ржавого металла 1.2 с: пилообразный тон скользит 210→90 Гц с дрожанием и треском шума, в конце удар."""
    import random
    rng = random.Random("creak")
    n = int(RATE * 1.2)
    out, phase = [], 0.0
    for i in range(n):
        t = i / RATE
        f = 210 - 120 * (t / 1.2) + 12 * math.sin(2 * math.pi * 23 * t)
        phase += f / RATE
        saw = 2 * (phase % 1.0) - 1
        env = min(1.0, t / 0.05) * (0.6 + 0.4 * math.sin(2 * math.pi * 7 * t) ** 2)
        out.append(0.5 * env * saw + 0.15 * env * (rng.random() * 2 - 1))
    return place(out, noise_burst(0.3, 0.01, 2000, 200, rng, amp=0.9), 0.9)


SOUNDS = {
    "ticket_pickup": ticket_pickup,
    "sweep": sweep,
    "finish": finish,
    "cart_rumble": cart_rumble,
    "carousel_music": carousel_music,
    "creak": creak,
}


def main(names):
    os.makedirs(OUT_DIR, exist_ok=True)
    for name in names or SOUNDS:
        if name not in SOUNDS:
            sys.exit(f"нет звука {name!r}; есть: {', '.join(SOUNDS)}")
        samples = SOUNDS[name]()
        path = os.path.join(OUT_DIR, f"{name}.wav")
        save_wav(path, samples)
        print(f"{name}.wav: {len(samples) / RATE:.2f} s, {os.path.getsize(path)} bytes")


if __name__ == "__main__":
    main(sys.argv[1:])
