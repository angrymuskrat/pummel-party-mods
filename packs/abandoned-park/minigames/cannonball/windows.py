"""Окна попадания Human Cannonball по этапам: какую долю времени вход в пушку даёт попадание.

Запуск из корня репозитория:  python packs/abandoned-park/minigames/cannonball/windows.py
Пишет plan/windows.txt. Константы, полёт и точки плотов берёт из build_mod.py, поэтому считает то, что собрано.

Модель (декомпиляция 2026-10-25): все Simple Animator идут от одних часов — Time.time хоста (у клиентов
SmoothServerTime), слой берёт (t·частота + AnimationOffset) mod 1, TimeOffset компонента — секунды
(SimpleAnimator.UpdateAnimation, SimpleAnimationLayer). Поэтому фаза «ствол — плот» постоянна, если периоды совпадают,
а момент начала этапа на этих часах случаен — окно этапа считается при многих началах, печатаются среднее и худшее.
Допущения: игрок входит в зону ровно когда хочет (без толчков), рулит идеально (подруливание — отрезок ±S поперёк
выстрела, удлинение полёта при руле ~0.7 м не учтено), выстрел — в момент входа. «Без руля» — так стреляет бот.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_mod as B  # noqa: E402


def smooth(u):
    return 3 * u * u - 2 * u ** 3


def swing(u):
    """Кривая anim_swing: −1 → 1 → −1 с плоскими касательными."""
    u %= 1.0
    return -1 + 2 * smooth(u / 0.5) if u < 0.5 else 1 - 2 * smooth((u - 0.5) / 0.5)


def along_line(u):
    """Кривая anim_move_along_line: 0 → 1 → 0 с плоскими касательными."""
    u %= 1.0
    return smooth(u / 0.5) if u < 0.5 else 1 - smooth((u - 0.5) / 0.5)


def raft_x(base_x, drift, far, t):
    amp, period = drift
    if not amp:
        return base_x
    off = period / 2 if far else 0.0
    return base_x - amp + 2 * amp * along_line((t + off) / period)


def hits(cannon, t0, raft_xz, spec, drift, size, far):
    """Можно ли попасть при входе в момент t0: (внешний, яблочко) с рулём и без."""
    fwd, side, T = B.reach(cannon["kind"]), B.flight(B.SHOTS[cannon["kind"]], steer=1.0)[0], B.flight(B.SHOTS[cannon["kind"]])[2]
    th = math.radians(cannon["yaw"] + cannon["amp"] * swing(t0 / cannon["period"] + cannon["phase"]))
    rx, rz = raft_x(raft_xz[0], drift, far, t0 + T), raft_xz[1]
    out = {"outer": False, "bull": False, "bot_outer": False, "bot_bull": False}
    for i in range(-24, 25):
        s = side * i / 24
        px = cannon["x"] + fwd * math.sin(th) + s * math.cos(th)
        pz = B.PIVOT_Z + fwd * math.cos(th) - s * math.sin(th)
        for key, h in (("outer", spec["half"][0] * size), ("bull", spec["half"][2] * size)):
            if abs(px - rx) <= h and abs(pz - rz) <= h:
                out[key] = True
                if i == 0:
                    out["bot_" + key] = True
    return out


def stage_windows(stages=None, starts=24, samples=300):
    """{этап: {пушка: {ключ: (среднее, худшее)}}} — доля времени этапа, когда вход даёт попадание."""
    stages = stages or B.STAGES
    near_l, near_r, far = B.raft_points()
    aim = {"Cannon_W": (near_l, B.NEAR, "near"), "Cannon_E": (near_r, B.NEAR, "near"),
           "Cannon_CW": (far, B.FAR, "far"), "Cannon_CE": (far, B.FAR, "far")}
    res = {}
    for r, st in enumerate(stages):
        res[r] = {}
        for c in B.CANNONS:
            xz, spec, kind = aim[c["name"]]
            per_start = []
            for k in range(starts):
                t_start = 1000.0 + 37.3 * k   # случайные начала этапа на общих часах
                acc = dict.fromkeys(("outer", "bull", "bot_outer", "bot_bull"), 0)
                for i in range(samples):
                    h = hits(c, t_start + B.STAGE_TIME * i / samples, xz, spec, st[kind], st["size"], kind == "far")
                    for key, v in h.items():
                        acc[key] += v
                per_start.append({key: v / samples for key, v in acc.items()})
            res[r][c["name"]] = {key: (sum(p[key] for p in per_start) / starts, min(p[key] for p in per_start))
                                 for key in per_start[0]}
    return res


def report(res):
    lines = ["# Окна попадания по этапам (windows.py)", "",
             f"Доля времени этапа ({B.STAGE_TIME:.0f} с), когда вход в пушку даёт попадание: среднее / худшее из 24 начал этапа.",
             "«С рулём» — идеальное подруливание, «без руля» — бот.", ""]
    for r, st in enumerate(B.STAGES):
        lines.append(f"## Этап {r + 1}: ближние ±{st['near'][0]} м за {st['near'][1]} с, дальний ±{st['far'][0]} м за "
                     f"{st['far'][1]} с, квадраты ×{st['size']}")
        lines.append("| Пушка | внешний, руль | яблочко, руль | внешний, без руля | яблочко, без руля |")
        lines.append("| --- | --- | --- | --- | --- |")
        for name, v in res[r].items():
            cells = [f"{v[k][0]:.0%} / {v[k][1]:.0%}" for k in ("outer", "bull", "bot_outer", "bot_bull")]
            lines.append(f"| {name} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    text = report(stage_windows())
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plan", "windows.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
