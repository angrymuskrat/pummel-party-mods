# Каталог логики Pummel Party Mod Editor (events / actions / components)

Источник: официальная вики `https://workshop.pummelparty.com/wiki/Main_Page` (MediaWiki, полный список страниц — `Special:AllPages`, 109 страниц). Собрано 2026‑10‑21. Все английские идентификаторы (имена событий, действий, компонентов, полей, опций) приведены **ровно так, как они написаны на вики**. Там, где вики молчит, это явно отмечено словами «вики не документирует». Ничего не придумано сверх того, что есть на вики; единственное стороннее дополнение — патч‑ноуты 1.13.0 (через SteamDB/веб‑поиск), помечено отдельно.

Важно для проектирования минигр: **в редакторе нет скриптинга, переменных, условий (if/else), счётчиков и математики над произвольными значениями.** Логика — это только «событие → линейный список действий». Всё, что ниже, — полный перечень доступных кирпичиков.

---

## 1. Как устроена логика

Страницы: `/wiki/Event`, `/wiki/Action`, `/wiki/Action_Editor`, `/wiki/Introduction_to_the_Mod_Editor`, `/wiki/Component`, `/wiki/Gameobject`.

- **Gameobject** — объект сцены с именем, слоем (`Layer`: `Default`, `WorldGround`), обязательным `Transform Component` и любыми компонентами. Объекты образуют иерархию (parent/child); дети наследуют позицию/поворот/масштаб. Отключённый объект скрыт и его компоненты не работают.
- **Component** — «piece of logic and functionality added to a gameobject». Добавляется через `Add Component` в `Inspector Window`. Компоненты, которые нельзя добавить, показаны серыми (наведение показывает причину).
- **Event** — «something that can run Actions when triggered». Обычно с префиксом `On` (вики приводит примеры `OnEnter`, `OnStart`, `OnHit`, `OnRespawn`). В инспекторе событие отмечено жёлтой молнией и кнопкой `Edit`. События живут (а) в компонентах (`Logic Component`, `Trigger Component`, `Item Component`, `Weapon Component`, `Board Space Event Component`) и (б) в настройках мода: `Mod Settings > Player Settings > Event Triggers` (только минигры).
- **Action** — «a single block of functionality or logic that can be invoked by an Event».
- **Action Editor** — окно, открывающееся кнопкой `Edit` на событии. Правила выполнения (цитаты со страницы `/wiki/Action_Editor`):
  - «Actions are executed from top to bottom».
  - Почти все действия мгновенные; только `Wait Action` задерживает всё, что ниже него. Можно ставить несколько `Wait Action` в одном списке.
  - `Display Popup Action` (board) тоже приостанавливает выполнение: действия ниже него ждут закрытия попапа и завершения всех вложенных списков. Вложенные списки (outcomes попапа) навигируются «хлебными крошками» (breadcrumb trail) вверху окна.
  - Часть действий доступна только в Board‑модах, часть — только в Minigame‑модах. «Board Actions are limited to events provided by the Board Space Event Component».
- **Target действия.** У большинства действий есть поле `Target`/`Targets`. Вики нигде не приводит полного списка вариантов этого выпадающего списка. По отдельным страницам достоверно известны: `Advanced` (список произвольных объектов/компонентов; упоминается в `Spawn Prefab`, `Play Sound`, `Play Tween Animation`, во всех board‑действиях), `This Player` и `This Board Space` (board‑действия), `This (Destructable)` и `Hitter` (пример на устаревшей странице `Destructible Component`), «activator of the trigger» (описательно на `Trigger Component`), «the activating player» (`Set Placement Action`). Точные подписи всех пунктов выпадающего списка в редакторе вики **не документирует** — проверять в редакторе.
- **Сеть.** Вики не описывает сетевой код вовсе: нет ни слова о синхронизации, авторитете хоста, RPC и т.п. Из `Minigame Mod`/`Creating Your First Mod` известно только, что хост лобби раздаёт моды остальным игрокам автоматически. Практический вывод: мультиплеер обрабатывается движком прозрачно, модмейкер ничего не настраивает. Единственная оговорка о недетерминизме — событие `Update` в `Logic Component` «не согласовано между игроками из‑за разного FPS», вики рекомендует `Timer`.
- **Тип мода** (`Minigame Mod` / `Board Mod`) задаётся шаблоном при создании и **не меняется** потом. Board‑мод не содержит minigame‑функциональности и наоборот.
- Мод нельзя редактировать во время плейтеста; плейтест — кнопка `[▶]`, в board‑плейтесте минигры пропускаются.

---

## 2. Таблица событий

Сокращения: MG = Minigame Mod, BD = Board Mod.

### 2.1 События `Logic Component` (MG)

URL: `https://workshop.pummelparty.com/wiki/Logic_Component`. На одном компоненте можно добавить несколько событий; у каждого свой список действий.

| Событие | Когда срабатывает | Тип |
|---|---|---|
| `Start` | Когда начинается стартовый отсчёт минигры | MG |
| `Enable` | Каждый раз, когда gameobject включается: при загрузке минигры и при включении через `Set Active Action` (если был выключен) | MG |
| `Update` | Каждый кадр. Вики: не консистентно между игроками (разный FPS); для таймингов использовать `Timer` | MG |
| `Hit` | Объект с компонентом ударен игроком (кулаком) или оружием | MG |
| `Weapon Hit` | Объект ударен оружием; поле `Weapon Type` — тип(ы) оружия, вызывающие срабатывание | MG |
| `Timer` | Периодически; поле `Interval`. Режимы (стрелка рядом со значением): константа или `Random Between Two Values` (случайно между min и max) | MG |
| `Round Start` | После отсчёта начала раунда | MG |
| `Round End` | В конце каждого раунда | MG |

Вики не указывает явно, что `Logic Component` недоступен в Board‑модах, но все его события описаны в терминах минигры (minigame countdown, rounds), а страница `Action Editor` говорит, что board‑действия ограничены событиями `Board Space Event Component`.

### 2.2 События `Trigger Component` (MG)

URL: `https://workshop.pummelparty.com/wiki/Trigger_Component`.

| Событие | Когда срабатывает |
|---|---|
| `On Hit` | Оружие или удар кулаком попали по триггеру. При включении триггер становится **твёрдым**, а остальные типы событий отключаются. Единственный режим, доступный при `Custom Collider` (на странице также упоминается как `Trigger On Hit` / `Trigger on Hit`) |
| `On Enter` | Что‑то вошло в объём |
| `On Exit` | Что‑то вышло из объёма |
| `On Stay` | Повторно, пока что‑то внутри; период — `Trigger Interval` |

### 2.3 Хуки действий `Item Component` (MG; предмет в руках игрока)

URL: `https://workshop.pummelparty.com/wiki/Item_Component`. Вики называет их не «events», а наборами действий.

| Хук | Когда |
|---|---|
| `'On Pickup' Actions` | При подборе предмета |
| `'While Held' Actions` | Повторно, пока предмет удерживается; период — `'While Held' Action Delay (s)` |
| `'On Use' Actions` | При каждом использовании (только `Carried` и `Weapon`) |
| `'On Drop' Action` | При любом сбросе: ручном, автоматическом по времени/использованиям, при смерти |

### 2.4 Хук `Weapon Component` (стационарное оружие)

URL: `https://workshop.pummelparty.com/wiki/Weapon_Component`.

| Хук | Когда |
|---|---|
| `On Hit` | «Actions performed whenever the weapon fires» (каждый выстрел) |

### 2.5 События игрока: `Mod Settings > Player Settings > Event Triggers` (MG)

URL: `https://workshop.pummelparty.com/wiki/Mod_Settings` (и `/wiki/Event`).

| Событие | Когда |
|---|---|
| `On Weapon Hit` | Игрок получил попадание оружием; есть настройка `Weapon Type` |
| `On Tick` | Непрерывно с периодом `Interval` |
| `On Death` | Каждый раз, когда игрок убит |
| `On Respawn` | Каждый респаун, **кроме** первого спауна в начале игры/раунда |
| `On Round Start` | Один раз на игрока на раунд, при его первоначальном спауне |
| `On Round End` | Один раз на игрока на раунд, при окончании раунда |

### 2.6 События `Board Space Event Component` (BD)

URL: `https://workshop.pummelparty.com/wiki/Board_Space_Event_Component`, `https://workshop.pummelparty.com/wiki/Custom_Board_Space`.

| Событие | Когда |
|---|---|
| `On Player Land` | Игрок закончил ход на этой клетке (прохождение мимо не считается) |
| `On Player Passing` | Игрок прошёл через клетку. Не срабатывает, если игрок пролетает над ней на ракете. (В патч‑ноутах 1.13.0 называется `On Player Pass`.) |

Компонент работает **только на корневом gameobject префаба** кастомной клетки; в сцене вне префаба он ничего не делает. Страница также упоминает событие «On Enter» в тексте раздела Setup — судя по контексту, это старое название `On Player Land`.

### 2.7 Устаревшее: `Destructible Component` → `On Hit`

URL: `https://workshop.pummelparty.com/wiki/Destructible_Component`. «This component has been removed and cannot be added to new mods». Замена — `Logic Component` (`Hit` / `Weapon Hit`) или `Trigger Component` (`On Hit`). Не использовать.

---

## 3. Таблица действий

Категории — как на главной странице вики. Поля `Target`/`Targets` есть почти у всех действий; явные опции указаны там, где вики их называет. Операции `Set / Add / Subtract / Multiply / Divide` у числовых действий: `Divide` всегда округляет вниз до целого.

### 3.1 Minigame Logic (только MG)

| Действие | Параметры (как на вики) | Что делает | URL |
|---|---|---|---|
| `Change Health Action` | операции set/add/subtract/multiply/divide; имя числового поля вики не приводит | Меняет здоровье игрока. Ничего не делает, если `Target` не игрок | `/wiki/Change_Health_Action` |
| `Change Player Velocity Action` | `Speed`; `Operation` = `Set`, `Add`, `Subtract`, `Multiply`, `Divide`; `Space` = `World`, `Local`; `Direction Type` — вики называет только `Towards Source` и `Towards Receiver` (вдоль линии «игрок ↔ объект, выполняющий действие»); остальные варианты не документированы | Меняет скорость игрока. Пример вики: jump pad/boost pad через `Trigger Component`; «bouncy sphere»: сферический триггер + `Towards Source` + `Set` ≈ 12 | `/wiki/Change_Player_Velocity_Action` |
| `Change Score Action` | операции set/add/subtract/multiply/divide; имя поля не приведено | Меняет очки игрока. Только для игрока‑цели | `/wiki/Change_Score_Action` |
| `Drop Minigame Item Action` | выбор конкретного слота или «все слоты» (имена полей не приведены) | Заставляет игрока выбросить предмет из слота / все предметы. Несколько действий — чтобы выбросить из нескольких, но не всех слотов | `/wiki/Drop_Minigame_Item_Action` |
| `Give Minigame Item Action` | ссылка на `Prefab Asset`, у которого на корне есть `Item Component` | Даёт игроку предмет. Чтобы заспаунить предмет на земле — `Spawn Prefab Action`. Для board‑игрока — `Give Item Action` | `/wiki/Give_Minigame_Item_Action` |
| `Modify Player Action` | атрибуты: `Movement Speed Multiplier` (0…100, не отрицательный); `Gravity` (направление + величина, в мировых осях) | Меняет атрибут одного игрока. Per‑player gravity переопределяет `Set Gravity Action` для этого игрока; более поздний `Set Gravity` перекрывает обратно | `/wiki/Modify_Player_Action` |
| `Set Gravity Action` | направление и величина (имена полей не приведены) | Глобальная гравитация для всех игроков, относительно мира | `/wiki/Set_Gravity_Action` |
| `Set Placement Action` | только `Target` (игрок) | Помечает игрока «финишировавшим» и даёт место. Очки = `100 * (<number of players> - <number of finished players>)`. Для завершения минигры поставить `Placement Condition` = `Finish Order`; очки можно скрыть опцией `Show Points in UI` (страница действия; в `Mod Settings` это поле не описано) | `/wiki/Set_Placement_Action` |
| `Stun Player Action` | `Target` (игрок); длительность стана — где задаётся, вики не говорит | Станит игрока. Не сработает, если игрок ещё в stun‑invulnerability (настройка в `Mod Settings > Stuns`) | `/wiki/Stun_Player_Action` |

### 3.2 Board Logic (только BD; все — на `Board Space Event Component`)

Общий паттерн `Targets`: `This Player` (игрок, вызвавший событие), `This Board Space` (все игроки на этой клетке), `Advanced` (список клеток; все игроки на любой из них).

| Действие | Параметры | Что делает | URL |
|---|---|---|---|
| `Display Popup Action` | `Title/Speaker Name`, `Body Text`, `Speaker Icon` (квадратная текстура), `Choice buttons` (0…4), `Choice # Label`, `Cost of Choice #` = `None`/`Key`/`Health`/`Item`/`Trophy`, `Cost (Key)`, `Cost (Health)`, `Item Cost` (какой предмет), `Cost (Item)`, `Cost (Trophy)`, `Show Close Button`, `Close Button Text`. У каждого выбора — событие `On Select` со своим списком действий | Модальный попап в ход игрока. Одна валюта на кнопку; если ресурса не хватает — кнопка недоступна. Попапы вкладываются друг в друга (одностороннее дерево диалога). Действия ниже попапа ждут. На вики помечено «planned/subject to change», но по патч‑ноутам 1.13.0 выпущено | `/wiki/Display_Popup_Action` |
| `Damage Player Action` | `Targets` (`This Player` / `This Board Space` / `Advanced`), `Damage`, `Flinch Animation` (только при выключенном `Ragdoll`), `Drop Keys` (роняет 3 ключа), `Ragdoll` (игрок умирает и спаунится регдолл), `Ragdoll Velocity`, `Blood`, `Blood Velocity`, `Blood Amount`, `Play Sound`, `Volume` | Наносит урон игрокам на клетках | `/wiki/Damage_Player_Action` |
| `Drop Keys Action` | `Targets` (`Advanced` доступен); режим: dropped (ключи падают на карту, другие могут собрать) / removed (уничтожаются); количество | Отнимает ключи. Больше, чем есть, — отнимет все | `/wiki/Drop_Keys_Action` |
| `Give Item Action` | `Targets` (`This Board Space`, `Advanced`); список board‑предметов (пример: Shotgun, Bee Hive, Magnet, Eggplant) | Даёт один случайный предмет из списка. Несколько предметов — несколько действий | `/wiki/Give_Item_Action` |
| `Give Keys Action` | `Targets` (`Advanced`); число ключей > 0 | Даёт ключи | `/wiki/Give_Keys_Action` |
| `Give Trophy Action` | `Targets` (`Advanced`); число трофеев (макс. 20 за раз); `Play Fanfare Sound` | Даёт трофеи | `/wiki/Give_Trophy_Action` |
| `Heal Player Action` | количество HP | Прибавляет HP (не устанавливает). Максимум здоровья на доске — 30 | `/wiki/Heal_Player_Action` |
| `Move To Space Action` | список ссылок на board spaces | 1 клетка — переместить туда; >1 — случайная из списка. Перемещение завершает ход; эффект клетки назначения **не** применяется; на сундук/кэш нельзя открыть | `/wiki/Move_To_Space_Action` |
| `Remove Trophy Action` | `Targets` (`Advanced`); `Trophies to Remove` | Снимает трофеи; если меньше — все | `/wiki/Remove_Trophy_Action` |
| `Set Board Space Active Action` | `Target`: `This Board Space` и/или `Advanced` (список); `Effect`: `Disable` / `Enable` / `Toggle` | Включает/выключает клетку. Отключённая клетка: невидима, ведёт себя как pathing, не стоит шага, триггеры не работают, нельзя закончить ход. Помечено «planned» | `/wiki/Set_Board_Space_Active_Action` |
| `Set Connection Active Action` | список `Board spaces to enable/disable/toggle connections on`; для каждой исходящей связи dropdown `Do Nothing` / `Disable` / `Enable` / `Toggle` | Открывает/закрывает пути. Если отключить последнюю исходящую связь — игра случайно включит одну обратно (нет тупиков). Помечено «planned», выпущено в 1.13.0 | `/wiki/Set_Connection_Active_Action` |
| `Spawn Keys Action` | `Target`: текущая клетка игрока / клетка события / `Advanced` (ссылки на `Board Space Component`, иное игнорируется); число ключей — **на каждую** цель | Спаунит ключи на клетках; собрать может любой | `/wiki/Spawn_Keys_Action` |

### 3.3 Utility (тип мода на вики не указан — считать «оба», кроме оговорок)

| Действие | Параметры | Что делает | URL |
|---|---|---|---|
| `Kill/Destroy Action` (на главной — `Kill Action`; обе страницы идентичны) | только ссылка на цель | Цель — gameobject/компонент → уничтожить объект; цель — игрок → убить. Объект, используемый как visual игрока, уничтожить нельзя | `/wiki/Kill_Action`, `/wiki/Kill/Destroy_Action` |
| `Play Sound Action` | `Target`, `Clip`, `Volume` | Если `Target` — `Audio Source Component`: клип играет через него с его настройками (пустой `Clip` → клип источника). Иначе — глобально | `/wiki/Play_Sound_Action` |
| `Set Active Action` | состояние: `Enabled` / `Disabled` / `Toggle` | Включает/выключает gameobject (цель‑компонент → его объект). Включение вызывает `Enable` у `Logic Component`. В BD также включает/выключает board spaces (цель — родитель → все дочерние клетки) | `/wiki/Set_Active_Action` |
| `Spawn Prefab Action` | `Prefabs` (список; случайный выбор), `Parent To Target`, `Target Position Offset`, `Target Rotation Offset`, `Spawn At Position`, `Position`, `Rotation` (Euler, градусы) | Спаунит префаб на позиции каждой цели (`Advanced` → несколько) и/или в мировой точке (аддитивно). Смещения локальные при `Parent To Target`, иначе мировые. Одна мировая точка на действие | `/wiki/Spawn_Prefab_Action` |
| `Wait Action` | режим константа (сек) или диапазон min…max (дробные секунды); переключение стрелкой справа от полей | Задерживает всё ниже себя | `/wiki/Wait_Action` |

### 3.4 Movement (тип мода не указан)

| Действие | Параметры | Что делает | URL |
|---|---|---|---|
| `Match Transform Action` | `Transform To Match`, `Targets`; в примере — выбор осей (X и Y, но не Z) | Переносит/поворачивает/масштабирует цели под другой transform. Паттерн: пустой объект как «маркер назначения» | `/wiki/Match_Transform_Action` |
| `Play Tween Animation Action` | `Target`, `Type` = `Position`/`Rotation`/`Scale`, `Ease Type` (`Linear`, ease in/out — полный список не приведён), `Time` (сек), `Start Type` и `End Type` = `Current` / `Specific` / `Offset` | Плавное одноразовое движение между двумя значениями (пример: куб вверх на 1 за 4 с) | `/wiki/Play_Tween_Animation_Action` |
| `Position Action` | операция `Set`/`Add`/`Subtract`/`Multiply`/`Divide` над вектором (покомпонентно); `Space` = `Local` (относительно родителя) / `World` | Меняет позицию объекта | `/wiki/Position_Action` |
| `Rotation Action` | то же над Euler‑углами; `Local`/`World` | Меняет поворот | `/wiki/Rotation_Action` |
| `Scale Action` | то же над локальным масштабом | Меняет масштаб (пример: игрок ×2) | `/wiki/Scale_Action` |

### 3.5 Visuals (тип мода не указан, кроме оговорок)

| Действие | Параметры | Что делает | URL |
|---|---|---|---|
| `Set Color Action` | цвет (имя поля не приведено) | `Prop Component` → tint; `Logic Component` → tint всех дочерних props; игрок → цвет игрока (сбрасывается при смерти, не сохраняется после минигры) | `/wiki/Set_Color_Action` |
| `Set Player Visual Action` | `Targets` (только игроки), `Prefab` (пусто → сброс к стандартному Pummel), `Use Player Color`, `Vertical Rotation Child` (только `Third Person`), `Movement Rotation Child` (нельзя тот же объект) | Заменяет визуал игрока префабом. Коллайдер игрока — капсула по коллайдерам префаба; слоты предметов: `Head` = макс. Y, `Left Hand` = мин. X, `Right Hand` = макс. X, `Back` = мин. Z, `Body` = корень. Сохраняется после респауна — сбрасывать в `OnRespawn` пустым `Prefab` | `/wiki/Set_Player_Visual_Action` |
| `Spawn Effect Action` | эффект: `Wood`, `Blood`, `Explosion`, `Confetti`, `Sparkles`; позиция = позиция `Target` | Готовый партикл‑эффект | `/wiki/Spawn_Effect_Action` |
| `Show Message Action` | `Message Target` = `All` / `Target` (игрок цели), `Message` (string), `Duration (s)` (0.5 с … «five minutes», на странице также «1200 seconds» — противоречие) | Текст по центру экрана. Нельзя адресовать игрока по номеру | `/wiki/Show_Message_Action` |

Всего на вики: категория `Category:Actions` — 34 страницы (33 уникальных действия; `Kill Action` и `Kill/Destroy Action` — одно и то же).

---

## 4. Компоненты

Полный список `Category:Components` — 26 компонентов (URL `https://workshop.pummelparty.com/wiki/Category:Components`). Ниже — поля, важные для логики. Рендер/физика — кратко.

### 4.1 Gameplay (`Category:Gameplay_Components`, 13 шт.)

| Компонент | Назначение | Ключевые поля | Тип | URL |
|---|---|---|---|---|
| `Logic Component` | Контейнер событий → действий | события из §2.1; `Weapon Type`, `Interval` | MG | `/wiki/Logic_Component` |
| `Trigger Component` | Объём, реагирующий на вход/выход/нахождение/удар | форма: `Box` (width/height/depth), `Sphere` (radius), `Capsule` (radius/height), `Custom Collider` (коллайдеры того же объекта; только `On Hit`); `Center` (кроме Custom); `Trigger Interval` (для `On Stay`); `One Use Per Player`; `Disable After Triggered`. Объём невидим в игре | MG | `/wiki/Trigger_Component` |
| `Item Component` | Подбираемый предмет | `Item Type` = `Carried`/`Weapon`/`Worn`/`Pickup`; `Item Slot` (`Right Hand`, `Left Hand`, `Head`, `Back`, `Body` — 5 слотов); `Item Hold Animation`; `Item Prefab`; `Unique Drop Prefab`; `Dropped Item Prefab`; `Item Beacon Color`; `Custom Item Beacon Color`. Weapon: `Weapon Type` = `Melee` (`Damage`, `Stun on Hit`, `Stun Duration (s)`, `Swing Range`, `Attack Animation`) / `Gun` (`Damage Type` = `Hit Scan`/`Beam`; `Damage`, `Stun on Hit`, `Stun Duration (s)`, `Shot Count`, `Spread` = `None`/`Random`, `Max Distance`, `Spawn Bullet Effect`, `Bullet Color`, `Spawn Trail Effect`, `Start Color`, `End Color`, `Trail Width`, `Trail Length`, `Fire Sound` = `None`/`Rifle`/`Shotgun`/`Sniper`/`Custom`, `Beam Damage Cooldown`, `Beam Sound` = `None`/`Laser`/`Custom`). Pickup: `Pickup Sound Type`, `Unique Pickup`, `Item Pickup Priority`, `'On Pickup' Actions`. Held: `Held Position Offset`, `Held Rotation Offset`, `'While Held' Action Delay (s)`, `'While Held' Actions`. Usage (Carried/Weapon): `Cooldown`, `Has Limited Uses`, `Drop After Uses`, `'On Use' Actions`. Drop: `Can Be Dropped`, `Automatically Drop After Time`, `Drop After Time (s)`, `Disappear When Dropped`, `Drop On Death`, `'On Drop' Action`. Нельзя добавить объекту с детьми | MG (вики тип не указывает) | `/wiki/Item_Component` |
| `Weapon Component` | Стационарная турель/оружие, не держится игроком | `Fire Time`, `Damage Type` = `Hit Scan`/`Beam`/`Area`, `Damage`, `Stun on Hit`, `Stun Duration (s)`, `Shot Count`, `Spread`, `Max Distance`, `Spawn Bullet Effect`, `Bullet Color`, `Spawn Trail Effect`, `Start Color`, `End Color`, `Trail Width`, `Trail Length`, `Beam Damage Cooldown`, `Shape` = `Point`/`Sphere`, `Radius`, `Fire Sound`, `On Hit` (действия) | MG | `/wiki/Weapon_Component` |
| `Player Spawn Component` | Точки спауна (обязательны для минигры; должны вместить 8 игроков) | `Spawn Shape` = `Point`/`Line`/`Circle`; `Spawn Usage Type` = `InitialSpawn`/`Respawn`; `Shared Spawn`; `Advanced`; `Allowed Players`; `Player Count Mask` | MG only | `/wiki/Player_Spawn_Component` |
| `Spawner Component` | Периодический спаун префабов | `Type` = `Always Spawn`/`Spawn On Destruction`; `Interval` (конст./случ.); `Delay`; `Spawn Count`; `Prefabs` (случайный выбор); `Locations` = `OnSpawner`/`OnTargets`; `Spawn Points` | не указан | `/wiki/Spawner_Component` |
| `Mover Component` | Постоянное движение/вращение в **локальных** осях | `Direction Type` (в т.ч. `Custom`), `Direction`, `Speed` (ед/с), `Rotation Axis Type`, `Rotation Axis`, `Rotation Speed` (град/с). Остановить — уничтожить объект или выключить компонент действиями | не указан | `/wiki/Mover_Component` |
| `Simple Animator Component` | Зацикленная анимация позиции/поворота | `Use Local Position`, `Use Local Rotation`, `Time Offset`; анимации: `Move Along Line` (`Frequency`, `Distance Along Line`, `Direction of Line`), `Orbit Position` (`Frequency`, `X Radius`, `Z Radius`), `Rotate Around Axis` (`Frequency`, `Rotate Around Axis`), `Custom Animation` (слои: `Animation Type` = `Position`/`Rotation`, `Animation Speed`, `Animation Axis`, `Random Animation Offset`, `Animation Offset`, `Animation Curve`) | не указан | `/wiki/Simple_Animator_Component` |
| `AI Navigation Node Component` | Навигация ботов | `Connected Nodes` (односторонние), `Is AI Goal` | MG | `/wiki/AI_Navigation_Node_Component` |
| `Board Space Component` | Клетка доски | `Type` = `Pathing`/`Start`/`Heal` (+10 HP)/`Gold` (+5 ключей)/`Hazard` (−5 HP)/`Item`/`Recruit`/`Graveyard`/`Custom`; `Custom Space Prefab`; `Supports Goal`; `Custom Goal Position`; `Spawn Rotation`; `Spawn Distance`; `Can be landed on` (Custom); `Stop Rocket from entering` (Custom); `Start Disabled`; `Outgoing Connections` → `Player Transition` = `Walk`/`Jump`/`Teleport`, `Start Disabled` (per connection); кнопка `Align board space to ground`. Нельзя в префабах и на объектах с детьми | BD only | `/wiki/Board_Space_Component` |
| `Board Space Event Component` | События кастомной клетки (§2.6) | `On Player Land`, `On Player Passing` | BD only, только корень префаба | `/wiki/Board_Space_Event_Component` |
| `Prefab Instance Component` | Экземпляр префаба | кнопка `Edit Prefab`; поле `Prefab`. Только на пустом объекте без детей/других компонентов | оба | `/wiki/Prefab_Instance_Component` |
| `Note Component` | Заметка для автора; в игре не действует | текст | оба | `/wiki/Note_Component` |
| `Destructible Component` | **Удалён**, нельзя добавить | `On Hit` | — | `/wiki/Destructible_Component` |

### 4.2 Rendering / Audio / Physics / Other (для логики второстепенно)

| Компонент | Ключевые поля | URL |
|---|---|---|
| `Prop Component` | `Prop`, `Tint Color`, `Collision Type` = `None`/`Box`/`Sphere`/`Mesh`, `Shadow` = `Off`/`On`/`Two Sided`/`Shadows Only`, `Custom Materials`. Один на объект. С `None` на проп нельзя встать | `/wiki/Prop_Component` |
| `Mesh Renderer Component` | `Cast Shadows`, `Mesh`, `Materials` | `/wiki/Mesh_Renderer_Component` |
| `Text Component` | `Text`, `Font`, `Color`, `Font Size`, `Size`, `Horizontal`, `Font Styles`, `Outline`, `Outline Color`, `Thickness`, `Shadow`, `Shadow Color`, `Offset X`, `Offset Y`, `Softness`; теги `<u>`, `<b>`, `<i>`, `<color=…>`, `<size=n>`. Статичный — действия для смены текста на вики нет | `/wiki/Text_Component` |
| `Particle System Component` | модули Unity particle system; «some fields may not be exposed» | `/wiki/Particle_System_Component` |
| `Line Renderer Component` | `Positions`, `Loop`, `Use World Space`, `Start Width`, `End Width`, `Corner Vertices`, `End Vertices`, `Start Color`, `End Color`, `Alignment` = `View`/`Transform Z`, `Texture Mode`, `Materials`, `Cast Shadows`, `Receive Shadows` | `/wiki/Line_Renderer_Component` |
| `Light Component` | `Type` = `Point`/`Spot`/`Directional`, `Color`, `Range`, `Spot Angle`, `Intensity`, `Shadows` = `None`/`Hard`/`Soft` | `/wiki/Light_Component` |
| `Water Component` | `Width`, `Height`, `Cell Size`, `Deep Color`, `Shallow Color`, `Froth Color`, `Wave Height`, `Wave Speed`. Некорректно внутри префабов | `/wiki/Water_Component` |
| `Audio Source Component` | `Audio Source Type` (SFX/music), `Audio Clip`, `Play On Awake`, `Loop`, `Pitch`, `Volume`, `2D/3D Sound Blend`, `Stereo Panning`, `Rolloff Mode`, `Min Distance`, `Max Distance`, `Use Doppler Effect`. Запуск в игре — `Play Sound Action` с `Target` = `Advanced` → источник | `/wiki/Audio_Source_Component` |
| `Box Collider Component` | `Center`, `Size` | `/wiki/Box_Collider_Component` |
| `Sphere Collider Component` | `Center`, `Radius` | `/wiki/Sphere_Collider_Component` |
| `Capsule Collider Component` | `Center`, `Radius`, `Height`, `Direction` | `/wiki/Capsule_Collider_Component` |
| `Mesh Collider Component` | `Convex`, `Mesh` | `/wiki/Mesh_Collider_Component` |
| `Transform Component` | `Position`, `Rotation`, `Scale`. Лимиты: позиция ≤ 1000 по любой оси; масштаб > 0 и ≤ 1000× | `/wiki/Transform_Component` |

### 4.3 Настройки мода, влияющие на логику (`/wiki/Mod_Settings`)

- **Minigame Settings:** `Rounds`, `Round Duration (s)`, `End Conditions` = `Timer` / `ObtainPoints` / `RemainingPlayersAlive` / `FinishMinigame`, `Points to win`, `Players Alive`, `Placement Condition` = `Most Points` / `Least Points` / `Finish Order` / `Last Man Standing`. (Страница `Set Placement Action` упоминает ещё `Show Points in UI`; туториал — `Points to Win` и `Obtain Points` в другом написании.)
- **Player Settings:** `Player Type` = `Third Person` / `Top Down`; `Movement` (speed, acceleration, gravity, jumping, twinstick); `Camera` (`Static`/`Follow`/`Follow All`, Square/Circle — только Top Down); `Punching` (allowed, cooldown, damage, stun); `Stuns` (immunity duration); `Respawning`: `Can Respawn`, `Respawn Time (s)`, `Invulnerable Time (s)`; `Event Triggers` (§2.5); `Health`: `Use Health` (если выкл. — любой урон убивает), `Show Health Bar`, `Health Points`; `Name Tags` = `Screen Space` / `World Space` / `True World Space`.
- **Board Settings:** `Board Details` (число сундуков, Weapons Cache, позиция Fake Chest), `Custom Spaces` (список префабов), `Board Size`, `Camera Settings`.
- Общие: детали мода, `Music & Ambient Sound`, `Lighting` (`/wiki/Lighting_Settings`), `Screen Effects` (`/wiki/Screen_Effects`).

---

## 5. Условия, переменные, счётчики

**На вики их нет.** Ни одна страница не описывает переменные, условия (if/else, сравнения), счётчики, случайные ветвления (кроме случайного выбора префаба/предмета/клетки/интервала), таймеры с состоянием, события между объектами («послать сигнал»), циклы. Единственные механизмы «состояния», доступные через существующие кирпичики:

- Очки игрока (`Change Score Action` + `End Conditions`/`Placement Condition`) и здоровье (`Change Health Action`) — единственные числовые величины, которые можно менять и по которым игра принимает решения (конец минигры, места).
- Включение/выключение объектов (`Set Active Action`, `Toggle`) и `Enable` событие в `Logic Component` — простейший «флаг» и способ запустить цепочку действий «по сигналу» (включить объект → его `Logic Component` `Enable` → его действия). Это документированное поведение, а не трюк.
- `One Use Per Player` / `Disable After Triggered` у триггера — одноразовость без счётчиков.
- Случайность: `Wait Action` (диапазон), `Timer` (`Random Between Two Values`), `Spawn Prefab`/`Give Item`/`Move To Space`/`Spawner` (случайный элемент списка), `Spread` = `Random`.
- Стан‑иммунитет, respawn invulnerability — таймеры движка, не управляемые действиями.
- В board‑модах: ресурсы игрока (ключи, трофеи, HP, предметы) можно тратить как «условие» через `Display Popup Action` (кнопка недоступна, если ресурса не хватает) — это единственный документированный условный механизм.

---

## 6. Ограничения (что нельзя сделать по вики)

- Нет скриптов, переменных, условий, счётчиков, математики (см. §5). Нет действия, меняющего текст `Text Component`, UI, таймер раунда или настройки мода в рантайме.
- Нельзя адресовать игрока по номеру (`Show Message Action`); нет действия «для каждого игрока» — только текущая цель / все / `Advanced`‑список объектов.
- Тип мода фиксирован при создании; board‑действия работают только на `Board Space Event Component`; MG‑действия — только в минигре.
- `Update` недетерминирован между клиентами — вики не рекомендует.
- `Logic Component`: событие `Hit`/`Weapon Hit` требует активного коллайдера (по аналогии с удалённым `Destructible`; явно на `Logic_Component` не сказано).
- `Trigger Component`: `On Hit` делает триггер твёрдым и отключает остальные события; `Custom Collider` — только `On Hit`.
- `Item Component`: без дочерних объектов; `Pickup` нельзя держать/использовать; `Worn` нельзя использовать; `Give Minigame Item` требует `Item Component` на корне префаба.
- `Player Spawn Component` обязателен; должны вмещаться 8 игроков.
- `Board Space Component`: один `Start`; все клетки связаны; у каждой ≥1 исходящая связь (кроме… `Graveyard` не имеет входящих); нельзя в префабах/на объектах с детьми; `Start` и `Graveyard` нельзя заменить кастомными; логику `Recruit` нельзя воспроизвести действиями. Каждая клетка должна быть достижима броском кубика, не только через `Move To Space`.
- `Move To Space Action` завершает ход и не применяет эффект клетки; `Give Trophy` ≤ 20; HP на доске ≤ 30; `Display Popup` ≤ 4 кнопок, одна валюта на кнопку, диалог односторонний.
- `Set Color Action` на игроке — временно (до смерти/конца минигры). `Set Player Visual` — объект‑визуал нельзя уничтожить, визуал сохраняется после респауна.
- `Spawn Prefab Action` — одна мировая точка на действие.
- `Transform`: |позиция| ≤ 1000, масштаб (0; 1000].
- Меши: ≤ 65 535 вершин (иначе `Mesh Collider`/`Mesh` collision не гарантированы); импорт только `.obj`; `Water Component` и значения в Prefab Instance могут отображаться неверно.
- Пол в board‑моде обязан иметь коллайдер и слой `WorldGround`, иначе игроки/предметы проваливаются.
- Публикация блокируется ошибками `Mod Validator` (конкретные правила вики не перечисляет); теги — не более 3 дополнительных.
- Мод нельзя редактировать во время плейтеста; в board‑плейтесте минигры пропускаются.
- Страницы `Display Popup Action`, `Set Board Space Active Action`, `Set Connection Active Action` помечены «planned / may change»; по патч‑ноутам 1.13.0 (SteamDB, `https://steamdb.info/patchnotes/12050134`, прочитано через веб‑поиск — прямой fetch вернул 403) они выпущены вместе с `On Player Pass`. 1.13.4: исправлены паузы при цепочке нескольких `Damage Player`/`Give Trophy` в одном списке.

### О чём вики молчит (проверять в редакторе)

- Полный список пунктов выпадающего списка `Target` у действий (`This`, `Hitter`, `Activator` и т.п. упоминаются лишь косвенно).
- Полные списки `Direction Type` (`Change Player Velocity`), `Ease Type` (`Play Tween Animation`), `Direction Type`/`Rotation Axis Type` (`Mover`), `Advanced` у `Player Spawn`.
- Имена числовых полей у `Change Health`, `Change Score`, `Set Gravity`, `Stun Player` (где задаётся длительность), `Drop Minigame Item`, `Give Keys`, `Heal Player`, `Spawn Keys`, `Set Color`.
- Применимость `Utility`/`Movement`/`Visuals` действий к Board‑модам (на вики тип не указан).
- Какие именно поля Unity Particle System экспонированы; конкретные правила `Mod Validator`; лимиты размера мода/числа объектов; что‑либо о сетевой синхронизации.
- Возможность копировать/вставлять/переупорядочивать действия в `Action Editor`.

---

## 7. Обработанные URL (все с префиксом `https://workshop.pummelparty.com`)

Служебные: `/wiki/Main_Page`, `/wiki/Special:AllPages`, `/wiki/Category:Actions`, `/wiki/Category:Components`, `/wiki/Category:Gameplay_Components`.

Концепции и окна: `/wiki/Event`, `/wiki/Action`, `/wiki/Action_Editor`, `/wiki/Component`, `/wiki/Gameobject`, `/wiki/Introduction_to_the_Mod_Editor`, `/wiki/Inspector_Window`, `/wiki/Hierarchy_Window`, `/wiki/Scene_View`, `/wiki/Log_Window`, `/wiki/Mod_Validator`, `/wiki/Mod_Settings`, `/wiki/Minigame_Mod`, `/wiki/Board_Mod`, `/wiki/Custom_Board_Space`, `/wiki/Unlocked_Mod`, `/wiki/Lighting_Settings`, `/wiki/Screen_Effects`, `/wiki/Publishing_to_the_Steam_Workshop`.

Туториалы: `/wiki/Tutorials/Creating_Your_First_Mod`, `/wiki/Tutorials/Building_A_Minigame_Mod`, `/wiki/Tutorials/Building_A_Board_Mod`, `/wiki/Your_First_Minigame`, `/wiki/Your_First_Board`, `/wiki/Your_First_Board_Map`.

Действия (34): `/wiki/Change_Health_Action`, `/wiki/Change_Player_Velocity_Action`, `/wiki/Change_Score_Action`, `/wiki/Drop_Minigame_Item_Action`, `/wiki/Give_Minigame_Item_Action`, `/wiki/Modify_Player_Action`, `/wiki/Set_Gravity_Action`, `/wiki/Set_Placement_Action`, `/wiki/Stun_Player_Action`, `/wiki/Display_Popup_Action`, `/wiki/Damage_Player_Action`, `/wiki/Drop_Keys_Action`, `/wiki/Give_Item_Action`, `/wiki/Give_Keys_Action`, `/wiki/Give_Trophy_Action`, `/wiki/Heal_Player_Action`, `/wiki/Move_To_Space_Action`, `/wiki/Remove_Trophy_Action`, `/wiki/Set_Board_Space_Active_Action`, `/wiki/Set_Connection_Active_Action`, `/wiki/Spawn_Keys_Action`, `/wiki/Kill_Action`, `/wiki/Kill/Destroy_Action`, `/wiki/Play_Sound_Action`, `/wiki/Set_Active_Action`, `/wiki/Spawn_Prefab_Action`, `/wiki/Wait_Action`, `/wiki/Match_Transform_Action`, `/wiki/Play_Tween_Animation_Action`, `/wiki/Position_Action`, `/wiki/Rotation_Action`, `/wiki/Scale_Action`, `/wiki/Set_Color_Action`, `/wiki/Set_Player_Visual_Action`, `/wiki/Spawn_Effect_Action`, `/wiki/Show_Message_Action`.

Компоненты (27, вкл. удалённый): `/wiki/Logic_Component`, `/wiki/Trigger_Component`, `/wiki/Item_Component`, `/wiki/Weapon_Component`, `/wiki/Player_Spawn_Component`, `/wiki/Spawner_Component`, `/wiki/Mover_Component`, `/wiki/Simple_Animator_Component`, `/wiki/AI_Navigation_Node_Component`, `/wiki/Board_Space_Component`, `/wiki/Board_Space_Event_Component`, `/wiki/Prefab_Instance_Component`, `/wiki/Note_Component`, `/wiki/Destructible_Component`, `/wiki/Prop_Component`, `/wiki/Mesh_Renderer_Component`, `/wiki/Text_Component`, `/wiki/Particle_System_Component`, `/wiki/Line_Renderer_Component`, `/wiki/Light_Component`, `/wiki/Water_Component`, `/wiki/Audio_Source_Component`, `/wiki/Box_Collider_Component`, `/wiki/Sphere_Collider_Component`, `/wiki/Capsule_Collider_Component`, `/wiki/Mesh_Collider_Component`, `/wiki/Transform_Component`.

Ассеты: `/wiki/Prefab_Asset`, `/wiki/Material_Asset`, `/wiki/Mesh_Asset`, `/wiki/Importing_Models`.

Не читались (не про логику): `/wiki/Asset_Browser`, `/wiki/*_Actions_and_Shortcuts`, `/wiki/Mod_Editor_Shortcuts`, `/wiki/Mod_Browser`, `/wiki/Opening_The_Mod_Editor`, `/wiki/Published_Mods_Window`, `/wiki/Rendering_Components`, `/wiki/Texture_Asset`, `/wiki/Audio_Clip_Asset`, `/wiki/Importing_Audio`, `/wiki/Importing_Images`, `/wiki/Tutorial/Creating_Your_First_Mod` (дубликат).

Внешнее: SteamDB patch notes 1.12.1 / 1.13.0 / 1.13.4 (`https://steamdb.info/patchnotes/10103260`, `/12050134`, `/12967480`) — прямой fetch 403, содержание получено через WebSearch.
