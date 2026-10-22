"""План сцены мини-игры сверху + разрез + метрики пространства. Без зависимостей (PNG через zlib).

Читает MainScene.scene мода (формат PMH, tools/pmscene.py), меши .obj из Assets/Props по .pmeta,
настройки движения из ModSettings.json и рисует:

    plan.png       вид сверху на игровой пол: цвет = роль объекта, яркость = высота, номера = легенда
    plan_wide.png  вся сцена с задником (композиция дальнего плана, ориентиры)
    elevation_north.png / elevation_south.png  силуэт «от южного края на север» и обратно: ярусы высот,
                   ориентиры над задником, линия высоты прыжка
    plan.txt       легенда номеров, метрики, карта клеток в ASCII

Запуск из корня репозитория:
    python .claude/skills/pummel-party-level-design/scripts/plan_view.py "Ticket Rush Gen" --out packs/<theme>/minigames/<slug>/plan
Аргумент — имя мода в WorkshopMods, имя встроенного мода (InbuiltMods), папка мода или путь к MainScene.scene.

Допущения (не из вики, проверять в редакторе): LowPolyCube — куб 1×1×1 с центром в pivot, LowPolyPlane — 10×10
по XZ, LowPolySphere — диаметр 1; Water растёт от pivot в +X/+Z (Width×Height клеток по CellSize).
Размеры остальных встроенных props неизвестны (каталог Addressables бинарный) — они рисуются маркером «?».
"""
from __future__ import annotations

import argparse
import glob
import heapq
import json
import math
import os
import struct
import sys
import zlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import pmscene as P  # noqa: E402

WORKSHOP = os.path.expandvars(r"%USERPROFILE%\AppData\LocalLow\Rebuilt Games\Pummel Party\WorkshopMods")
INBUILT = r"C:\Program Files (x86)\Steam\steamapps\common\Pummel Party\PummelParty_Data\StreamingAssets\InbuiltMods"

PROP_CUBE = "cfc9faf9-3852-4dbe-803b-32cec4c94139"
PROP_PLANES = ("e314a70b-98f2-4459-9214-ef4da97b4e6d", "331019a7-e85f-47d4-a19d-703dc99a3fab")
PROP_SPHERE = "c7d7ef4d-4e66-4b08-b91a-d5b0190b74ee"
LAYER_WORLD_GROUND = 10

# ModActionType, которые важны для чтения пространства
A_KILL, A_DAMAGE, A_HEALTH, A_SCORE, A_VELOCITY, A_GRAVITY, A_MODIFY = 64, 640, 96, 128, 832, 448, 512

HEAD = 1.5      # высота, до которой препятствие мешает идти (персонаж Pummel невысокий; уточнять в плейтесте)
PLAYER_R = 0.4  # радиус игрока для «пробега без помех»: дорожка, которую игрок пробегает, не задевая помех (допущение)

COLORS = {
    "bg": (24, 24, 30), "grid": (40, 40, 50), "grid10": (62, 62, 76),
    "floor": (120, 120, 126), "wall": (196, 104, 52), "low": (220, 170, 70), "decor": (92, 128, 104),
    "unknown": (150, 150, 150), "water": (50, 110, 210), "kill": (235, 50, 50), "velocity": (255, 140, 0),
    "trigger": (240, 220, 60), "spawn": (60, 230, 90), "respawn": (60, 210, 230), "spawner": (255, 215, 0),
    "item": (255, 215, 0), "motion": (230, 70, 230), "nav": (90, 170, 255), "empty": (200, 60, 160), "label": (255, 255, 255),
}


# ---------------------------------------------------------------- математика трансформов (Unity: TRS, Euler ZXY)

def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def trs(pos, rot, scale):
    x, y, z = (math.radians(v) for v in rot)
    cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
    r = [[sum(ry[i][k] * sum(rx[k][m] * rz[m][j] for m in range(3)) for k in range(3)) for j in range(3)] for i in range(3)]
    return [[r[i][0] * scale[0], r[i][1] * scale[1], r[i][2] * scale[2], pos[i]] for i in range(3)] + [[0, 0, 0, 1]]


IDENTITY = trs((0, 0, 0), (0, 0, 0), (1, 1, 1))


def apply(m, p):
    return (m[0][0] * p[0] + m[0][1] * p[1] + m[0][2] * p[2] + m[0][3],
            m[1][0] * p[0] + m[1][1] * p[1] + m[1][2] * p[2] + m[1][3],
            m[2][0] * p[0] + m[2][1] * p[1] + m[2][2] * p[2] + m[2][3])


# ---------------------------------------------------------------- декодирование свойств

def _r(raw): return P.Reader(raw)
def d_vec3(raw): return struct.unpack("<fff", raw[:12])
def d_i32(raw): return struct.unpack("<i", raw[:4])[0]
def d_f32(raw): return struct.unpack("<f", raw[:4])[0]
def d_bool(raw): return raw[:1] == b"\x01"


def d_ref(raw):
    r = _r(raw)
    return r.string() if r.bool() else None


def d_ref_array(raw):
    r = _r(raw)
    out = []
    for _ in range(r.i32()):
        if r.bool():
            out.append(r.string())
    return out


def d_trigger_actions(raw) -> list[int]:
    """ModLogicTrigger: u16 тип + JSON + u16 n + n × (u16 тип действия + JSON). Возвращает типы действий."""
    if not raw:
        return []
    r = _r(raw)
    r.u16(); r.string()
    out = []
    for _ in range(r.u16()):
        out.append(r.u16()); r.string()
    return out


def d_animations(raw) -> list[str]:
    """ModSimpleAnimator.Animations: i32 n + n × JSON. Возвращает «Имя пресета частота/с»."""
    r = _r(raw)
    out = []
    for _ in range(r.i32()):
        d = json.loads(r.string())
        refs = d.get("references", {})
        layers = [x.get("data", {}) for x in refs.get("RefIds", [])] or [v.get("data", {}) for k, v in refs.items() if isinstance(v, dict)]
        speed = next((x["AnimationSpeed"] for x in layers if "AnimationSpeed" in x), None)
        out.append(f"{d.get('m_animationName', '?')}" + (f" {speed:g}/с" if speed is not None else ""))
    return out


def prop(c: P.Component, name, dec, default=None):
    p = c.prop(name)
    if p is None or not p.raw:
        return default
    try:
        return dec(p.raw)
    except Exception:  # noqa: BLE001 — незнакомая кодировка не должна ронять отрисовку
        return default


# ---------------------------------------------------------------- меши

def load_obj(path):
    verts, tris = [], []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("v "):
                verts.append(tuple(float(v) for v in line.split()[1:4]))
            elif line.startswith("f "):
                idx = []
                for tok in line.split()[1:]:
                    i = int(tok.split("/")[0])
                    idx.append(i - 1 if i > 0 else len(verts) + i)
                for k in range(1, len(idx) - 1):
                    tris.append((idx[0], idx[k], idx[k + 1]))
    return verts, tris


def _box_mesh(hx, hy, hz, cy=0.0):
    v = [(x, y + cy, z) for x in (-hx, hx) for y in (-hy, hy) for z in (-hz, hz)]
    t = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    return v, t


BUILTIN_MESHES = {PROP_CUBE: _box_mesh(0.5, 0.5, 0.5), PROP_SPHERE: _box_mesh(0.5, 0.5, 0.5)}
for _g in PROP_PLANES:
    BUILTIN_MESHES[_g] = ([(-5, 0, -5), (5, 0, -5), (5, 0, 5), (-5, 0, 5)], [(0, 1, 2), (0, 2, 3)])


class ModFiles:
    def __init__(self, mod_dir):
        self.mod_dir = mod_dir
        self.props, self.prefabs = {}, {}
        for meta in glob.glob(os.path.join(mod_dir, "Assets", "**", "*.pmeta"), recursive=True):
            try:
                guid = json.load(open(meta, encoding="utf-8-sig"))["guid"]["serializedGuid"]
            except Exception:  # noqa: BLE001
                continue
            path = meta[:-len(".pmeta")]
            if path.lower().endswith(".obj"):
                self.props[guid] = path
            elif path.lower().endswith(".pfab"):
                self.prefabs[guid] = path
        self._mesh_cache = {}
        self._prefab_cache = {}

    def mesh(self, guid):
        if guid in BUILTIN_MESHES:
            return BUILTIN_MESHES[guid]
        if guid not in self.props:
            return None
        if guid not in self._mesh_cache:
            self._mesh_cache[guid] = load_obj(self.props[guid])
        return self._mesh_cache[guid]

    def prefab(self, guid):
        if guid not in self.prefabs:
            return None
        if guid not in self._prefab_cache:
            self._prefab_cache[guid] = P.load(self.prefabs[guid])
        return self._prefab_cache[guid]


# ---------------------------------------------------------------- модель сцены для анализа

class Thing:
    """Один объект сцены с мировыми координатами и ролью."""

    def __init__(self, path, go, m):
        self.path, self.go, self.m = path, go, m
        self.kind = None          # floor / wall / low / decor / unknown
        self.tris3 = []           # мировые треугольники меша
        self.aabb = None          # (min xyz, max xyz)
        self.markers = []         # (тип, данные) — триггеры, спавны, спавнеры, вода, движение
        self.label = None

    @property
    def pos(self): return (self.m[0][3], self.m[1][3], self.m[2][3])


def collect(scene: P.Scene, files: ModFiles):
    things: list[Thing] = []
    tpos = {}   # GUID трансформа → мировая позиция (точки спавнеров OnTargets)

    def visit(go: P.GameObject, parent_m, prefix, depth=0):
        if not go.active:
            return
        t = go.component("ModTransform")
        if t is not None:
            m = mat_mul(parent_m, trs(prop(t, "position", d_vec3, (0, 0, 0)), prop(t, "rotation", d_vec3, (0, 0, 0)),
                                      prop(t, "scale", d_vec3, (1, 1, 1))))
        else:
            m = parent_m
        path = f"{prefix}/{go.name}" if prefix else go.name
        th = Thing(path, go, m)
        tpos[go.transform_guid] = th.pos
        for c in go.components:
            if not c.enabled:
                continue
            classify(th, c, files)
        if th.kind or th.markers:
            things.append(th)
        inst = go.component("ModPrefabInstance")
        if inst is not None and depth < 4:
            pf = files.prefab(prop(inst, "PrefabGUID", lambda r: _r(r).string()) or prop(inst, "PrefabReference", d_ref))
            if pf is not None:
                for root in pf.roots:   # корень префаба неактивен в файле — обходим его детей и компоненты
                    root_copy = P.GameObject(root.name, True, root.layer, root.tag, root.children, root.transform_guid, root.components)
                    visit(root_copy, m, path, depth + 1)
        for ch in go.children:
            visit(ch, m, path, depth)

    for root in scene.roots:
        visit(root, IDENTITY, "")
    node_pos = {d["guid"]: t.pos for t in things for k, d in t.markers if k == "ainode"}
    for t in things:
        for k, d in t.markers:
            if k == "spawner":
                d["targets"] = [tpos[g] for g in d["points"] if g in tpos] if d["location"] & 2 else []
            elif k == "ainode":
                d["link_pos"] = [node_pos[g] for g in d["links"] if g in node_pos]
    return things


def classify(th: Thing, c: P.Component, files: ModFiles):
    t = c.type_name
    if t in ("ModProp", "ModMeshRenderer"):
        guid = prop(c, "prop" if t == "ModProp" else "mesh", d_ref)
        coll = prop(c, "collisionType", d_i32, 0) if t == "ModProp" else (1 if th.go.component("ModMeshCollider") else 0)
        mesh = files.mesh(guid) if guid else None
        if mesh is None:
            th.kind = "unknown"
            v, tr = _box_mesh(0.5, 0.5, 0.5)
        else:
            v, tr = mesh
        wv = [apply(th.m, p) for p in v]
        th.tris3 = [(wv[a], wv[b], wv[c_]) for a, b, c_ in tr]
        xs, ys, zs = zip(*wv)
        th.aabb = ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))
        if th.kind != "unknown":
            if coll == 0:
                th.kind = "decor"
            elif th.go.layer == LAYER_WORLD_GROUND:
                th.kind = "floor"
            else:
                th.kind = "wall"   # уточняется в analyse(): низкое — «low» (перепрыгиваемое)
        th.collides = coll != 0
        tint = prop(c, "tintColor", lambda r: struct.unpack("<ffff", r[:16]), None) if t == "ModProp" else None
        th.tint = tuple(int(255 * max(0.0, min(1.0, v))) for v in tint[:3]) if tint and min(tint[:3]) < 0.99 else None
    elif t == "ModTrigger":
        acts = []
        for name in ("OnEnterActions", "OnStayActions", "OnHitActions"):
            acts += prop(c, name, d_trigger_actions, []) or []
        th.markers.append(("trigger", {"shape": prop(c, "TriggerShape", d_i32, 1), "size": prop(c, "Size", d_vec3, (1, 1, 1)),
                                       "center": prop(c, "Center", d_vec3, (0, 0, 0)), "radius": prop(c, "Radius", d_f32, 0.5),
                                       "height": prop(c, "Height", d_f32, 2.0), "actions": acts}))
    elif t == "ModPlayerSpawn":
        th.markers.append(("spawn", {"usage": prop(c, "SpawnUsageType", d_i32, 3), "shape": prop(c, "SpawnShape", d_i32, 0),
                                     "radius": prop(c, "Radius", d_f32, 5.0), "line": prop(c, "LineLength", d_f32, 5.0)}))
    elif t == "ModSpawner":
        th.markers.append(("spawner", {"points": prop(c, "SpawnPoints", d_ref_array, []), "location": prop(c, "LocationType", d_i32, 1)}))
    elif t == "ModItem":
        th.markers.append(("item", {}))
    elif t == "ModWater":
        th.markers.append(("water", {"w": prop(c, "Width", d_i32, 20), "h": prop(c, "Height", d_i32, 20), "cell": prop(c, "CellSize", d_f32, 1.0)}))
    elif t == "ModMover":
        th.markers.append(("mover", {"speed": prop(c, "Speed", d_f32, 0.0), "rot": prop(c, "RotationSpeed", d_f32, 0.0),
                                     "axis": prop(c, "RotationAxisType", d_i32, 1)}))
    elif t == "ModAINavigation":
        th.markers.append(("ainode", {"guid": c.guid, "links": prop(c, "ConnectedNodes", d_ref_array, []),
                                      "goal": prop(c, "IsAIGoal", d_bool, False)}))
    elif t == "ModSimpleAnimator":
        th.markers.append(("animator", {"anims": prop(c, "Animations", d_animations, [])}))


def trigger_polys(th: Thing, data):
    """Многоугольник триггера в плане и вертикальный диапазон (мировые)."""
    cx, cy, cz = data["center"]
    if data["shape"] == 1:  # Box
        sx, sy, sz = data["size"]
        pts = [apply(th.m, (cx + dx * sx / 2, cy + dy * sy / 2, cz + dz * sz / 2)) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
    else:                   # Sphere / Capsule / Custom — круг радиуса Radius
        r = data["radius"]
        h = data["height"] / 2 if data["shape"] == 3 else r
        pts = [apply(th.m, (cx + r * math.cos(a), cy + dy * h, cz + r * math.sin(a)))
               for a in [i * math.pi / 8 for i in range(16)] for dy in (-1, 1)]
    ys = [p[1] for p in pts]
    return hull([(p[0], p[2]) for p in pts]), (min(ys), max(ys))


def trigger_role(actions):
    if A_KILL in actions or A_DAMAGE in actions:
        return "kill"
    if A_VELOCITY in actions or A_GRAVITY in actions or A_MODIFY in actions:
        return "velocity"
    return "trigger"


def spawn_points(th: Thing, data):
    if data["shape"] == 2:   # Circle
        return [apply(th.m, (data["radius"] * math.cos(a), 0, data["radius"] * math.sin(a))) for a in [i * math.pi / 4 for i in range(8)]]
    if data["shape"] == 1:   # Line — вдоль локальной X (по вики ориентация не описана)
        L = data["line"]
        return [apply(th.m, (-L / 2 + L * i / 7, 0, 0)) for i in range(8)]
    return [th.pos]


def water_poly(th: Thing, data):
    w, h = data["w"] * data["cell"], data["h"] * data["cell"]
    return [(p[0], p[2]) for p in (apply(th.m, q) for q in ((0, 0, 0), (w, 0, 0), (w, 0, h), (0, 0, h)))]


# ---------------------------------------------------------------- геометрия 2D

def hull(pts):
    pts = sorted(set((round(x, 4), round(y, 4)) for x, y in pts))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def tri_spans(p0, p1, p2, h):
    """Сканлайн: для треугольника в пиксельных координатах отдаёт (y, x0, x1) включительно."""
    ys = [p0[1], p1[1], p2[1]]
    y_start, y_end = max(0, math.ceil(min(ys) - 0.5)), min(h - 1, math.floor(max(ys) - 0.5))
    edges = ((p0, p1), (p1, p2), (p2, p0))
    for y in range(y_start, y_end + 1):
        yc = y + 0.5
        xs = []
        for a, b in edges:
            if (a[1] <= yc < b[1]) or (b[1] <= yc < a[1]):
                xs.append(a[0] + (yc - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
        if len(xs) >= 2:
            x0, x1 = math.ceil(min(xs) - 0.5), math.floor(max(xs) - 0.5)
            if x1 >= x0:
                yield y, x0, x1


def poly_spans(poly, h):
    for i in range(1, len(poly) - 1):
        yield from tri_spans(poly[0], poly[i], poly[i + 1], h)


# ---------------------------------------------------------------- растр и PNG

FONT = {  # 3×5, строки сверху вниз, биты слева направо
    "0": (7, 5, 5, 5, 7), "1": (2, 6, 2, 2, 7), "2": (7, 1, 7, 4, 7), "3": (7, 1, 7, 1, 7), "4": (5, 5, 7, 1, 1),
    "5": (7, 4, 7, 1, 7), "6": (7, 4, 7, 5, 7), "7": (7, 1, 1, 1, 1), "8": (7, 5, 7, 5, 7), "9": (7, 5, 7, 1, 7),
    "-": (0, 0, 7, 0, 0), "m": (0, 0, 7, 7, 5),
}


class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.buf = bytearray(bytes(bg) * (w * h))

    def span(self, y, x0, x1, color):
        x0, x1 = max(0, x0), min(self.w - 1, x1)
        if 0 <= y < self.h and x1 >= x0:
            i = (y * self.w + x0) * 3
            self.buf[i:i + (x1 - x0 + 1) * 3] = bytes(color) * (x1 - x0 + 1)

    def blend_span(self, y, x0, x1, color, a):
        x0, x1 = max(0, x0), min(self.w - 1, x1)
        if not (0 <= y < self.h):
            return
        for x in range(x0, x1 + 1):
            i = (y * self.w + x) * 3
            for k in range(3):
                self.buf[i + k] = int(self.buf[i + k] * (1 - a) + color[k] * a)

    def px(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i:i + 3] = bytes(color)

    def line(self, a, b, color, width=1):
        (x0, y0), (x1, y1) = a, b
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        r = width // 2
        for i in range(n + 1):
            t = i / n
            x, y = int(round(x0 + (x1 - x0) * t)), int(round(y0 + (y1 - y0) * t))
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    self.px(x + dx, y + dy, color)

    def poly_outline(self, poly, color, width=1, dash=0):
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            if dash:
                n = max(1, int(math.dist(a, b) / dash))
                for k in range(0, n, 2):
                    self.line((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n),
                              (a[0] + (b[0] - a[0]) * (k + 1) / n, a[1] + (b[1] - a[1]) * (k + 1) / n), color, width)
            else:
                self.line(a, b, color, width)

    def disk(self, c, r, color):
        for y in range(int(c[1] - r), int(c[1] + r) + 1):
            dy = y + 0.5 - c[1]
            if abs(dy) <= r:
                dx = math.sqrt(r * r - dy * dy)
                self.span(y, int(c[0] - dx), int(c[0] + dx), color)

    def circle(self, c, r, color, width=1):
        n = max(16, int(r * 2))
        pts = [(c[0] + r * math.cos(2 * math.pi * i / n), c[1] + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
        self.poly_outline(pts, color, width)

    def text(self, x, y, s, color=(255, 255, 255), scale=2):
        for pass_color, off in (((0, 0, 0), ((-1, 0), (1, 0), (0, -1), (0, 1))), (color, ((0, 0),))):
            cx = x
            for ch in s:
                rows = FONT.get(ch)
                if rows:
                    for ry, bits in enumerate(rows):
                        for rx in range(3):
                            if bits >> (2 - rx) & 1:
                                for ox, oy in off:
                                    for sx in range(scale):
                                        for sy in range(scale):
                                            self.px(cx + rx * scale + sx + ox, y + ry * scale + sy + oy, pass_color)
                cx += 4 * scale

    def save(self, path):
        raw = bytearray()
        row = self.w * 3
        for y in range(self.h):
            raw.append(0)
            raw += self.buf[y * row:(y + 1) * row]

        def chunk(tag, data):
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0))
        png += chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b"")
        with open(path, "wb") as fh:
            fh.write(png)


def shade(color, k):
    return tuple(max(0, min(255, int(c * k))) for c in color)


class View:
    """Отображение мировых XZ (или XY для разреза) в пиксели."""

    def __init__(self, x0, x1, y0, y1, ppm):
        self.x0, self.y1, self.ppm = x0, y1, ppm
        self.w, self.h = int((x1 - x0) * ppm) + 1, int((y1 - y0) * ppm) + 1

    def __call__(self, x, y):
        return ((x - self.x0) * self.ppm, (self.y1 - y) * self.ppm)


# ---------------------------------------------------------------- анализ

class Grid:
    """Маска пола с шагом res: 0 вне пола, 1 проходимо, 2 стена, 3 опасность, 4 вода, 5 низкое препятствие,
    6 зона триггера скорости (проходима, но прерывает пробег и пустую площадку)."""

    def __init__(self, bounds, res):
        self.x0, self.z0, x1, z1 = bounds
        self.res = res
        self.w, self.h = int(math.ceil((x1 - self.x0) / res)), int(math.ceil((z1 - self.z0) / res))
        self.cells = bytearray(self.w * self.h)

    def to_px(self, x, z): return ((x - self.x0) / self.res, (z - self.z0) / self.res)
    def center(self, i, j): return (self.x0 + (i + 0.5) * self.res, self.z0 + (j + 0.5) * self.res)

    def fill(self, poly_world, value, only_on=None):
        poly = [self.to_px(x, z) for x, z in poly_world]
        for y, a, b in poly_spans(poly, self.h):
            for x in range(max(0, a), min(self.w - 1, b) + 1):
                k = y * self.w + x
                if only_on is None or self.cells[k] in only_on:
                    self.cells[k] = value

    def stroke(self, a, b, value, only_on):
        (ax, az), (bx, bz) = self.to_px(*a), self.to_px(*b)
        n = int(max(abs(bx - ax), abs(bz - az)) * 2) + 1
        for i in range(n + 1):
            x, y = int(ax + (bx - ax) * i / n), int(az + (bz - az) * i / n)
            if 0 <= x < self.w and 0 <= y < self.h and self.cells[y * self.w + x] in only_on:
                self.cells[y * self.w + x] = value


def read_settings(mod_dir):
    path = os.path.join(mod_dir, "Data", "ModSettings.json")
    try:
        d = json.load(open(path, encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001
        return {}, {}
    return d.get("SimpleMinigameSettings", {}), d.get("SimpleModPlayerSettings", {})


def nav_edges(things):
    """Рёбра графа ботов: (откуда, куда) мировые позиции; связь направленная, как ConnectedNodes."""
    return [(t.pos, q) for t in things for k, d in t.markers if k == "ainode" for q in d.get("link_pos", [])]


def nav_report(things, grid, floor_y):
    nodes = [(t, d) for t in things for k, d in t.markers if k == "ainode"]
    if not nodes:
        return ["Сетка ботов: нет (боты бегут к цели по прямой)"]
    edges = nav_edges(things)
    bad = []
    for a, b in edges:
        if max(a[1], b[1]) > floor_y + 1.2:   # ребро на крышу или с крыши — полёт с батута или спрыгивание, не проверяем
            continue
        n = int(math.dist((a[0], a[2]), (b[0], b[2])) / (grid.res / 2)) + 1
        for i in range(1, n):
            x, z = a[0] + (b[0] - a[0]) * i / n, a[2] + (b[2] - a[2]) * i / n
            gi, gj = int((x - grid.x0) / grid.res), int((z - grid.z0) / grid.res)
            if 0 <= gi < grid.w and 0 <= gj < grid.h and grid.cells[gj * grid.w + gi] in (2, 3):
                bad.append(f"({a[0]:.1f}, {a[2]:.1f})→({b[0]:.1f}, {b[2]:.1f})")
                break
    linked_in = {(round(q[0], 2), round(q[2], 2)) for _, q in edges}
    orphans = sum(1 for t, d in nodes if not d.get("link_pos") and (round(t.pos[0], 2), round(t.pos[2], 2)) not in linked_in)
    goals = sum(1 for _, d in nodes if d.get("goal"))
    line = (f"Сетка ботов: {len(nodes)} узлов, {len(edges)} направленных связей, без связей {orphans}"
            + (f", целей Is AI Goal {goals} (все боты пойдут к первой!)" if goals else ""))
    out = [line]
    if bad:
        out.append(f"  связи по полу сквозь стену или опасность: {len(bad)} — " + ", ".join(bad[:8]) + (" …" if len(bad) > 8 else ""))
    return out


def motion_summary(things):
    groups = {}
    for t in things:
        for k, d in t.markers:
            if k in ("mover", "animator"):
                desc = ((", ".join(d.get("anims") or []) or "анимация") if k == "animator" else
                        " ".join(x for x in (f"{d['speed']:.1f} м/с" if d.get("speed") else "",
                                             f"вращение {d['rot']:.0f}°/с" if d.get("rot") else "") if x) or "стоит")
                stem = t.path.split("/")[-1].rstrip("0123456789").rstrip("_ ")
                groups.setdefault((stem, desc), []).append(t)
    if not groups:
        return "Движется: ничего (нет Mover / Simple Animator)"
    n = sum(len(v) for v in groups.values())
    return f"Движется ({n}): " + "; ".join(f"{stem} ×{len(ts)} — {desc}" if len(ts) > 1 else f"{stem} — {desc}"
                                         for (stem, desc), ts in sorted(groups.items(), key=lambda kv: -len(kv[1])))


def inventory(things, L, speed):
    """Сцена без распознанного пола (встроенные props без мешей): только счёт и разброс по позициям."""
    props = [t for t in things if t.aabb]
    if not props:
        L.append("Props нет.")
        return
    xs, ys, zs = (sorted(t.pos[i] for t in props) for i in range(3))
    q = lambda v, f: v[min(len(v) - 1, int(f * len(v)))]  # noqa: E731
    w, d = q(xs, 0.95) - q(xs, 0.05), q(zs, 0.95) - q(zs, 0.05)
    area = max(1.0, w * d)
    roles = {}
    for t in things:
        for k, dt in t.markers:
            r = trigger_role(dt["actions"]) if k == "trigger" else ("spawn" if dt["usage"] & 1 else "respawn") if k == "spawn" else k
            roles[r] = roles.get(r, 0) + 1
    L.append("Пол не распознан (встроенные props без меша или нет слоя WorldGround с коллизией) — метрики пола пропущены, ниже инвентарь.")
    L.append(f"Ядро сцены (5–95% позиций props): {w:.0f} × {d:.0f} м ≈ {area:.0f} м², {max(w, d) / speed:.1f} с бега по длинной стороне")
    L.append(f"Props: {len(props)} (с коллизией {sum(1 for t in props if getattr(t, 'collides', False))}) — "
             f"{100 * len(props) / area:.1f} на 100 м² ядра; перепад высот pivot: {q(ys, 0.05):.1f}..{q(ys, 0.95):.1f} м")
    L.append("Маркеры: " + ", ".join(f"{k} {v}" for k, v in sorted(roles.items(), key=lambda kv: -kv[1])))
    L.append(motion_summary(things))


def analyse(things, mg, ps, cell):
    floors = [t for t in things if t.kind == "floor"]
    out = {"lines": [], "cellmap": [], "empty_cells": []}
    L = out["lines"]
    speed = ps.get("movementSpeed", 6.0)
    jump_v, g = ps.get("jumpSpeed", 7.0), ps.get("playerGravity", 25.0)
    step = ps.get("stepOffset", 0.2)
    jump_h = jump_v * jump_v / (2 * g) if ps.get("canJump", True) else 0.0
    air = 2 * jump_v / g
    out["jump_h"] = jump_h
    jump_txt = f"прыжок {jump_h:.2f} м вверх, ≈{speed * air:.1f} м в длину" if jump_h else "прыжок выключен"
    L.append(f"Движение (ModSettings): бег {speed:.1f} м/с; {jump_txt}; ступенька {step:.2f} м")
    if mg:
        pt = mg.get("ChosenPlayerType", 0)
        L.append(f"Раунд: {mg.get('RoundDuration', '?')} с × {mg.get('NumberOfRounds', '?')}; "
                 f"тип игрока {['ThirdPerson', 'TopDown', 'TwinStick'][pt] if pt in (0, 1, 2) else pt}")

    if floors:
        xs = [p for t in floors for p in (t.aabb[0][0], t.aabb[1][0])]
        zs = [p for t in floors for p in (t.aabb[0][2], t.aabb[1][2])]
        floor_y = max(t.aabb[1][1] for t in floors)
        bounds = (min(xs), min(zs), max(xs), max(zs))
    else:
        pts = [t.pos for t in things if t.markers] or [t.pos for t in things]
        bounds = (min(p[0] for p in pts) - 2, min(p[2] for p in pts) - 2, max(p[0] for p in pts) + 2, max(p[2] for p in pts) + 2)
        out["bounds"], out["floor_y"] = bounds, 0.0
        inventory(things, L, speed)
        return out
    out["bounds"], out["floor_y"] = bounds, floor_y
    fw, fd = bounds[2] - bounds[0], bounds[3] - bounds[1]

    # роли препятствий по высоте
    for t in things:
        if t.kind == "wall":
            lo, hi = t.aabb[0][1], t.aabb[1][1]
            if hi <= floor_y + step or lo >= floor_y + HEAD:
                t.kind = "decor_high" if lo >= floor_y + HEAD else "decor"
            elif hi <= floor_y + jump_h * 0.9:
                t.kind = "low"

    grid = Grid(bounds, 0.25)
    for t in floors:
        for tri in t.tris3:
            grid.fill([(p[0], p[2]) for p in tri], 1, only_on=(0,))
    for t in things:
        for kind, data in t.markers:
            if kind == "water":
                grid.fill(water_poly(t, data), 4, only_on=(1,))
    for t in things:
        for kind, data in t.markers:
            if kind == "trigger" and trigger_role(data["actions"]) == "kill":
                poly, (lo, hi) = trigger_polys(t, data)
                if hi >= floor_y - 1.0 and lo <= floor_y + HEAD:
                    grid.fill(poly, 3, only_on=(1, 4))
    for t in things:
        for kind, data in t.markers:
            if kind == "trigger" and trigger_role(data["actions"]) == "velocity":
                poly, (lo, hi) = trigger_polys(t, data)
                if hi >= floor_y - 1.0 and lo <= floor_y + HEAD:
                    grid.fill(poly, 6, only_on=(1, 4))
    for t in things:
        if t.kind in ("wall", "low"):
            v = 2 if t.kind == "wall" else 5
            for tri in t.tris3:
                ys = [p[1] for p in tri]
                if max(ys) < floor_y + step or min(ys) > floor_y + HEAD:
                    continue
                flat = [(p[0], p[2]) for p in tri]
                grid.fill(flat, v, only_on=(1, 3, 4, 5, 6))
                for i in range(3):
                    grid.stroke(flat[i], flat[(i + 1) % 3], v, only_on=(1, 3, 4, 5, 6))
    out["grid"] = grid

    total = sum(1 for c in grid.cells if c)
    cnt = {v: sum(1 for c in grid.cells if c == v) for v in (1, 2, 3, 4, 5, 6)}
    pct = lambda v: 100.0 * cnt[v] / total if total else 0.0  # noqa: E731

    L.insert(0, f"Пол: {fw:.1f} × {fd:.1f} м по габаритам, площадь пола {total * 0.0625:.0f} м², высота пола {floor_y:.2f}; "
             f"диагональ {math.hypot(fw, fd):.0f} м ≈ {math.hypot(fw, fd) / speed:.1f} с бега")
    L.append(f"Занятость пола: стены {pct(2):.1f}%, низкие (перепрыгиваемые) {pct(5):.1f}%, опасность {pct(3):.1f}%, вода {pct(4):.1f}%, ускорители {pct(6):.1f}%, свободно {pct(1):.1f}%")

    # связность: BFS от стартовых спавнов по проходимым клеткам (1 и 4)
    starts = []
    for t in things:
        for kind, data in t.markers:
            if kind == "spawn" and data["usage"] & 1:
                starts += spawn_points(t, data)
    passable = (1, 4, 6)
    seen = bytearray(grid.w * grid.h)
    dq = []
    for p in starts:
        i, j = int((p[0] - grid.x0) / grid.res), int((p[2] - grid.z0) / grid.res)
        if 0 <= i < grid.w and 0 <= j < grid.h and grid.cells[j * grid.w + i] in passable:
            seen[j * grid.w + i] = 1
            dq.append(j * grid.w + i)
    while dq:
        k = dq.pop()
        x, y = k % grid.w, k // grid.w
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < grid.w and 0 <= ny < grid.h:
                n = ny * grid.w + nx
                if not seen[n] and grid.cells[n] in passable:
                    seen[n] = 1
                    dq.append(n)
    walk = sum(1 for c in grid.cells if c in passable)
    reach = sum(seen)
    if not reach:   # нет стартовых спавнов на полу — считаем весь проходимый пол
        seen = bytearray(1 if c in passable else 0 for c in grid.cells)
    if starts:
        L.append(f"Связность: из стартовых спавнов пешком достижимо {100.0 * reach / walk if walk else 0:.0f}% проходимой площади "
                 f"(без прыжков и jump pad)")

    # самая большая пустая площадка: дистанция до непроходимого (chamfer 3-4)
    INF = 10 ** 9
    dist = [0 if not (grid.cells[k] == 1 and seen[k]) else INF for k in range(grid.w * grid.h)]
    for y in range(grid.h):
        for x in range(grid.w):
            k = y * grid.w + x
            if dist[k]:
                if x == 0 or y == 0 or x == grid.w - 1 or y == grid.h - 1:
                    dist[k] = 3
                    continue
                dist[k] = min(dist[k], dist[k - 1] + 3, dist[k - grid.w] + 3, dist[k - grid.w - 1] + 4, dist[k - grid.w + 1] + 4)
    for y in range(grid.h - 1, -1, -1):
        for x in range(grid.w - 1, -1, -1):
            k = y * grid.w + x
            if dist[k] and 0 < x < grid.w - 1 and 0 < y < grid.h - 1:
                dist[k] = min(dist[k], dist[k + 1] + 3, dist[k + grid.w] + 3, dist[k + grid.w + 1] + 4, dist[k + grid.w - 1] + 4)
    best = max(range(len(dist)), key=lambda k: dist[k]) if dist else 0
    r_open = dist[best] / 3 * grid.res if dist else 0
    cx, cz = grid.center(best % grid.w, best // grid.w)
    out["open"] = (cx, cz, r_open)
    out["seen"], out["dist"] = seen, dist
    L.append(f"Самая большая пустая площадка: круг радиусом {r_open:.1f} м с центром ({cx:.1f}, {cz:.1f}) — "
             f"{r_open / speed:.1f} с бега от края до центра")

    # самый длинный прямой пробег по осям: клетки, от которых до помехи не меньше радиуса игрока
    clear = PLAYER_R / grid.res * 3
    def longest(axis):
        best_len, where = 0, None
        rng_outer = range(grid.h) if axis == "x" else range(grid.w)
        for o in rng_outer:
            run = 0
            rng_inner = range(grid.w) if axis == "x" else range(grid.h)
            for i in rng_inner:
                k = o * grid.w + i if axis == "x" else i * grid.w + o
                run = run + 1 if grid.cells[k] == 1 and seen[k] and dist[k] >= clear else 0
                if run > best_len:
                    best_len, where = run, o
        return best_len * grid.res, (grid.z0 if axis == "x" else grid.x0) + ((where or 0) + 0.5) * grid.res
    lx, at_z = longest("x")
    lz, at_x = longest("z")
    L.append(f"Самый длинный прямой пробег без помех (игрок радиусом {PLAYER_R} м): {lx:.0f} м вдоль X (z={at_z:.1f}), {lz:.0f} м вдоль Z (x={at_x:.1f}) — "
             f"{max(lx, lz) / speed:.1f} с бега")

    # точки интереса на полу
    def on_floor(p): return bounds[0] <= p[0] <= bounds[2] and bounds[1] <= p[2] <= bounds[3]
    interest = []
    for t in things:
        for kind, data in t.markers:
            if kind == "trigger":
                poly, (lo, hi) = trigger_polys(t, data)
                if hi >= floor_y - 1.0 and lo <= floor_y + HEAD + 3:
                    cxp = sum(p[0] for p in poly) / len(poly)
                    czp = sum(p[1] for p in poly) / len(poly)
                    interest.append((cxp, czp, "trigger"))
            elif kind == "spawner":   # OnTargets — каждая точка из списка; иначе сам спавнер
                for p in data.get("targets") or [t.pos]:
                    if on_floor(p):   # билет выше пола (на крыше) пешком не взять — в честность старта не идёт
                        interest.append((p[0], p[2], kind if p[1] < floor_y + 1.2 else "spawner_high"))
            elif kind in ("item", "water") and on_floor(t.pos):
                interest.append((t.pos[0], t.pos[2], kind))
            elif kind in ("mover", "animator") and t.aabb and on_floor(t.pos) and t.aabb[0][1] < floor_y + HEAD:
                interest.append((t.pos[0], t.pos[2], kind))
    area = total * 0.0625 or 1
    def perimeter(p): return min(p[0] - bounds[0], bounds[2] - p[0], p[2] - bounds[1], bounds[3] - p[2]) < 1.5
    n_perim = sum(1 for t in things if t.kind in ("wall", "low") and on_floor(t.pos) and perimeter(t.pos))
    n_wall = sum(1 for t in things if t.kind in ("wall", "low") and on_floor(t.pos)) - n_perim
    n_decor = sum(1 for t in things if t.kind in ("decor", "decor_high") and on_floor(t.pos))
    n_back = sum(1 for t in things if t.kind in ("decor", "decor_high", "unknown") and not on_floor(t.pos))
    L.append(f"Плотность на 100 м² пола: препятствия {100 * n_wall / area:.1f}, декор {100 * n_decor / area:.1f}, "
             f"точки интереса {100 * len(interest) / area:.1f} (всего: {n_wall} / {n_decor} / {len(interest)}); "
             f"ограждение по краю: {n_perim}; объектов задника вне пола: {n_back}")

    # путь от спавнов до точек интереса (Дейкстра по сетке, 8 соседей)
    goals = [p for p in interest if p[2] in ("spawner", "item")] or interest   # цели, за которыми бегут
    if starts and goals:
        targets = {}
        for x, z, _ in goals:
            i, j = int((x - grid.x0) / grid.res), int((z - grid.z0) / grid.res)
            if 0 <= i < grid.w and 0 <= j < grid.h:
                targets[j * grid.w + i] = True
        res3, per_spawn = [], []
        for p in starts:
            i, j = int((p[0] - grid.x0) / grid.res), int((p[2] - grid.z0) / grid.res)
            if not (0 <= i < grid.w and 0 <= j < grid.h):
                continue
            k0 = j * grid.w + i
            d = {k0: 0.0}
            pq = [(0.0, k0)]
            found = []
            while pq and len(found) < 3:
                dk, k = heapq.heappop(pq)
                if dk > d.get(k, 1e18):
                    continue
                if k in targets:
                    found.append(dk)
                x, y = k % grid.w, k // grid.w
                for ddx, ddy, w8 in ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)):
                    nx, ny = x + ddx, y + ddy
                    if 0 <= nx < grid.w and 0 <= ny < grid.h:
                        n = ny * grid.w + nx
                        if grid.cells[n] in passable or n in targets:
                            nd = dk + w8 * grid.res
                            if nd < d.get(n, 1e18):
                                d[n] = nd
                                heapq.heappush(pq, (nd, n))
            if found:
                res3.append(sum(found) / len(found))
                per_spawn.append(f"({p[0]:.0f}, {p[2]:.0f}) {res3[-1]:.1f}")
        if res3:
            spread = max(res3) / max(min(res3), 0.01)
            L.append(f"Спавн → 3 ближайшие цели на полу (спавнеры и предметы; если их нет — точки интереса), путь пешком: "
                     f"от {min(res3):.1f} до {max(res3):.1f} м, "
                     f"разброс ×{spread:.2f} — {'честно' if spread <= 1.5 else 'НЕРАВНО'} (порог ×1.5); по спавнам: " + ", ".join(per_spawn))

    # ориентиры
    tall = sorted((t for t in things if t.aabb and t.kind not in ("floor",)), key=lambda t: -t.aabb[1][1])[:6]
    L.append("Ориентиры (самые высокие): " + "; ".join(
        f"{t.path.split('/')[-1]} {t.aabb[1][1] - floor_y:.1f} м в ({t.pos[0]:.0f}, {t.pos[2]:.0f}){'' if on_floor(t.pos) else ' вне пола'}" for t in tall))
    L.append(motion_summary(things))
    L.extend(nav_report(things, grid, floor_y))

    # карта клеток
    n_cx, n_cz = int(math.ceil(fw / cell)), int(math.ceil(fd / cell))
    cells_obj = {}
    for t in things:
        if t.kind in ("wall", "low", "decor", "decor_high") and on_floor(t.pos):
            cells_obj.setdefault((int((t.pos[0] - bounds[0]) // cell), int((t.pos[2] - bounds[1]) // cell)), set()).add("o" if t.kind in ("wall", "low") else "d")
    for x, z, _ in interest:
        cells_obj.setdefault((int((x - bounds[0]) // cell), int((z - bounds[1]) // cell)), set()).add("*")
    rows = []
    empty = 0
    inside = 0
    for cz_i in range(n_cz - 1, -1, -1):
        row = ""
        for cx_i in range(n_cx):
            sub = [grid.cells[j * grid.w + i]
                   for j in range(int(cz_i * cell / grid.res), min(grid.h, int((cz_i + 1) * cell / grid.res)))
                   for i in range(int(cx_i * cell / grid.res), min(grid.w, int((cx_i + 1) * cell / grid.res)))]
            n_in = sum(1 for c in sub if c)
            if not sub or n_in < 0.3 * len(sub):
                row += " "
                continue
            inside += 1
            s = cells_obj.get((cx_i, cz_i), set())
            if sum(1 for c in sub if c == 2) > 0.6 * n_in:
                row += "#"
            elif sum(1 for c in sub if c == 3) > 0.3 * n_in:
                row += "~"
            elif "*" in s:
                row += "*"
            elif "o" in s or any(c in (2, 5) for c in sub):
                row += "o"
            elif "d" in s:
                row += "d"
            else:
                row += "."
                empty += 1
                out["empty_cells"].append((bounds[0] + cx_i * cell, bounds[1] + cz_i * cell))
        rows.append(row)
    out["cellmap"] = rows
    L.append(f"Пустые клетки {cell:g}×{cell:g} м (ни препятствия, ни декора, ни интереса): {empty} из {inside} "
             f"({100.0 * empty / inside if inside else 0:.0f}%)")
    return out


# ---------------------------------------------------------------- отрисовка

def plan_color(t, ymin, ymax):
    base = COLORS["wall" if t.kind == "wall" else "low" if t.kind == "low" else "floor" if t.kind == "floor" else
                  "unknown" if t.kind == "unknown" else "decor"]
    k = 0.55 + 0.6 * max(0.0, min(1.0, (t.aabb[1][1] - ymin) / max(0.01, ymax - ymin)))
    return shade(base, k)


def draw_plan(things, an, view: View, path, labels=True, cell=4.0, clean=False):
    """clean=True — картинка для превью мода: только геометрия, вода, батуты и билеты, без сетки и служебных пометок."""
    cv = Canvas(view.w, view.h, COLORS["bg"])
    x0w, x1w = view.x0, view.x0 + view.w / view.ppm
    z1w, z0w = view.y1, view.y1 - view.h / view.ppm
    for gx in range(math.floor(x0w), math.ceil(x1w) + 1):
        if gx % 2 == 0 and not clean:
            cv.line(view(gx, z0w), view(gx, z1w), COLORS["grid10" if gx % 10 == 0 else "grid"])
    for gz in range(math.floor(z0w), math.ceil(z1w) + 1):
        if gz % 2 == 0 and not clean:
            cv.line(view(x0w, gz), view(x1w, gz), COLORS["grid10" if gz % 10 == 0 else "grid"])
    solid = [t for t in things if t.aabb]
    ymin, ymax = an["floor_y"], max([t.aabb[1][1] for t in solid] + [an["floor_y"] + 1])
    order = sorted(solid, key=lambda t: t.aabb[1][1])
    for t in order:
        col = plan_color(t, ymin, ymax)
        if clean and getattr(t, "tint", None):   # в превью — настоящий цвет окрашенных props (батуты)
            col = t.tint
        for tri in t.tris3:
            for y, a, b in tri_spans(*[view(p[0], p[2]) for p in tri], view.h):
                cv.span(y, a, b, col)
        if t.kind != "floor":
            h2 = hull([view(p[0], p[2]) for tri in t.tris3 for p in tri])
            if len(h2) >= 2:
                cv.poly_outline(h2, shade(col, 0.6))
    for t in things:
        for kind, data in t.markers:
            if kind == "water":
                poly = [view(*p) for p in water_poly(t, data)]
                for y, a, b in poly_spans(poly, view.h):
                    cv.blend_span(y, a, b, COLORS["water"], 0.6)
                cv.poly_outline(poly, COLORS["water"], 2)
    # сетка ботов: тонкие голубые линии, точка у конца ребра показывает направление
    for a, b in ([] if clean else nav_edges(things)):
        pa, pb = view(a[0], a[2]), view(b[0], b[2])
        cv.line(pa, pb, COLORS["nav"])
        cv.disk((pa[0] + (pb[0] - pa[0]) * 0.8, pa[1] + (pb[1] - pa[1]) * 0.8), 1.5, COLORS["nav"])
    for t in things:
        for kind, data in t.markers:
            if kind == "ainode" and not clean:
                cv.disk(view(t.pos[0], t.pos[2]), 2.5, COLORS["nav"] if t.pos[1] < an["floor_y"] + 1.2 else COLORS["label"])
    # пустые клетки
    for ex, ez in ([] if clean else an["empty_cells"]):
        sq = [view(ex + 0.4, ez + 0.4), view(ex + cell - 0.4, ez + 0.4), view(ex + cell - 0.4, ez + cell - 0.4), view(ex + 0.4, ez + cell - 0.4)]
        cv.poly_outline(sq, COLORS["empty"], 1, dash=4)
    for t in things:
        for kind, data in t.markers:
            if clean and kind not in ("spawner", "item"):
                continue
            if kind == "trigger":
                poly, (lo, hi) = trigger_polys(t, data)
                role = trigger_role(data["actions"])
                pp = [view(*p) for p in poly]
                in_band = hi >= an["floor_y"] - 1.0 and lo <= an["floor_y"] + HEAD + 3
                if role == "kill" and in_band:
                    for y, a, b in poly_spans(pp, view.h):
                        if y % 4 == 0:
                            cv.blend_span(y, a, b, COLORS["kill"], 0.5)
                cv.poly_outline(pp, COLORS[role], 2 if in_band else 1, dash=0 if role != "trigger" and in_band else 5)
            elif kind == "spawn":
                col = COLORS["spawn"] if data["usage"] & 1 else COLORS["respawn"]
                for p in spawn_points(t, data):
                    q = view(p[0], p[2])
                    if data["usage"] & 1:
                        cv.disk(q, max(3, view.ppm * 0.4), col)
                    else:
                        r = max(3, view.ppm * 0.4)
                        cv.poly_outline([(q[0] - r, q[1] - r), (q[0] + r, q[1] - r), (q[0] + r, q[1] + r), (q[0] - r, q[1] + r)], col, 2)
                if data["shape"] == 2:
                    cv.circle(view(t.pos[0], t.pos[2]), data["radius"] * view.ppm, shade(col, 0.6))
            elif kind == "spawner" and data.get("targets"):
                for p in data["targets"]:
                    cv.circle(view(p[0], p[2]), max(4, view.ppm * 0.45), COLORS["spawner"], 2)
            elif kind in ("spawner", "item"):
                q = view(t.pos[0], t.pos[2])
                cv.disk(q, max(2.5, view.ppm * 0.3), COLORS[kind])
                cv.circle(q, max(4, view.ppm * 0.55), shade(COLORS[kind], 0.7))
            elif kind in ("mover", "animator"):
                q = view(t.pos[0], t.pos[2])
                if t.aabb:
                    r = max(t.aabb[1][0] - t.aabb[0][0], t.aabb[1][2] - t.aabb[0][2]) / 2 * view.ppm
                else:
                    r = view.ppm
                cv.circle(q, max(6, r), COLORS["motion"], 2)
    if labels and not clean:
        for t in things:
            if t.label is not None:
                q = view(t.pos[0], t.pos[2])
                cv.text(int(q[0]) + 4, int(q[1]) - 12, str(t.label))
    if clean:
        cv.save(path)
        return
    # шкала 10 м
    cv.line((10, view.h - 12), (10 + 10 * view.ppm, view.h - 12), (255, 255, 255), 3)
    cv.text(14 + int(10 * view.ppm), view.h - 18, "10m")
    cv.save(path)


def draw_elevation(things, an, path, ppm, facing="north"):
    """Разрез-силуэт: что видит игрок, стоящий у края пола и смотрящий через карту.
    facing="north" — взгляд вдоль +Z (в кадре пол и всё, что севернее его южного края), "south" — наоборот, X зеркален."""
    b = an["bounds"]
    north = facing == "north"
    def zc(t): return (t.aabb[0][2] + t.aabb[1][2]) / 2
    solid = [t for t in things if t.aabb and (t.kind == "floor" or ((zc(t) >= b[1] - 1) if north else (zc(t) <= b[3] + 1)))]
    sx = (lambda x: x) if north else (lambda x: -x)
    xs = [sx(p) for t in solid for p in (t.aabb[0][0], t.aabb[1][0])]
    ys = [p for t in solid for p in (t.aabb[0][1], t.aabb[1][1])]
    bx0, bx1 = sorted((sx(b[0]), sx(b[2])))
    x0, x1 = max(min(xs), bx0 - 60), min(max(xs), bx1 + 60)
    y0, y1 = max(min(ys), an["floor_y"] - 3), min(max(ys), an["floor_y"] + 60)
    view = View(x0 - 1, x1 + 1, y0 - 1, y1 + 1, ppm)
    cv = Canvas(view.w, view.h, COLORS["bg"])
    for gy in range(math.floor(y0), math.ceil(y1) + 1):
        cv.line(view(x0, gy), view(x1, gy), COLORS["grid10" if gy % 5 == 0 else "grid"])
    depth = (lambda t: (t.aabb[0][2] + t.aabb[1][2]) / 2) if north else (lambda t: -(t.aabb[0][2] + t.aabb[1][2]) / 2)
    order = sorted(solid, key=lambda t: -depth(t))   # дальние первыми
    dmin, dmax = min(depth(t) for t in solid), max(depth(t) for t in solid)
    for t in order:
        zc = (t.aabb[0][2] + t.aabb[1][2]) / 2
        on_floor = b[1] <= zc <= b[3]
        base = COLORS["wall" if t.kind == "wall" else "low" if t.kind == "low" else "floor" if t.kind == "floor" else
                      "unknown" if t.kind == "unknown" else "decor"]
        k = 1.15 - 0.75 * (depth(t) - dmin) / max(0.01, dmax - dmin)
        col = shade(base, k if on_floor else k * 0.7)
        for tri in t.tris3:
            for y, a, bb in tri_spans(*[view(sx(p[0]), p[1]) for p in tri], view.h):
                cv.span(y, a, bb, col)
        if t.markers and any(k_ in ("mover", "animator") for k_, _ in t.markers):
            (ax, ay, _), (bx_, by, _) = t.aabb
            cv.poly_outline([view(sx(ax), ay), view(sx(bx_), ay), view(sx(bx_), by), view(sx(ax), by)], COLORS["motion"], 1, dash=4)
    fy = an["floor_y"]
    cv.line(view(x0, fy), view(x1, fy), (255, 255, 255))
    cv.line(view(x0, fy + an["jump_h"]), view(x1, fy + an["jump_h"]), COLORS["spawn"])
    cv.line(view(x0, fy + HEAD), view(x1, fy + HEAD), COLORS["respawn"])
    for ex in (bx0, bx1):
        cv.line(view(ex, fy - 0.5), view(ex, fy + 0.5), (255, 255, 255), 3)
    for gy in range(0, int(y1 - fy) + 1, 5):
        q = view(x0, fy + gy)
        cv.text(4, int(q[1]) - 5, f"{gy}m")
    cv.save(path)


def render_preview(mod_dir, path, w=640, h=360, margin=3.0):
    """Превью мода (окно Load a saved mod показывает Data/Preview.jpg 640×360): вид сверху на пол с запасом margin,
    по ширине добран задник до 16:9."""
    _, scene_path = resolve(mod_dir)
    things = collect(P.load(scene_path), ModFiles(mod_dir))
    mg, ps = read_settings(mod_dir)
    an = analyse(things, mg, ps, 4.0)
    b = an["bounds"]
    cx, cz = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    half_h = (b[3] - b[1]) / 2 + margin
    ppm = h / (2 * half_h)
    half_w = w / ppm / 2
    view = View(cx - half_w, cx + half_w, cz - half_h, cz + half_h, ppm)
    view.w, view.h = w, h
    draw_plan(things, an, view, path, labels=False, clean=True)


# ---------------------------------------------------------------- точка входа

def portable_path(path):
    """Путь для отчёта без имени пользователя и диска: от WorkshopMods / InbuiltMods / корня репозитория."""
    full = os.path.normcase(os.path.abspath(path))
    for base, label in ((WORKSHOP, "WorkshopMods"), (INBUILT, "InbuiltMods"), (ROOT, "")):
        b = os.path.normcase(os.path.abspath(base))
        if full.startswith(b + os.sep):
            rel = os.path.relpath(os.path.abspath(path), base).replace(os.sep, "/")
            return f"{label}/{rel}" if label else rel
    return os.path.basename(path)


def resolve(arg):
    cands = [arg, os.path.join(WORKSHOP, arg), os.path.join(INBUILT, arg)]
    for c in cands:
        if os.path.isfile(c) and c.lower().endswith(".scene"):
            return os.path.dirname(os.path.dirname(c)), c
        if os.path.isfile(os.path.join(c, "Data", "MainScene.scene")):
            return c, os.path.join(c, "Data", "MainScene.scene")
    raise SystemExit(f"сцена не найдена: {arg} (искал {cands})")


def assign_labels(things, bounds):
    groups = {}
    for t in things:
        if t.kind == "floor":
            continue
        parent, name = os.path.split(t.path.replace("/", os.sep))
        stem = name.rstrip("0123456789").rstrip("_ ")
        if not t.kind and t.markers and all(k == "ainode" for k, _ in t.markers):
            stem = ""   # все узлы сетки ботов под одним родителем — одной строкой легенды
        groups.setdefault((parent, stem), []).append(t)
    legend, n = [], 0
    for (parent, stem), ts in sorted(groups.items(), key=lambda kv: kv[1][0].path):
        if all(k == "ainode" for t in ts for k, _ in t.markers) and not any(t.kind for t in ts):
            legend.append(f"   {parent.replace(os.sep, '/')}/* ×{len(ts)}  [узлы сетки ботов — голубые точки на плане]")
            continue
        interesting = any(t.markers for t in ts) or any(t.kind in ("wall", "low") for t in ts)
        if not interesting and len(ts) > 3:
            continue
        if len(ts) > 8:  # длинные ряды (забор) — одной строкой без номеров на плане
            xs = [t.pos[0] for t in ts]; zs = [t.pos[2] for t in ts]
            legend.append(f"   {parent.replace(os.sep, '/')}/{stem}* ×{len(ts)}  [{ts[0].kind or ts[0].markers[0][0]}] "
                          f"x {min(xs):.0f}..{max(xs):.0f}, z {min(zs):.0f}..{max(zs):.0f}")
            continue
        for t in ts:
            n += 1
            t.label = n
            roles = [t.kind] if t.kind else []
            for k, d in t.markers:
                roles.append(trigger_role(d["actions"]) if k == "trigger" else
                             ("spawn" if d["usage"] & 1 else "respawn") if k == "spawn" else k)
            size = ""
            if t.aabb:
                (ax, ay, az), (bx, by, bz) = t.aabb
                size = f" {bx - ax:.1f}×{bz - az:.1f} м, h {ay:.1f}..{by:.1f}"
            legend.append(f"{n:>3} {t.path}  [{', '.join(roles)}] ({t.pos[0]:.1f}, {t.pos[1]:.1f}, {t.pos[2]:.1f}){size}")
    return legend


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mod")
    ap.add_argument("--out", default=None, help="папка для plan*.png, elevation.png, plan.txt (по умолчанию ./plan_view/<мод>)")
    ap.add_argument("--cell", type=float, default=4.0, help="размер клетки карты интереса, м")
    ap.add_argument("--px", type=int, default=1000, help="длинная сторона плана в пикселях")
    a = ap.parse_args(argv)

    mod_dir, scene_path = resolve(a.mod)
    name = os.path.basename(os.path.normpath(mod_dir))
    out = a.out or os.path.join("plan_view", name)
    os.makedirs(out, exist_ok=True)
    files = ModFiles(mod_dir)
    things = collect(P.load(scene_path), files)
    mg, ps = read_settings(mod_dir)
    an = analyse(things, mg, ps, a.cell)
    legend = assign_labels(things, an["bounds"])

    b = an["bounds"]
    m = 3.0
    ppm = a.px / max(b[2] - b[0] + 2 * m, b[3] - b[1] + 2 * m)
    draw_plan(things, an, View(b[0] - m, b[2] + m, b[1] - m, b[3] + m, ppm), os.path.join(out, "plan.png"), cell=a.cell)
    pts = [p for t in things if t.aabb for p in (t.aabb[0], t.aabb[1])] + [t.pos for t in things]
    wx0, wx1 = max(min(p[0] for p in pts), -200), min(max(p[0] for p in pts), 200)
    wz0, wz1 = max(min(p[2] for p in pts), -200), min(max(p[2] for p in pts), 200)
    wppm = a.px / max(wx1 - wx0 + 4, wz1 - wz0 + 4)
    draw_plan(things, an, View(wx0 - 2, wx1 + 2, wz0 - 2, wz1 + 2, wppm), os.path.join(out, "plan_wide.png"), labels=False, cell=a.cell)
    for facing in ("north", "south"):
        draw_elevation(things, an, os.path.join(out, f"elevation_{facing}.png"), ppm=max(4.0, min(12.0, a.px / 120)), facing=facing)

    unknown = sum(1 for t in things if t.kind == "unknown")
    text = [f"# План сцены: {name}", f"сцена: {portable_path(scene_path)}", ""]
    text += ["## Метрики", *[f"- {line}" for line in an["lines"]]]
    if unknown:
        text.append(f"- Встроенных props неизвестного размера: {unknown} (на плане серые кубы 1 м; занятость и плотность занижены)")
    text += ["", f"## Карта клеток {a.cell:g} м (север сверху; . пусто, d декор, o препятствие, * интерес, ~ опасность, # стена)", "```",
             *an["cellmap"], "```", "", "## Легенда номеров на plan.png", "```", *legend, "```", "",
             "Цвета: серый — пол; оранжевый — стены (выше прыжка); жёлтый — низкие препятствия (перепрыгнуть); зелёный — декор без коллизии;"
             " ярче = выше. Синий — вода; красная штриховка — триггер с Kill/Damage; оранжевая рамка — триггер скорости/гравитации;"
             " жёлтая пунктирная — прочие триггеры; зелёные точки — стартовые спавны, голубые квадраты — респаун; золотые — спавнеры/предметы;"
             " розовые круги — Mover/Simple Animator; розовый пунктир — пустая клетка. Голубые линии и точки — сетка ботов"
             " (AI Navigation Node; точка ближе к концу линии — направление связи; белые узлы — выше пола, на крышах);"
             " золотые кольца — точки, из которых спавнер выбирает место (OnTargets).",
             "Разрезы (elevation_north/south.png): взгляд от края пола через карту, ближние объекты ярче, розовая рамка — движется; "
             "белая — пол, белые засечки — края пола, зелёная — высота прыжка, голубая — "
             f"граница «мешает идти» ({HEAD} м)."]
    with open(os.path.join(out, "plan.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(text) + "\n")
    print("\n".join(text))
    print(f"\nзаписано: {os.path.abspath(out)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
