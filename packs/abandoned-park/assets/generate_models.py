"""Генерирует .obj-модели пака из примитивов. Без зависимостей.

Запуск:  python generate_models.py [имя ...]
Без аргументов — все модели. Результат в models/<имя>.obj.
Оси: Y вверх, Z вперёд, единицы — метры. У каждой грани есть нормаль и UV
(box-проекция), чтобы текстуры ложились без ручной развёртки.
"""
import math
import os
import sys

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")


class Mesh:
    def __init__(self):
        self.v = []   # позиции
        self.vt = []  # uv
        self.vn = []  # нормали
        self.f = []   # (name, [(vi, ti, ni), ...])
        self.group = "default"

    def add_quad(self, p0, p1, p2, p3, uv_scale=1.0):
        self.add_poly([p0, p1, p2, p3], uv_scale)

    def add_poly(self, pts, uv_scale=1.0):
        """Плоский выпуклый многоугольник против часовой стрелки (если смотреть снаружи)."""
        n = _normal(pts[0], pts[1], pts[2])
        base_v = len(self.v) + 1
        base_t = len(self.vt) + 1
        base_n = len(self.vn) + 1
        self.v.extend(pts)
        self.vt.extend(_box_uv(pts, n, uv_scale))
        self.vn.append(n)
        self.f.append((self.group, [(base_v + i, base_t + i, base_n) for i in range(len(pts))]))

    def add_box(self, center, size, rot=None, uv_scale=1.0):
        cx, cy, cz = center
        sx, sy, sz = size[0] / 2, size[1] / 2, size[2] / 2
        c = [
            (-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
            (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz),
        ]
        if rot:
            c = [_rotate(p, rot) for p in c]
        c = [(x + cx, y + cy, z + cz) for x, y, z in c]
        quads = [
            (0, 3, 2, 1),  # back  (-z)
            (4, 5, 6, 7),  # front (+z)
            (0, 1, 5, 4),  # bottom
            (3, 7, 6, 2),  # top
            (0, 4, 7, 3),  # left
            (1, 2, 6, 5),  # right
        ]
        start_face = len(self.f)
        for a, b, cc, d in quads:
            self.add_quad(c[a], c[b], c[cc], c[d], uv_scale)
        self._check_outward(center, start_face)

    def add_cylinder(self, center, radius, height, segments=12, axis="y", rot=None, uv_scale=1.0):
        """Цилиндр вдоль оси axis ('y' или 'z'), центр в center."""
        cx, cy, cz = center
        h = height / 2
        start_face = len(self.f)
        ring_lo, ring_hi = [], []
        for i in range(segments):
            a = 2 * math.pi * i / segments
            x, w = radius * math.cos(a), radius * math.sin(a)
            if axis == "y":
                lo, hi = (x, -h, w), (x, h, w)
            else:
                lo, hi = (x, w, -h), (x, w, h)
            if rot:
                lo, hi = _rotate(lo, rot), _rotate(hi, rot)
            ring_lo.append((lo[0] + cx, lo[1] + cy, lo[2] + cz))
            ring_hi.append((hi[0] + cx, hi[1] + cy, hi[2] + cz))
        for i in range(segments):
            j = (i + 1) % segments
            if axis == "y":
                self.add_quad(ring_lo[j], ring_lo[i], ring_hi[i], ring_hi[j], uv_scale)
            else:
                self.add_quad(ring_lo[i], ring_lo[j], ring_hi[j], ring_hi[i], uv_scale)
        self._add_cap(ring_lo, reverse=(axis != "y"), uv_scale=uv_scale)
        self._add_cap(ring_hi, reverse=(axis == "y"), uv_scale=uv_scale)
        self._check_outward(center, start_face)

    def add_cone(self, center, radius, height, segments=12, rim_jitter=0.0, rng=None, uv_scale=1.0):
        """Конус вершиной вверх; rim_jitter 0..1 делает край рваным (радиус точек обода случайно меньше)."""
        cx, cy, cz = center
        start_face = len(self.f)
        apex = (cx, cy + height, cz)
        rim = []
        for i in range(segments):
            a = 2 * math.pi * i / segments
            r = radius * (1 - rim_jitter * rng.random()) if rng else radius
            rim.append((cx + r * math.cos(a), cy, cz + r * math.sin(a)))
        for i in range(segments):
            j = (i + 1) % segments
            self.add_poly([apex, rim[j], rim[i]], uv_scale)
        for i in range(segments):
            j = (i + 1) % segments
            self.add_poly([(cx, cy, cz), rim[i], rim[j]], uv_scale)
        self._check_outward((cx, cy + height / 4, cz), start_face)

    def add_sphere(self, center, radius, segments=12, rings=6, uv_scale=1.0):
        cx, cy, cz = center
        start_face = len(self.f)
        grid = []
        for r in range(rings + 1):
            phi = math.pi * r / rings
            row = []
            for i in range(segments):
                th = 2 * math.pi * i / segments
                row.append((cx + radius * math.sin(phi) * math.cos(th),
                            cy + radius * math.cos(phi),
                            cz + radius * math.sin(phi) * math.sin(th)))
            grid.append(row)
        for r in range(rings):
            for i in range(segments):
                j = (i + 1) % segments
                a, b, c, d = grid[r][i], grid[r][j], grid[r + 1][j], grid[r + 1][i]
                if r == 0:
                    self.add_poly([a, c, d], uv_scale)
                elif r == rings - 1:
                    self.add_poly([a, b, c], uv_scale)
                else:
                    self.add_poly([a, b, c, d], uv_scale)
        self._check_outward(center, start_face)

    def add_prism(self, base, y0, y1, uv_scale=1.0):
        """Выпуклая призма: base — точки (x, z) выпуклого многоугольника в любом порядке обхода, от y0 до y1."""
        start_face = len(self.f)
        center = (sum(x for x, _ in base) / len(base), (y0 + y1) / 2, sum(z for _, z in base) / len(base))
        lo = [(x, y0, z) for x, z in base]
        hi = [(x, y1, z) for x, z in base]
        faces = [lo, hi] + [[lo[i], lo[(i + 1) % len(base)], hi[(i + 1) % len(base)], hi[i]] for i in range(len(base))]
        for pts in faces:
            n = _normal(pts[0], pts[1], pts[2])
            fc = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
            if sum(n[k] * (fc[k] - center[k]) for k in range(3)) < 0:
                pts = list(reversed(pts))
            self.add_poly(pts, uv_scale)
        self._check_outward(center, start_face)

    def _add_cap(self, ring, reverse, uv_scale):
        pts = list(reversed(ring)) if reverse else ring
        n = _normal(pts[0], pts[1], pts[2])
        base_v = len(self.v) + 1
        base_t = len(self.vt) + 1
        base_n = len(self.vn) + 1
        self.v.extend(pts)
        self.vt.extend(_box_uv(pts, n, uv_scale))
        self.vn.append(n)
        self.f.append((self.group, [(base_v + i, base_t + i, base_n) for i in range(len(pts))]))

    def _check_outward(self, center, start_face):
        """Самопроверка: нормаль каждой грани выпуклого примитива смотрит от его центра."""
        for group, idx in self.f[start_face:]:
            pts = [self.v[vi - 1] for vi, _, _ in idx]
            n = self.vn[idx[0][2] - 1]
            fc = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
            dot = sum(n[k] * (fc[k] - center[k]) for k in range(3))
            if dot <= 0:
                raise AssertionError(f"грань в группе {group!r} смотрит внутрь")

    def write(self, path):
        with open(path, "w", encoding="ascii") as fh:
            fh.write("# generated by generate_models.py\n")
            for x, y, z in self.v:
                fh.write(f"v {x:.4f} {y:.4f} {z:.4f}\n")
            for u, v in self.vt:
                fh.write(f"vt {u:.4f} {v:.4f}\n")
            for x, y, z in self.vn:
                fh.write(f"vn {x:.4f} {y:.4f} {z:.4f}\n")
            current = None
            for group, idx in self.f:
                if group != current:
                    fh.write(f"g {group}\n")
                    current = group
                fh.write("f " + " ".join(f"{a}/{b}/{c}" for a, b, c in idx) + "\n")
        return len(self.v), len(self.f)


def _normal(p0, p1, p2):
    ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return (nx / length, ny / length, nz / length)


def _box_uv(points, normal, scale):
    ax, ay, az = (abs(c) for c in normal)
    if ax >= ay and ax >= az:
        return [(p[2] * scale, p[1] * scale) for p in points]
    if ay >= az:
        return [(p[0] * scale, p[2] * scale) for p in points]
    return [(p[0] * scale, p[1] * scale) for p in points]


def _rotate(p, rot):
    """rot = (rx, ry, rz) в градусах, порядок X → Y → Z."""
    x, y, z = p
    rx, ry, rz = (math.radians(a) for a in rot)
    if rx:
        y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
    if ry:
        x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
    if rz:
        x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
    return (x, y, z)


# ---------------------------------------------------------------- модели

def ticket():
    """Билет 0.6×0.3, толщина 2 см, зубчатые короткие края, лежит в плоскости XZ."""
    m = Mesh()
    m.group = "body"
    m.add_box((0, 0, 0), (0.5, 0.02, 0.3), uv_scale=2.0)
    m.group = "teeth"
    teeth = 5
    pitch = 0.3 / teeth
    for i in range(teeth):
        z = -0.15 + pitch * (i + 0.5)
        m.add_box((-0.275, 0, z), (0.05, 0.02, pitch * 0.6), uv_scale=2.0)
        m.add_box((0.275, 0, z), (0.05, 0.02, pitch * 0.6), uv_scale=2.0)
    return m


def booth():
    """Киоск 2×2.2×2: корпус, прилавок, крыша, провисший козырёк."""
    m = Mesh()
    m.group = "walls"
    m.add_box((0, 1.1, 0), (2.0, 2.2, 2.0), uv_scale=0.5)
    m.group = "counter"
    m.add_box((0, 1.0, 1.15), (2.2, 0.12, 0.4), uv_scale=0.5)
    m.group = "roof"
    m.add_box((0, 2.28, 0), (2.4, 0.16, 2.4), uv_scale=0.5)
    m.group = "awning"
    m.add_box((0, 2.0, 1.55), (2.4, 0.06, 0.9), rot=(25, 0, 0), uv_scale=0.5)
    m.group = "posts"
    for x in (-1.1, 1.1):
        m.add_cylinder((x, 1.6, 1.95), 0.04, 0.9, segments=6)
    return m


FERRIS_RADIUS, FERRIS_GAP = 6.0, 0.9


def ferris_wheel():
    """Колесо обозрения радиусом 6 одним куском: ротор + опоры. Mover крутит его целиком вместе с опорами —
    для вращения брать ferris_wheel_rotor + ferris_wheel_stand (pivot у обоих в ступице)."""
    m = Mesh()
    _ferris_rotor(m)
    _ferris_stand(m)
    return m


def ferris_wheel_rotor():
    """Вращающаяся часть колеса: два обода, спицы, ступица, 8 кабинок. Pivot — центр ступицы."""
    m = Mesh()
    _ferris_rotor(m)
    return m


def ferris_wheel_stand():
    """Неподвижная часть колеса: А-образные опоры, основание и ось сквозь ступицу. Pivot — центр ступицы."""
    m = Mesh()
    _ferris_stand(m)
    m.group = "axle"
    m.add_cylinder((0, 0, 0), 0.18, FERRIS_GAP + 1.2, segments=8, axis="z")
    return m


def _ferris_rotor(m):
    radius, segments, gap = FERRIS_RADIUS, 24, FERRIS_GAP
    m.group = "rims"
    for z in (-gap / 2, gap / 2):
        for i in range(segments):
            a0 = 2 * math.pi * i / segments
            a1 = 2 * math.pi * (i + 1) / segments
            am = (a0 + a1) / 2
            length = 2 * radius * math.sin(math.pi / segments) * 1.05
            m.add_box((radius * math.cos(am), radius * math.sin(am), z),
                      (length, 0.15, 0.15), rot=(0, 0, math.degrees(am) + 90))
    m.group = "spokes"
    for z in (-gap / 2, gap / 2):
        for i in range(8):
            a = 2 * math.pi * i / 8
            m.add_box((radius / 2 * math.cos(a), radius / 2 * math.sin(a), z),
                      (radius, 0.1, 0.1), rot=(0, 0, math.degrees(a)))
    m.group = "hub"
    m.add_cylinder((0, 0, 0), 0.5, gap + 0.4, segments=12, axis="z")
    m.group = "gondolas"
    for i in range(8):
        a = 2 * math.pi * i / 8 + math.pi / 8
        gx, gy = radius * math.cos(a), radius * math.sin(a)
        m.add_box((gx, gy - 0.6, 0), (0.9, 0.9, 1.1))
        m.add_box((gx, gy - 0.1, 0), (0.08, 0.5, 0.08))


def _ferris_stand(m):
    radius, gap = FERRIS_RADIUS, FERRIS_GAP
    m.group = "legs"
    for z in (-gap / 2 - 0.3, gap / 2 + 0.3):
        for sign in (-1, 1):
            # A-образно: верх у ступицы, низ разведён на ±3.2 м
            m.add_box((sign * 1.6, -radius / 2 - 0.5, z), (0.25, radius + 1.2, 0.25),
                      rot=(0, 0, sign * 28))
    m.group = "base"
    m.add_box((0, -radius - 1.1, 0), (6.0, 0.3, gap + 1.4))


def horse(headless=False):
    """Лошадка карусели из боксов: тело, 4 ноги, шея и голова (или обрубок шеи), хвост. Высота ~1.3 м."""
    m = Mesh()
    m.group = "body"
    m.add_box((0, 0.85, 0), (0.45, 0.4, 1.1), uv_scale=1.5)
    m.group = "legs"
    for x in (-0.14, 0.14):
        for z in (-0.4, 0.4):
            m.add_box((x, 0.42, z), (0.12, 0.5, 0.12), rot=(0, 0, 0), uv_scale=1.5)
    m.group = "neck"
    if headless:
        m.add_box((0, 1.1, 0.5), (0.22, 0.2, 0.22), uv_scale=1.5)
    else:
        m.add_box((0, 1.2, 0.6), (0.2, 0.55, 0.22), rot=(-30, 0, 0), uv_scale=1.5)
        m.group = "head"
        m.add_box((0, 1.42, 0.92), (0.2, 0.2, 0.42), uv_scale=1.5)
        m.add_box((0, 1.55, 0.8), (0.14, 0.12, 0.06), uv_scale=1.5)
    m.group = "tail"
    m.add_box((0, 0.9, -0.62), (0.1, 0.3, 0.12), rot=(20, 0, 0), uv_scale=1.5)
    return m


def horse_headless():
    return horse(headless=True)


def carousel_roof():
    """Конус радиусом 11, высотой 3, 12 секций, рваный край; ось — шпиль."""
    import random
    m = Mesh()
    m.group = "roof"
    m.add_cone((0, 0, 0), 11.0, 3.0, segments=12, rim_jitter=0.18, rng=random.Random("roof"), uv_scale=0.25)
    m.group = "spire"
    m.add_cylinder((0, 3.4, 0), 0.12, 1.2, segments=6)
    m.add_sphere((0, 4.1, 0), 0.25, segments=8, rings=4)
    return m


DECK_INNER_R, DECK_OUTER_R = 7.0, 10.0   # внутренний диск карусели и внешнее кольцо из 8 осыпающихся секторов


def carousel_deck():
    """Пол карусели: диск радиусом 7 (дальше — сектора carousel_sector), толщиной 0.5, верх на y = 0; ступица в центре."""
    m = Mesh()
    m.group = "deck"
    m.add_cylinder((0, -0.25, 0), DECK_INNER_R, 0.5, segments=32, uv_scale=0.25)
    m.group = "hub"
    m.add_cylinder((0, 0.08, 0), 1.2, 0.16, segments=12, uv_scale=0.5)   # ниже stepOffset 0.2: заходится без прыжка
    return m


def carousel_sector():
    """Сектор внешнего кольца карусели: r 7…10, 45° вокруг +X, толщина 0.5, верх на y = 0. Pivot — ось карусели,
    так что восемь копий, повёрнутых на 45°, замыкают кольцо. Кольцо не выпуклое — собрано из 4 выпуклых призм."""
    m = Mesh()
    m.group = "sector"
    steps = 4
    for i in range(steps):
        a0 = math.radians(-22.5 + 45 * i / steps)
        a1 = math.radians(-22.5 + 45 * (i + 1) / steps)
        base = [(r * math.cos(a), r * math.sin(a)) for r, a in
                ((DECK_INNER_R, a0), (DECK_OUTER_R, a0), (DECK_OUTER_R, a1), (DECK_INNER_R, a1))]
        m.add_prism(base, -0.5, 0.0, uv_scale=0.25)
    return m


def debris():
    """Обломок ~1 м: три пересекающихся повёрнутых бокса, читается как камень."""
    m = Mesh()
    m.group = "rock"
    m.add_box((0, 0, 0), (1.0, 0.7, 0.8), rot=(15, 30, 10))
    m.add_box((0.1, 0.05, -0.05), (0.8, 0.9, 0.6), rot=(-20, 60, 25))
    m.add_box((-0.1, -0.05, 0.1), (0.6, 0.6, 1.0), rot=(40, -15, -30))
    return m


def cart():
    """Вагонетка 1.4×1.0×2.2: корпус, борта, 4 колеса на оси X."""
    m = Mesh()
    m.group = "body"
    m.add_box((0, 0.55, 0), (1.2, 0.5, 2.0), uv_scale=0.8)
    m.group = "walls"
    for x in (-0.65, 0.65):
        m.add_box((x, 0.9, 0), (0.1, 0.5, 2.0), uv_scale=0.8)
    for z in (-1.05, 1.05):
        m.add_box((0, 0.95, z), (1.4, 0.6, 0.1), uv_scale=0.8)
    m.group = "wheels"
    for x in (-0.75, 0.75):
        for z in (-0.7, 0.7):
            m.add_cylinder((x, 0.3, z), 0.3, 0.12, segments=10, axis="z", rot=(0, 90, 0))
    m.group = "axles"
    for z in (-0.7, 0.7):
        m.add_cylinder((0, 0.3, z), 0.05, 1.5, segments=6, axis="z", rot=(0, 90, 0))
    return m


def rail_segment():
    """Секция рельсов 6 м: несущая балка, два рельса, 7 шпал."""
    m = Mesh()
    m.group = "beam"
    m.add_box((0, -0.3, 0), (0.4, 0.4, 6.0), uv_scale=0.5)
    m.group = "sleepers"
    for i in range(7):
        m.add_box((0, 0.0, -2.7 + 0.9 * i), (1.3, 0.12, 0.2), uv_scale=0.5)
    m.group = "rails"
    for x in (-0.5, 0.5):
        m.add_box((x, 0.12, 0), (0.08, 0.12, 6.0), uv_scale=0.5)
    return m


def mascot_headless():
    """Маскот без головы ~2 м: тело-капсула, обрубок шеи, руки и ноги цилиндрами, большие ботинки."""
    m = Mesh()
    m.group = "body"
    m.add_cylinder((0, 1.1, 0), 0.45, 0.9, segments=12)
    m.add_sphere((0, 0.65, 0), 0.45, segments=12, rings=6)
    m.add_sphere((0, 1.55, 0), 0.45, segments=12, rings=6)
    m.group = "neck"
    m.add_cylinder((0, 2.05, 0), 0.14, 0.2, segments=8)
    m.group = "arms"
    for sign in (-1, 1):
        m.add_cylinder((sign * 0.7, 1.35, 0), 0.12, 0.9, segments=8, rot=(0, 0, sign * 35))
        m.add_sphere((sign * 0.98, 0.98, 0), 0.18, segments=8, rings=4)
    m.group = "legs"
    for sign in (-1, 1):
        m.add_cylinder((sign * 0.22, 0.25, 0), 0.13, 0.5, segments=8)
        m.add_box((sign * 0.22, 0.08, 0.12), (0.3, 0.16, 0.55), uv_scale=1.5)
    return m


def lamppost():
    """Парковый фонарь 5 м: основание, столб, кронштейн, покосившийся плафон."""
    m = Mesh()
    m.group = "base"
    m.add_cylinder((0, 0.15, 0), 0.3, 0.3, segments=8)
    m.group = "pole"
    m.add_cylinder((0, 2.6, 0), 0.08, 4.9, segments=8)
    m.group = "arm"
    m.add_box((0.45, 4.95, 0), (0.9, 0.08, 0.08))
    m.group = "lamp"
    m.add_box((0.9, 4.75, 0), (0.5, 0.35, 0.5), rot=(0, 0, -12))
    return m


def fence_segment():
    """Секция забора 3 м: два столба и три перекладины, одна провисла."""
    m = Mesh()
    m.group = "posts"
    for x in (-1.5, 1.5):
        m.add_box((x, 0.6, 0), (0.12, 1.2, 0.12))
    m.group = "rails"
    m.add_box((0, 1.05, 0), (3.0, 0.08, 0.05))
    m.add_box((0, 0.65, 0), (3.0, 0.08, 0.05), rot=(0, 0, 6))
    m.add_box((0, 0.25, 0), (3.0, 0.08, 0.05))
    return m


def barrel():
    """Бочка 1 м: корпус и два обруча."""
    m = Mesh()
    m.group = "body"
    m.add_cylinder((0, 0.5, 0), 0.4, 1.0, segments=12)
    m.group = "hoops"
    for y in (0.22, 0.78):
        m.add_cylinder((0, y, 0), 0.43, 0.06, segments=12)
    return m


def dead_tree():
    """Сухое дерево 6 м: ствол и четыре голых ветки."""
    m = Mesh()
    m.group = "trunk"
    m.add_cylinder((0, 2.0, 0), 0.28, 4.0, segments=8)
    m.add_cylinder((0, 4.6, 0), 0.16, 1.6, segments=8)
    m.group = "branches"
    for angle, y, tilt, length in ((0, 3.2, 40, 2.2), (110, 3.9, 50, 1.8), (210, 4.4, 35, 2.0), (300, 2.6, 55, 1.5)):
        r = math.radians(angle)
        dx, dz = math.sin(r) * length * 0.35, math.cos(r) * length * 0.35
        m.add_cylinder((dx, y + length * 0.3, dz), 0.08, length, segments=6, rot=(tilt * math.cos(r), 0, -tilt * math.sin(r)))
    return m


def hill():
    """Низкополигональный холм радиусом 25, высотой 8, рваный край; для заднего плана."""
    import random
    m = Mesh()
    m.group = "hill"
    m.add_cone((0, 0, 0), 25.0, 8.0, segments=16, rim_jitter=0.12, rng=random.Random("hill"), uv_scale=0.1)
    return m


def coaster_trestle():
    """Опора заброшенных горок 10 м: две наклонные ноги, три поперечины, площадка под рельсы."""
    m = Mesh()
    m.group = "legs"
    for sign in (-1, 1):
        m.add_box((sign * 1.2, 5.0, 0), (0.3, 10.2, 0.3), rot=(0, 0, sign * -7))
    m.group = "beams"
    for y, w in ((2.5, 3.2), (5.5, 2.6), (8.5, 2.0)):
        m.add_box((0, y, 0), (w, 0.2, 0.2))
    m.group = "deck"
    m.add_box((0, 10.1, 0), (2.0, 0.3, 2.4))
    return m


def throne():
    """Трон маскота ~3 м: сиденье, высокая спинка с веером «лучей», подлокотники-шары, ножки. Pivot — пол под
    центром сиденья, сидят лицом к +Z; габарит 1.8 × 1.4 м."""
    m = Mesh()
    m.group = "seat"
    m.add_box((0, 0.55, 0.05), (1.5, 0.3, 1.2))
    m.group = "legs"
    for sx in (-0.6, 0.6):
        for sz in (-0.45, 0.5):
            m.add_box((sx, 0.2, sz), (0.2, 0.4, 0.2))
    m.group = "back"
    m.add_box((0, 1.6, -0.5), (1.6, 2.1, 0.25))
    for k in range(5):   # веер над спинкой, как у циркового трона
        a = math.radians(-50 + 25 * k)
        m.add_box((1.0 * math.sin(a), 2.65 + 0.55 * math.cos(a), -0.5), (0.22, 1.1, 0.18), rot=(0, 0, -math.degrees(a)))
        m.add_sphere((1.55 * math.sin(a), 2.65 + 1.1 * math.cos(a), -0.5), 0.17, segments=8, rings=4)
    m.group = "arms"
    for sx in (-0.85, 0.85):
        m.add_box((sx, 0.95, 0.05), (0.2, 0.5, 1.2))
        m.add_sphere((sx, 1.25, 0.6), 0.2, segments=8, rings=4)
    return m


def throne_dais():
    """Помост трона: диск r 3, высота 0.15 (ниже ступеньки 0.2 — заходят и боты), pivot — пол в центре."""
    m = Mesh()
    m.group = "dais"
    m.add_cylinder((0, 0.075, 0), 3.0, 0.15, segments=24, uv_scale=0.5)
    return m


def crown():
    """Корона ~1.4 м в поперечнике: обруч из 12 пластин, 6 зубцов с шарами. Pivot — низ обруча в центре."""
    m = Mesh()
    r, n = 0.7, 12
    m.group = "band"
    for i in range(n):
        a = 2 * math.pi * (i + 0.5) / n
        m.add_box((r * math.cos(a), 0.2, r * math.sin(a)), (0.08, 0.4, 2 * r * math.sin(math.pi / n) + 0.02),
                  rot=(0, -math.degrees(a), 0))
    m.group = "spikes"
    for i in range(6):
        a = 2 * math.pi * i / 6
        x, z = r * math.cos(a), r * math.sin(a)
        m.add_cone((x, 0.4, z), 0.14, 0.45, segments=6)
        m.add_sphere((x, 0.92, z), 0.1, segments=8, rings=4)
    return m


def crown_zone():
    """Кольцо зоны короны на полу: r 2.25…2.5, толщина 4 см, 32 пластины. Pivot — центр на полу."""
    m = Mesh()
    m.group = "ring"
    r0, r1, n = 2.25, 2.5, 32
    for i in range(n):
        a = 2 * math.pi * (i + 0.5) / n
        rm = (r0 + r1) / 2
        m.add_box((rm * math.cos(a), 0.02, rm * math.sin(a)), (r1 - r0, 0.04, 2 * r1 * math.sin(math.pi / n) + 0.02),
                  rot=(0, -math.degrees(a), 0))
    return m


def cannon_barrel():
    """Ствол циркового ядромёта 3.2 м вдоль +Z: казённик-шар, ствол сужается от r 0.5 к 0.42 тремя цилиндрами,
    два обруча, раструб у дула. Pivot — ось цапф (z 0.6 от казённой части), наклон задаёт сцена поворотом по X."""
    m = Mesh()
    m.group = "breech"
    m.add_sphere((0, 0, -0.6), 0.5, segments=12, rings=6)
    m.group = "barrel"
    for z0, z1, r in ((-0.6, 0.5, 0.5), (0.5, 1.6, 0.46), (1.6, 2.6, 0.42)):
        m.add_cylinder((0, 0, (z0 + z1) / 2), r, z1 - z0, segments=14, axis="z")
    m.group = "hoops"
    for z in (0.5, 1.6):
        m.add_cylinder((0, 0, z), 0.53, 0.12, segments=14, axis="z")
    m.group = "muzzle"
    m.add_cylinder((0, 0, 2.5), 0.56, 0.2, segments=14, axis="z")
    m.group = "trunnions"
    m.add_cylinder((0, 0, 0), 0.14, 1.3, segments=8, rot=(0, 0, 90))
    return m


def mascot_target():
    """Жестяная мишень тира — голова маскота: диск-лицо r 0.45 и два уха r 0.18 толщиной 6 см в плоскости XY
    (лицом к −Z и +Z), глаза-кнопки и нос на стороне −Z (к стрелкам), под головой стойка 0.6 м. Pivot — низ стойки,
    центр лица на y 1.05."""
    m = Mesh()
    cy = 1.05
    m.group = "face"
    m.add_cylinder((0, cy, 0), 0.45, 0.06, segments=20, axis="z")
    m.group = "ears"
    for sign in (-1, 1):
        m.add_cylinder((sign * 0.36, cy + 0.36, 0), 0.18, 0.06, segments=12, axis="z")
    m.group = "eyes"
    for sign in (-1, 1):
        m.add_cylinder((sign * 0.16, cy + 0.1, -0.05), 0.07, 0.04, segments=10, axis="z")
    m.add_cylinder((0, cy - 0.08, -0.05), 0.06, 0.04, segments=10, axis="z")
    m.group = "post"
    m.add_box((0, 0.3, 0), (0.08, 0.6, 0.06))
    return m


def cotton_candy():
    """Облако сахарной ваты ~0.9 м: большой шар, 7 комков вокруг и один сверху, без палочки (её ставит сцена кубом другого
    цвета). Pivot — низ облака на оси, куда входит палочка."""
    import random
    m = Mesh()
    rng = random.Random("cotton-candy")
    m.group = "fluff"
    m.add_sphere((0, 0.42, 0), 0.36, segments=12, rings=6)
    for k in range(7):
        a = 2 * math.pi * k / 7 + rng.uniform(-0.2, 0.2)
        y = 0.42 + rng.uniform(-0.12, 0.2)
        r = rng.uniform(0.17, 0.24)
        m.add_sphere((0.3 * math.cos(a), y, 0.3 * math.sin(a)), r, segments=8, rings=4)
    m.add_sphere((0.03, 0.74, -0.02), 0.2, segments=8, rings=4)
    return m


MODELS = {
    "mascot_target": mascot_target,
    "cotton_candy": cotton_candy,
    "cannon_barrel": cannon_barrel,
    "throne": throne,
    "throne_dais": throne_dais,
    "crown": crown,
    "crown_zone": crown_zone,
    "ticket": ticket,
    "booth": booth,
    "ferris_wheel": ferris_wheel,
    "ferris_wheel_rotor": ferris_wheel_rotor,
    "ferris_wheel_stand": ferris_wheel_stand,
    "horse": horse,
    "horse_headless": horse_headless,
    "carousel_roof": carousel_roof,
    "carousel_deck": carousel_deck,
    "carousel_sector": carousel_sector,
    "debris": debris,
    "cart": cart,
    "rail_segment": rail_segment,
    "mascot_headless": mascot_headless,
    "lamppost": lamppost,
    "fence_segment": fence_segment,
    "barrel": barrel,
    "dead_tree": dead_tree,
    "hill": hill,
    "coaster_trestle": coaster_trestle,
}


def main(names):
    os.makedirs(OUT_DIR, exist_ok=True)
    for name in names or MODELS:
        if name not in MODELS:
            sys.exit(f"нет модели {name!r}; есть: {', '.join(MODELS)}")
        mesh = MODELS[name]()
        path = os.path.join(OUT_DIR, f"{name}.obj")
        nv, nf = mesh.write(path)
        print(f"{name}.obj: {nv} vertices, {nf} faces")


if __name__ == "__main__":
    main(sys.argv[1:])
