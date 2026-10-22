"""Сетка ботов (AI Navigation Node) по карте занятости plan_view: решётка узлов на свободном полу + особые узлы.

Как боты ходят по сетке (SimpleModPlayer.GetPath, ModAINavigation.GetPath, декомпиляция 2026-10-22):
- путь ищется от узла, ближайшего к боту, до узла, ближайшего к цели (просто по расстоянию, без проверки видимости);
- узел «достигнут» в 1.6 м, после последнего узла бот идёт к его точке, а не к самой цели — поэтому узел
  ставится ровно в каждой точке, где появляется билет;
- связи направленные (ConnectedNodes): бот идёт из узла только по его собственному списку.

Особые узлы (specials):
    {"name": ..., "pos": (x, y, z), "kind": "ground"}            точка билета на полу — связь с решёткой в обе стороны
    {"name": ..., "pos": (x, y, z), "kind": "pad"}               батут — только решётка → батут (не транзит)
    {"name": ..., "pos": (x, y, z), "kind": "roof", "pad": i}    крыша — батут i → крыша, крыша → решётка (спрыгнуть)

Использование из build_mod.py: собрать мод без сетки, вызвать generate(папка мода, specials), добавить узлы
через pmgen (obj(...).ai_node(), link_ai_nodes) и записать мод ещё раз.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plan_view as V  # noqa: E402

FLOOR_OK = (1,)          # клетки, по которым идёт связь решётки (без воды, опасности, батутов)
PAD_OK = (1, 6)          # к батуту можно подойти через его зону


def _cell(grid, x, z):
    i, j = int((x - grid.x0) / grid.res), int((z - grid.z0) / grid.res)
    if 0 <= i < grid.w and 0 <= j < grid.h:
        return j * grid.w + i
    return None


def _clear(an, a, b, allowed, clearance, skip_near=None, skip_r=0.8):
    """Отрезок a→b (x, z) идёт по клеткам allowed с запасом clearance м до помех; skip_near — точка, около которой
    (в радиусе skip_r) проверка не делается (сам билет у стойки, сам батут)."""
    grid, dist = an["grid"], an["dist"]
    n = int(math.dist(a, b) / (grid.res / 2)) + 1
    for i in range(n + 1):
        x, z = a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n
        if skip_near and math.dist((x, z), skip_near) < skip_r:
            continue
        k = _cell(grid, x, z)
        if k is None or grid.cells[k] not in allowed:
            return False
        if grid.cells[k] == 1 and dist[k] / 3 * grid.res < clearance:
            return False
    return True


def generate(mod_dir, specials, spacing=3.5, clearance=0.6, link_radius=4.8):
    """Возвращает (nodes, edges, warnings): nodes — [(имя, (x, y, z))], edges — [(i, j)] направленные."""
    _, scene_path = V.resolve(mod_dir)
    things = V.collect(V.P.load(scene_path), V.ModFiles(mod_dir))
    mg, ps = V.read_settings(mod_dir)
    an = V.analyse(things, mg, ps, 4.0)
    grid, seen, dist = an["grid"], an["seen"], an["dist"]
    fy = an["floor_y"]
    x0, z0, x1, z1 = an["bounds"]

    nodes, edges, warnings = [], [], []
    lattice = []
    nx, nz = int((x1 - x0) // spacing), int((z1 - z0) // spacing)
    for i in range(nx + 1):
        for j in range(nz + 1):
            x, z = x0 + spacing / 2 + i * spacing, z0 + spacing / 2 + j * spacing
            k = _cell(grid, x, z)
            if k is not None and grid.cells[k] == 1 and seen[k] and dist[k] / 3 * grid.res >= clearance:
                lattice.append(len(nodes))
                nodes.append((f"Grid_{i}_{j}", (round(x, 2), fy, round(z, 2))))
    xz = lambda n: (nodes[n][1][0], nodes[n][1][2])  # noqa: E731
    for a in lattice:
        for b in lattice:
            if a < b and math.dist(xz(a), xz(b)) <= spacing * 1.5 and _clear(an, xz(a), xz(b), FLOOR_OK, 0.4):
                edges += [(a, b), (b, a)]

    def near_lattice(p, allowed, skip, limit, avoid_pads=False, skip_r=0.8):
        cand = sorted(lattice, key=lambda n: math.dist(p, xz(n)))
        out = []
        for n in cand:
            if math.dist(p, xz(n)) > link_radius:
                break
            ok = _clear(an, xz(n), p, allowed, 0.3, skip_near=skip, skip_r=skip_r)
            if ok and avoid_pads:
                ok = all(grid.cells[k] != 6 for k in (_cell(grid, *xz(n)),) if k is not None)
            if ok:
                out.append(n)
            if len(out) >= limit:
                break
        return out

    index = {}
    for s in specials:
        index[s["name"]] = len(nodes)
        nodes.append((s["name"], tuple(s["pos"])))
    for s in specials:
        me, p = index[s["name"]], (s["pos"][0], s["pos"][2])
        if s["kind"] == "ground":
            links = near_lattice(p, (1, 4), p, 4)
            if not links:
                links = sorted(lattice, key=lambda n: math.dist(p, xz(n)))[:1]
                warnings.append(f"{s['name']}: нет свободного прохода к сетке, связан с ближайшим узлом напрямую")
            for n in links:
                edges += [(n, me), (me, n)]
        elif s["kind"] == "pad":
            links = near_lattice(p, PAD_OK, p, 3, skip_r=1.8)   # зона батута 2.2 м сама по себе «помеха» для запаса
            if not links:
                warnings.append(f"{s['name']}: к батуту не подходит ни один узел сетки")
            edges += [(n, me) for n in links]
        elif s["kind"] == "roof":
            pad = index[s["pad"]]
            edges.append((pad, me))
            # спрыгнуть с крыши — к ближайшим узлам, не через батут (иначе снова подбросит)
            down = [n for n in sorted(lattice, key=lambda n: math.dist(p, xz(n)))
                    if math.dist(p, xz(n)) <= link_radius + 1.5
                    and all(grid.cells[k] != 6 for k in [_cell(grid, *xz(n))] if k is not None)
                    and math.dist(xz(n), (nodes[pad][1][0], nodes[pad][1][2])) > 2.5][:2]
            if not down:
                warnings.append(f"{s['name']}: с крыши некуда спрыгнуть по сетке")
            edges += [(me, n) for n in down]
    return nodes, sorted(set(edges)), warnings
