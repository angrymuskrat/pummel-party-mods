# Ticket Rush / Билетики

**Цель:** за 60 секунд собрать больше всех билетов, разбросанных по развалинам парка. Побеждает тот, у кого больше очков.

| Параметр | Значение |
| --- | --- |
| Тип мода | Minigame, шаблон `Minimal Third Person` (или `Empty`) |
| Игроки | 8 спавнов, баланс на 4–6 |
| Длительность | 1 раунд, 60 с |
| End Condition | `Timer`, `Round Duration (s)` = 60 |
| Placement Condition | `Most Points` |
| Player Type | `Third Person` |
| Health | `Use Health` выкл. (любой урон смертелен); `Can Respawn` вкл., `Respawn Time (s)` = 3, `Invulnerable Time (s)` = 2 |
| Punching | вкл. (драка замедляет, но билеты с рук не сбить) |

## Сцена

| Объект | Компоненты | Заметки |
| --- | --- | --- |
| `Ground` | `Prop Component` (Plane, `Collision Type` = `Box`) | бетон, 40×40 |
| `Booth_*` (6–8 шт.) | `Prop Component` (Cube/BevelCube, `Collision Type` = `Box`) | киоски-укрытия, ломают прямую видимость |
| `Pond` | `Water Component` + дочерний `KillVolume` | кислотно-зелёный, по центру |
| `KillVolume` | `Trigger Component` (`Box`, чуть ниже уровня воды) | событие `On Enter` → см. логику |
| `Spawn_Ring` | `Player Spawn Component` (`Spawn Shape` = `Circle`, радиус 15, `Spawn Usage Type` = `InitialSpawn`) | 8 игроков по кругу |
| `Respawn_*` (4 шт.) | `Player Spawn Component` (`Spawn Usage Type` = `Respawn`) | по углам карты |
| `Ticket` (префаб) | корень: `Item Component`; дочерний визуал — `Prop Component` | `Item Type` = `Pickup`, `Unique Pickup` вкл. |
| `TicketSpawner_*` (10–12 шт.) | `Spawner Component` | `Type` = `Spawn On Destruction`, `Delay` 4–8 с (случайный), `Spawn Count` 1, `Prefabs` = [`Ticket`], `Locations` = `OnSpawner` |
| `JumpPad_*` (2–3 шт.) | `Trigger Component` (`Box`) + `Prop Component` (плоский цилиндр) | ускоряют переходы через пруд |
| `FerrisWheel` | `Prop Component` + `Mover Component` (`Rotation Axis` Z, `Rotation Speed` 10) | декор, якорь темы, без коллизии |

## Логика

| Где | Событие | Действия по порядку | Параметры |
| --- | --- | --- | --- |
| `Ticket` → `Item Component` | `'On Pickup' Actions` | 1. `Change Score Action` 2. `Spawn Effect Action` 3. `Play Sound Action` | 1: `Add` 1, `Target` = подобравший игрок (точная подпись пункта выпадающего списка — проверить в редакторе). 2: `Sparkles`, `Target` = предмет. 3: `Clip` = `ticket_pickup.wav`, `Volume` 0.8 |
| `KillVolume` → `Trigger Component` | `On Enter` | 1. `Spawn Effect Action` 2. `Kill/Destroy Action` | 1: `Explosion` на активаторе. 2: `Target` = активатор триггера |
| `JumpPad_*` → `Trigger Component` | `On Enter` | `Change Player Velocity Action` | `Operation` = `Set`, `Speed` 14, `Direction Type` = `Towards Receiver` (пример вики для jump pad; направление проверить в плейтесте) |
| `Mod Settings` → `Event Triggers` | `On Death` | `Show Message Action` | `Message Target` = `Target`, `Message` = «Пруд не прощает», `Duration (s)` 2 |

Эскалации нет: игра намеренно простая, это проба редактора.

## Ассеты

| Ассет | Тип | Способ |
| --- | --- | --- |
| `ticket.obj` | модель | генерировать: плоский прямоугольник 0.6×0.3 с зубчатым краем |
| `booth.obj` | модель | генерировать: бокс с козырьком |
| `ferris_wheel.obj` | модель | генерировать: два кольца из сегментов + 8 спиц + кабинки-боксы |
| `rust_booth.png`, `concrete.png` | текстуры | PIL: шум + полосы ржавчины, 512×512 |
| `ticket_pickup.wav` | звук | синтез: короткий «дзынь» 0.2 с |

Киоски можно заменить встроенными props, если импорт `.obj` задерживает первую сборку.

## Риски

- `Item Type` = `Pickup`: вики говорит, что Pickup нельзя держать; это и нужно. Туториал делал сбор через `Worn` + `Auto Drop After Time` 0 + `Disappear When Dropped`; если Pickup не исчезает после подбора — перейти на схему туториала.
- Респаун предметов через `Spawn On Destruction` предполагает, что подобранный Pickup считается уничтоженным — проверить; иначе `Always Spawn` с `Interval` 6 с и риском накопления объектов.
- Какой `Respawn`-спавн выбирается при нескольких — вики не говорит.
- Сетевая синхронизация подбора не задокументирована; дубли очков при одновременном подборе — смотреть в плейтесте на двух клиентах.

## Чеклист плейтеста

1. Все 8 спавнов стоят над полом, старт без проваливаний.
2. Подбор билета: +1 в UI очков, звук, искры, билет исчез.
3. Через 4–8 с на той же точке появился новый билет.
4. Зайти в пруд → смерть, сообщение, респаун через 3 с на углу.
5. Jump pad перебрасывает через пруд, а не в него.
6. На 60-й секунде игра завершилась, места по очкам.
7. Mod Validator без ошибок; предупреждения записать.
8. После сохранения заглянуть в `WorkshopMods\Ticket Rush\` и записать формат файлов в `PACK.md`.
