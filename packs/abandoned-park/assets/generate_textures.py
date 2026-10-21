"""Генерирует текстуры пака в PNG. Без зависимостей (PNG пишется через zlib).

Запуск:  python generate_textures.py [имя ...]
Результат в textures/<имя>.png, 512×512 RGB. Сид фиксирован — перегенерация даёт тот же файл.
"""
import os
import random
import struct
import sys
import zlib

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "textures")
SIZE = 512


def save_png(path, pixels, size=SIZE):
    """pixels: список строк, строка — список (r, g, b)."""
    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for r, g, b in row:
            raw.extend((_clamp(r), _clamp(g), _clamp(b)))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
        fh.write(chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)))
        fh.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        fh.write(chunk(b"IEND", b""))


def _clamp(v):
    return max(0, min(255, int(v)))


def value_noise(rng, size, cells):
    """Плавный шум 0..1: случайная сетка cells×cells, билинейно растянутая до size."""
    grid = [[rng.random() for _ in range(cells + 1)] for _ in range(cells + 1)]
    out = []
    step = size / cells
    for y in range(size):
        gy = y / step
        y0 = int(gy)
        fy = gy - y0
        row = []
        for x in range(size):
            gx = x / step
            x0 = int(gx)
            fx = gx - x0
            a = grid[y0][x0] * (1 - fx) + grid[y0][x0 + 1] * fx
            b = grid[y0 + 1][x0] * (1 - fx) + grid[y0 + 1][x0 + 1] * fx
            row.append(a * (1 - fy) + b * fy)
        out.append(row)
    return out


def fbm(rng, size, octaves=(4, 8, 16, 32)):
    """Сумма шумов разного масштаба, нормирована в 0..1."""
    layers = [value_noise(rng, size, c) for c in octaves]
    weights = [1 / (i + 1) for i in range(len(octaves))]
    total = sum(weights)
    return [[sum(layers[k][y][x] * weights[k] for k in range(len(layers))) / total
             for x in range(size)] for y in range(size)]


def mix(c0, c1, t):
    return tuple(c0[i] + (c1[i] - c0[i]) * t for i in range(3))


def drips(rng, size, count, color_map, strength):
    """Вертикальные потёки ржавчины: тёмные линии вниз от случайной точки."""
    for _ in range(count):
        x = rng.randrange(size)
        y0 = rng.randrange(size // 2)
        length = rng.randrange(size // 8, size // 2)
        width = rng.choice((1, 2, 3))
        for y in range(y0, min(size, y0 + length)):
            fade = 1 - (y - y0) / length
            for dx in range(-width, width + 1):
                xx = (x + dx) % size
                r, g, b = color_map[y][xx]
                color_map[y][xx] = mix((r, g, b), (60, 30, 10), strength * fade * (1 - abs(dx) / (width + 1)))


# ---------------------------------------------------------------- текстуры

def rust_booth(rng):
    """Выцветшие красно-белые полосы киоска с ржавыми пятнами и потёками."""
    noise = fbm(rng, SIZE)
    fine = value_noise(rng, SIZE, 128)
    red, white = (170, 50, 40), (225, 215, 190)
    rust_dark, rust_light = (85, 42, 18), (150, 80, 35)
    px = []
    for y in range(SIZE):
        row = []
        for x in range(SIZE):
            stripe = (x // 64) % 2
            base = red if stripe else white
            fade = 0.75 + 0.25 * fine[y][x]
            c = tuple(v * fade for v in base)
            n = noise[y][x]
            if n > 0.56:
                t = min(1.0, (n - 0.56) / 0.18)
                c = mix(c, mix(rust_light, rust_dark, fine[y][x]), t)
            row.append(c)
        px.append(row)
    drips(rng, SIZE, 40, px, 0.7)
    return px


def concrete(rng):
    """Серый бетон: шум, грязь, несколько трещин случайным блужданием."""
    noise = fbm(rng, SIZE)
    fine = value_noise(rng, SIZE, 256)
    px = []
    for y in range(SIZE):
        row = []
        for x in range(SIZE):
            g = 120 + 40 * noise[y][x] + 18 * (fine[y][x] - 0.5)
            dirt = max(0.0, noise[y][x] - 0.6) * 1.5
            row.append(mix((g, g, g * 0.97), (70, 65, 55), dirt))
        px.append(row)
    for _ in range(5):
        _crack(rng, px, rng.randrange(SIZE), rng.randrange(SIZE), rng.uniform(0, 6.283), rng.randrange(250, 600), depth=2)
    return px


def _crack(rng, px, x, y, angle, length, depth):
    """Трещина: почти прямая линия с дрожанием, пара ответвлений покороче."""
    import math
    for step in range(length):
        px[int(y) % SIZE][int(x) % SIZE] = (48, 45, 40)
        if step % 7 == 0:
            px[int(y + 1) % SIZE][int(x) % SIZE] = (70, 66, 60)
        angle += rng.uniform(-0.25, 0.25)
        x += math.cos(angle)
        y += math.sin(angle)
        if depth > 0 and rng.random() < 0.006:
            _crack(rng, px, x, y, angle + rng.choice((-0.9, 0.9)), length // 3, depth - 1)


def rust_metal(rng):
    """Тёмный металл: серо-коричневая база, ржавые пятна, царапины, потёки."""
    noise = fbm(rng, SIZE)
    fine = value_noise(rng, SIZE, 128)
    metal_dark, metal_light = (62, 60, 58), (112, 108, 100)
    rust_dark, rust_light = (90, 45, 20), (160, 85, 35)
    px = []
    for y in range(SIZE):
        row = []
        for x in range(SIZE):
            c = mix(metal_dark, metal_light, 0.4 * noise[y][x] + 0.6 * fine[y][x])
            n = noise[y][x]
            if n > 0.5:
                c = mix(c, mix(rust_light, rust_dark, fine[y][x]), min(1.0, (n - 0.5) / 0.2))
            row.append(c)
        px.append(row)
    for _ in range(60):
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        length = rng.randrange(20, 120)
        dx, dy = rng.uniform(-1, 1), rng.uniform(-0.3, 0.3)
        for i in range(length):
            xx, yy = int(x + dx * i) % SIZE, int(y + dy * i) % SIZE
            px[yy][xx] = mix(px[yy][xx], (150, 148, 140), 0.6)
    drips(rng, SIZE, 25, px, 0.6)
    return px


def carousel_paint(rng):
    """Крыша карусели: 12 секторов красный/жёлтый от центра, выцветание, ржавчина по краям."""
    import math
    noise = fbm(rng, SIZE)
    fine = value_noise(rng, SIZE, 128)
    red, yellow = (175, 48, 42), (225, 185, 60)
    rust = (120, 62, 25)
    half = SIZE / 2
    px = []
    for y in range(SIZE):
        row = []
        for x in range(SIZE):
            ang = math.atan2(y - half, x - half)
            sector = int((ang + math.pi) / (2 * math.pi) * 12) % 2
            base = red if sector else yellow
            dist = math.hypot(x - half, y - half) / half
            c = mix(base, (215, 205, 180), 0.25 * fine[y][x] + 0.25 * max(0.0, dist - 0.5))
            n = noise[y][x] + 0.35 * max(0.0, dist - 0.7)
            if n > 0.6:
                c = mix(c, rust, min(1.0, (n - 0.6) / 0.2))
            row.append(c)
        px.append(row)
    return px


def acid_water(rng):
    """Кислотная вода 256²: два зелёных по шуму, светлые разводы."""
    size = 256
    noise = fbm(rng, size, octaves=(3, 6, 12))
    deep, bright, foam = (30, 110, 20), (120, 255, 40), (200, 255, 150)
    px = []
    for y in range(size):
        row = []
        for x in range(size):
            n = noise[y][x]
            c = mix(deep, bright, n)
            if n > 0.68:
                c = mix(c, foam, min(1.0, (n - 0.68) / 0.1))
            row.append(c)
        px.append(row)
    return px


def dirt(rng):
    """Сухая земля для заднего плана: коричневая база, пятна травы и пыли."""
    noise = fbm(rng, SIZE)
    fine = value_noise(rng, SIZE, 128)
    dark, light, grass = (78, 58, 38), (132, 108, 72), (95, 105, 50)
    px = []
    for y in range(SIZE):
        row = []
        for x in range(SIZE):
            c = mix(dark, light, 0.5 * noise[y][x] + 0.5 * fine[y][x])
            if noise[y][x] > 0.58:
                c = mix(c, grass, min(1.0, (noise[y][x] - 0.58) / 0.15))
            row.append(c)
        px.append(row)
    return px


TEXTURES = {
    "rust_booth": rust_booth,
    "concrete": concrete,
    "rust_metal": rust_metal,
    "carousel_paint": carousel_paint,
    "acid_water": acid_water,
    "dirt": dirt,
}


def main(names):
    os.makedirs(OUT_DIR, exist_ok=True)
    for name in names or TEXTURES:
        if name not in TEXTURES:
            sys.exit(f"нет текстуры {name!r}; есть: {', '.join(TEXTURES)}")
        rng = random.Random(name)
        path = os.path.join(OUT_DIR, f"{name}.png")
        pixels = TEXTURES[name](rng)
        save_png(path, pixels, size=len(pixels))
        print(f"{name}.png: {len(pixels)}x{len(pixels)}, {os.path.getsize(path)} bytes")


if __name__ == "__main__":
    main(sys.argv[1:])
