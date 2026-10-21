# Coaster Run / Горки без рельс

**Цель:** добежать до финиша по обрушенным американским горкам. Места — по порядку прихода.

| Параметр | Значение |
| --- | --- |
| Тип мода | Minigame, шаблон `Third Person Obstacle Course` (переодеть и заменить препятствия) |
| Игроки | 8 спавнов линией на старте |
| Длительность | 1 раунд, предохранитель `Round Duration (s)` = 120 |
| End Condition | `FinishMinigame` |
| Placement Condition | `Finish Order` |
| Player Type | `Third Person`; прыжки вкл., `Jump Speed` по шаблону |
| Health | `Use Health` выкл.; `Can Respawn` вкл., `Respawn Time (s)` = 2, `Invulnerable Time (s)` = 1 |
| Punching | вкл. (столкнуть соперника в пропасть — часть гонки) |

## Трасса (5 секций, около 90 м)

| Секция | Объекты | Препятствие |
| --- | --- | --- |
| S1 Старт | `Platform_Start` (Cube), `Spawn_Line` (`Player Spawn Component`, `Line`, длина 8, `InitialSpawn`) | — |
| S2 Рельсы | `Rail_*` — узкие балки (Cube 1×0.3×6, `Collision Type` = `Box`) с разрывами 2–3 м | прыжки через разрывы |
| S3 Вагонетки | `Cart_*` (3 шт.): `Prop Component` (`cart.obj`, `Box`) + `Mover Component` (`Direction Type` `Custom`, `Direction` вдоль трассы, `Speed` 6) + `Trigger Component` (`Box`, `On Enter`) + `Logic Component` | едут навстречу, сбивают |
| S4 Петля | `Loop_*` — дуга из 12 плоских сегментов, часть удалена | обход по уцелевшим |
| S5 Финиш | `Platform_Finish`, `FinishTrigger` (`Trigger Component`, `Box`, `One Use Per Player` вкл.) | — |
| Везде | `KillVolume` (`Trigger Component`, `Box` на всю карту ниже трассы) | падение = смерть |
| Чекпоинты | `Respawn_S2`, `Respawn_S3`, `Respawn_S4` (`Player Spawn Component`, `Respawn`) | возврат после падения |
| Декор | `FerrisWheel` (`Mover`), `Mascot_*` (`mascot_headless.obj`), `Pond` (`Water Component`) | якоря темы |

## Логика

| Где | Событие | Действия по порядку | Параметры |
| --- | --- | --- | --- |
| `FinishTrigger` → `Trigger Component` | `On Enter` | 1. `Set Placement Action` 2. `Spawn Effect Action` 3. `Play Sound Action` | 1: активатор. 2: `Confetti`. 3: `finish.wav` |
| `Cart_*` → `Trigger Component` | `On Enter` | 1. `Stun Player Action` 2. `Change Player Velocity Action` | 1: активатор. 2: `Add` 10, `Towards Receiver` (отбросить) |
| `Cart_*` → `Logic Component` | `Timer`, `Interval` 10 с | `Match Transform Action` | `Transform To Match` = пустой маркер `CartStart_*`, `Targets` = вагонетка; возврат в начало секции каждые 10 с |
| `KillVolume` → `Trigger Component` | `On Enter` | `Kill/Destroy Action` | активатор |
| `Mod Settings` → `Event Triggers` | `On Round Start` | `Show Message Action` | `All`, «Рельсов нет. Беги.», 3 с |

Чекпоинты: редактор не даёт «ближайший респаун» — какой из `Respawn`-спавнов выбирается, вики не говорит. Если выбор случайный, оставить один респаун в начале S2 и смириться с откатом; для гонки это честно.

## Ассеты

| Ассет | Тип | Способ |
| --- | --- | --- |
| `cart.obj` | модель | генерировать: бокс с бортами и 4 цилиндра-колеса |
| `rail_segment.obj` | модель | генерировать: балка с двумя рельсами и шпалами |
| `mascot_headless.obj` | модель | генерировать: тело-капсула, руки-цилиндры, без головы |
| `rust_metal.png` | текстура | PIL |
| `finish.wav`, `cart_rumble.wav` | звук | синтез |

## Риски

- Вагонетка после `Match Transform` продолжает ехать в ту же сторону (направление у `Mover` локальное) — ожидаемо, но проверить, что маркер `CartStart_*` повёрнут так же, как вагонетка.
- `Set Placement Action` при `One Use Per Player` — повторный заход в финиш не должен ничего менять; проверить.
- Шаблон `Third Person Obstacle Course` несёт свои `Mod Settings` и объекты; после переодевания пройтись по ним и удалить лишнее.
- Кулаки на узких рельсах могут сделать гонку слишком хаотичной на 6 игроках — если так, выключить `Punching`.

## Чеклист плейтеста

1. Старт: 8 игроков в линию, сообщение на экране.
2. Падение с рельс → смерть → респаун на чекпоинте, не на старте (или на старте, если выбор случайный — записать).
3. Вагонетка сбивает и отбрасывает; через 10 с возвращается в начало секции.
4. Финиш: конфетти, звук, игрок получает место и больше не участвует.
5. Все финишировали → игра завершилась, места по порядку.
6. Предохранитель 120 с срабатывает, если кто-то застрял.
