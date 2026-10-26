"""Скольжение в Tilt House по кадрам: на сколько сносит за крен при разном вводе, что делают прыжок и удар.

Запуск из корня репозитория:  python packs/abandoned-park/minigames/tilt-house/slide.py
Пишет plan/slide.txt. Константы берёт из build_mod.py, поэтому считает то, что собрано.

Модель — горизонталь CharacterMover.CalculateVelocity (декомпиляция 2026-10-25), шаг 1/60 с:
1. velocity += g · playerGravity / 9.81 · dt (SimpleModPlayer.ApplyCustomForces; горизонталь g — боковая тяга P);
2. цель = ввод × бег; темп по оси X и по оси Z свой: Acceleration, если ввод по этой оси есть и скорость не за целью,
   иначе Deceleration (в воздухе оба — midAirMovementAcceleration);
3. шаг = нормаль (цель − скорость) по оси × темп × dt; если шаг не меньше разницы — скорость встаёт ровно на цель.
Не учтено: упор в стену (контроллер скорость не обнуляет — она копится, см. «Упор»), наклон пола (визуальный, 6–9°),
сглаживание склона, сеть. Крен по оси +X; «в гору» — ввод −X.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_mod as B  # noqa: E402

DT = 1 / 60


def step(v, target, push, grounded):
    """Один кадр горизонтали. v, target, push — (x, z)."""
    vx, vz = v[0] + push[0] * DT, v[1] + push[1] * DT
    acc = B.ACCEL if grounded else B.MID_AIR
    dec = B.DECEL if grounded else B.MID_AIR

    def rate(t, s):
        return acc if (not (t < 0 and s < t)) and (not (t > 0 and s > t)) and t != 0 else dec

    dx, dz = target[0] - vx, target[1] - vz
    n = math.hypot(dx, dz) or 1.0
    sx, sz = dx / n * rate(target[0], vx) * DT, dz / n * rate(target[1], vz) * DT
    vx = target[0] if abs(dx) <= abs(sx) else vx + sx
    vz = target[1] if abs(dz) <= abs(sz) else vz + sz
    return vx, vz


def run(push_x, target, seconds, v0=(0.0, 0.0), air_until=0.0):
    """Смещение (x, z) и скорость через seconds. air_until — сколько первых секунд игрок в воздухе."""
    v, x, z, t = v0, 0.0, 0.0, 0.0
    while t < seconds - 1e-9:
        v = step(v, target, (push_x, 0.0), grounded=t >= air_until)
        x, z, t = x + v[0] * DT, z + v[1] * DT, t + DT
    return x, z, v


INPUTS = [("стоит", (0, 0), (0, 0)),
          ("бежит в гору", (-B.RUN, 0), (0, 0)),
          ("бежит в гору с разбега", (-B.RUN, 0), (-B.RUN, 0)),
          ("бежит поперёк", (0, B.RUN), (0, 0)),
          ("в гору по диагонали", (-B.RUN / math.sqrt(2), B.RUN / math.sqrt(2)), (0, 0)),
          ("бежит под гору", (B.RUN, 0), (0, 0))]


def main():
    lines = ["# Скольжение в крене (slide.py)", "",
             f"Игрок: бег {B.RUN:g} м/с, разгон {B.ACCEL:g}, торможение {B.DECEL:g}, в воздухе {B.MID_AIR:g} м/с²; "
             f"крен держится {B.HOLD[False]:g} с (лёгкий) и {B.HOLD[True]:g} с (тяжёлый). Смещение по склону: + — под гору (к красной стене), − — в гору.", ""]
    for heavy in (False, True):
        p = B.P_HEAVY if heavy else B.P_LIGHT
        lines += [f"## {'Тяжёлый' if heavy else 'Лёгкий'} крен: тяга {p:g} м/с², Set Gravity {B.lateral_gravity('E', heavy)}", "",
                  f"| Ввод | через 1 с | через 2 с | к концу крена ({B.HOLD[heavy]:g} с) | скорость к концу | поперёк за крен |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for label, target, v0 in INPUTS:
            cells = [f"{run(p, target, s, v0)[0]:+.1f} м" for s in (1, 2, B.HOLD[heavy])]
            x, z, v = run(p, target, B.HOLD[heavy], v0)
            lines.append(f"| {label} | {' | '.join(cells)} | {v[0]:+.1f} м/с | {z:.1f} м |")
        lines.append("")

    lines += ["## Прыжок в гору с разбега (полёт 2 · 7 / 25 = 0.56 с), смещение за 1 с", "",
              "| Крен | без прыжка | с прыжком | разница |", "| --- | --- | --- | --- |"]
    air = 2 * B.JUMP / B.PLAYER_GRAVITY
    for label, p in (("нет", 0.0), ("лёгкий", B.P_LIGHT), ("тяжёлый", B.P_HEAVY)):
        a = run(p, (-B.RUN, 0), 1.0, (-B.RUN, 0))[0]
        b = run(p, (-B.RUN, 0), 1.0, (-B.RUN, 0), air_until=air)[0]
        lines.append(f"| {label} | {a:+.1f} м | {b:+.1f} м | {b - a:+.1f} м |")

    lines += ["", f"## Удар: {B.PUNCH_PUSH:g} м/с от бьющего + {B.PUNCH_LIFT:g} вверх, получивший потом не жмёт ничего (полёт "
              f"{2 * B.PUNCH_LIFT / B.PLAYER_GRAVITY:.2f} с), смещение за 1.5 с", "",
              "| Крен | удар под гору | удар в гору |", "| --- | --- | --- |"]
    fly = 2 * B.PUNCH_LIFT / B.PLAYER_GRAVITY
    for label, p in (("нет", 0.0), ("лёгкий", B.P_LIGHT), ("тяжёлый", B.P_HEAVY)):
        down = run(p, (0, 0), 1.5, (B.PUNCH_PUSH, 0), air_until=fly)[0]
        up = run(p, (0, 0), 1.5, (-B.PUNCH_PUSH, 0), air_until=fly)[0]
        lines.append(f"| {label} | {down:+.1f} м | {up:+.1f} м |")

    lines += ["", "## Упор в стену под горой (без Leveler)", "",
              "Контроллер при упоре скорость не обнуляет, тяга копится весь крен. Сколько держит у стены после выравнивания:", "",
              "| Крен | скорость в стену к концу | уйти от стены с вводом | без ввода |", "| --- | --- | --- | --- |"]
    for label, heavy in (("лёгкий", False), ("тяжёлый", True)):
        stored = max(0.0, (B.P_HEAVY if heavy else B.P_LIGHT) - B.DECEL) * B.HOLD[heavy]
        lines.append(f"| {label} | {stored:.0f} м/с | {stored / B.ACCEL:.1f} с | {stored / B.DECEL:.1f} с |")
    lines += ["", f"Поэтому Leveler на {B.LEVEL_RESET:g} с при выравнивании умножает скорость каждого в доме на (0, 1, 0)."]

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plan", "slide.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
