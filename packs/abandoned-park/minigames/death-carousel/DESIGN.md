# Death Carousel / Карусель смерти

**Цель:** удержаться на вращающейся карусели над радиоактивным прудом. Кто упал — выбыл. Последний живой побеждает.

| Параметр | Значение |
| --- | --- |
| Тип мода | Minigame, шаблон `Empty` (Minigame) |
| Игроки | 8 спавнов на платформе, баланс 4–6 |
| Длительность | 1 раунд, предохранитель `Round Duration (s)` = 90 |
| End Condition | `RemainingPlayersAlive`, `Players Alive` = 1 |
| Placement Condition | `Last Man Standing` |
| Player Type | `Third Person` |
| Health | `Use Health` выкл.; `Can Respawn` выкл. |
| Punching | вкл., стан вкл. — толкать соседей к краю |

## Сцена

| Объект | Компоненты | Заметки |
| --- | --- | --- |
| `Pond` | `Water Component` + `KillVolume` (`Trigger Component` `Box` под водой) | весь уровень ниже платформы |
| `Carousel` | пустой родитель с `Mover Component` (`Rotation Axis Type` Y, `Rotation Speed` 25 град/с) | вращает всё дочернее |
| `Carousel/Deck` | `Prop Component` (Cylinder, `Collision Type` = `Mesh`, радиус 10, высота 0.5) | пол платформы |
| `Carousel/Pole_*` (8 шт.) | `Prop Component` (тонкий Cylinder, `Collision Type` = `Box`) | шесты лошадок, укрытие от толчков |
| `Carousel/Horse_*` (8 шт.) | `Prop Component` (`horse.obj`, `Collision Type` = `Box`) | лошадки, одна без головы |
| `Carousel/Spawn_*` (8 шт.) | `Player Spawn Component` (`Point`, `InitialSpawn`) | у шестов |
| `Carousel/Roof` | `Prop Component` (`carousel_roof.obj`, без коллизии) | ржавая крыша |
| `RingA` | пустой, **выключен** при старте; 4 дочерних `Sweeper_*` | фаза 2 |
| `RingA/Sweeper_*` | `Prop Component` (длинный Cube, `Collision Type` = `Box`) под родителем-осью с `Mover Component` (`Rotation Axis` Y, `Rotation Speed` −40) | вращаются против карусели, сметают стоящих |
| `RingB` | пустой, выключен; `Spawner Component` | фаза 3 |
| `RingB` → `Spawner Component` | `Type` = `Always Spawn`, `Interval` 2–4 с, `Spawn Count` 1, `Prefabs` = [`Debris`], `Locations` = `OnTargets`, `Spawn Points` = 6 пустых объектов над платформой | обломки |
| `Debris` (префаб) | `Prop Component` (`debris.obj`, `Collision Type` = `Box`) + `Trigger Component` (`On Enter`) + `Logic Component` | см. риски про падение |
| `Director` | `Logic Component` | цепочка эскалации |

## Логика

| Где | Событие | Действия по порядку | Параметры |
| --- | --- | --- | --- |
| `Director` → `Logic Component` | `Start` | 1. `Show Message Action` 2. `Wait Action` 3. `Show Message Action` 4. `Set Active Action` 5. `Wait Action` 6. `Show Message Action` 7. `Set Active Action` 8. `Wait Action` 9. `Set Gravity Action` 10. `Show Message Action` | 1: `All`, «Держись!», 2 с. 2: 20 с. 3: «Метла!», 2 с. 4: `RingA` → `Enabled`. 5: 20 с. 6: «Обломки!», 2 с. 7: `RingB` → `Enabled`. 8: 20 с. 9: гравитация ×0.5 от стандартной (имена полей на вики не названы — проверить). 10: «Невесомость», 2 с |
| `KillVolume` → `Trigger Component` | `On Enter` | 1. `Spawn Effect Action` 2. `Kill/Destroy Action` | `Explosion` на активаторе; убить активатора |
| `Debris` → `Trigger Component` | `On Enter` | 1. `Stun Player Action` 2. `Change Player Velocity Action` | 1: активатор. 2: `Add` 8, `Towards Receiver` — отбросить от обломка |
| `Debris` → `Logic Component` | `Enable` | 1. `Wait Action` 2. `Kill/Destroy Action` | 6 с, затем уничтожить сам обломок, чтобы не копились |
| `Mod Settings` → `Event Triggers` | `On Death` | `Show Message Action` | `All`, «Минус один», 1.5 с (имя игрока подставить нельзя) |

Эскалация сделана линейной цепочкой `Start` → `Wait` → `Set Active`, потому что счётчиков и условий в редакторе нет. Ускорять саму карусель нельзя (`Mover` не управляется действиями) — усложнение идёт за счёт метёлок, обломков и гравитации.

## Ассеты

| Ассет | Тип | Способ |
| --- | --- | --- |
| `horse.obj` | модель | генерировать: лоу-поли лошадка из 5–6 боксов, вариант без головы |
| `carousel_roof.obj` | модель | генерировать: конус из 12 сегментов с рваным краем |
| `debris.obj` | модель | генерировать: неправильный многогранник |
| `carousel_paint.png` | текстура | PIL: красно-жёлтые сектора + ржавые пятна |
| `carousel_music.wav` | звук | синтез: расстроенная шарманка, луп 8 с (фон через `Music & Ambient Sound`) |
| `sweep.wav` | звук | «вжух» для метёлок |

## Риски

- **Главный:** вики не говорит, переносит ли `Mover` стоящих на платформе игроков. Если нет — платформа вращается только визуально, и дизайн ломается. Проверить первым делом; запасной план — платформа статична, а «вращение» дают метёлки `RingA` с самого старта.
- Падение `Debris`: физики свободного падения у props вики не описывает. Запасной вариант: спавнить обломок на уровне платформы и двигать его `Mover Component` горизонтально.
- `Set Gravity Action`: поля направления и величины на вики не названы.
- `Rotation Speed` у `Mover` — локальные оси: `Sweeper` вращать через родителя-ось, иначе он вращается вокруг собственного центра.

## Чеклист плейтеста

1. Стоя на `Deck` без ввода, игрок едет вместе с платформой (ключевая проверка).
2. Шаг с края → пруд → смерть, без респауна.
3. 20 с: сообщение «Метла!», `RingA` включился, метёлки сбивают.
4. 40 с: обломки появляются над платформой с интервалом 2–4 с и исчезают через 6 с.
5. 60 с: гравитация упала, прыжки выше.
6. Остался один → игра закончилась, он первый.
7. Предохранитель 90 с: игра завершается, даже если никто не упал.
