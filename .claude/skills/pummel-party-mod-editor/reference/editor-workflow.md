# Pummel Party Mod Editor — рабочий процесс редактора и контент

Справочник по официальному Mod Editor игры Pummel Party (появился в Update 1.12.1 «Mod Editor Beta», декабрь 2022). Охватывает создание проекта, интерфейс, доски, мини-игры, импорт ассетов, префабы, плейтест/валидацию, публикацию и хранение проектов на диске. Каталог действий (Actions) и событий — в отдельном справочнике.

Всё, что не подтверждено источниками, помечено как **«не задокументировано»**. Английские идентификаторы (меню, компоненты, настройки) сохранены в написании вики.

Собрано 2026-10-21. Основные страницы вики датированы декабрём 2022 (редактор в статусе beta); актуальная версия игры могла изменить детали.

---

## 1. Создание проекта и типы модов

Источники:
- https://workshop.pummelparty.com/wiki/Introduction_to_the_Mod_Editor
- https://workshop.pummelparty.com/wiki/Opening_The_Mod_Editor
- https://workshop.pummelparty.com/wiki/Tutorials/Creating_Your_First_Mod
- https://workshop.pummelparty.com/wiki/Unlocked_Mod
- https://steamdb.info/patchnotes/10103260 (прямой fetch вернул 403; содержимое известно через WebSearch-выдачу и статью TechRaptor)

**Что такое редактор.** Mod Editor встроен в исполняемый файл игры, это не отдельная программа. Построен на базе Unity Editor, но имеет отличия (вики рекомендует прочитать введение даже тем, кто знает Unity). Объекты с позицией в пространстве называются Gameobjects, организуются в иерархию и получают Components с логикой/функциональностью.

**Как открыть.** Главное меню → кнопка **Workshop** → кнопка **Mod Editor** → открывается **Welcome Screen**. На нём можно создать или открыть мод, перейти к документации и в Workshop. Если экран закрыт, он вызывается через **Window > Welcome Screen**.

**Создание мода.**
1. На Welcome Screen выбрать **New Mod** (или **File > New Mod**).
2. Выбрать шаблон (template). Шаблон задаёт предустановленные объекты, ассеты и настройки. Каждый шаблон относится либо к **Minigame Mod**, либо к **Board Mod**. Есть пустые варианты **Empty** (по одному на тип) для сборки с нуля; в туториале по первому моду используется **Minimal Third Person**.
3. **Тип мода задаётся шаблоном и не может быть изменён позднее.**
4. Ввести имя мода (можно сменить позже) и нажать **OK** — мод создаётся и загружается.

**Шаблоны мини-игр по патч-нотам 1.12.1 (шесть штук):** Minimal Third Person, Minimal Top Down, Simple Arena, Third Person Obstacle Course, Third Person Shooter, Top Down Shooter. Шаблоны досок: кроме Empty, не задокументированы.

**Шаблон из чужого мода (Unlocked Mod).** Если автор опубликовал мод с галочкой **Unlock for editing**, подписчики могут использовать его как основу: в окне New Mod есть вкладка **Unlocked Workshop Mods**. Чтобы мод там появился, нужно быть подписанным на него и мод должен иметь тег «Unlocked» в Workshop. Повторная публикация без галочки «запирает» мод для новых копий (уже созданные на его основе моды не затрагиваются). Обновления оригинала не распространяются на моды, созданные из старой версии.

**Базовый workflow (по вики):**
1. Создать gameobjects в Hierarchy.
2. Расположить и просмотреть их в Scene View.
3. Добавить и настроить components в Inspector.
4. Отредактировать Mod Settings.
5. Протестировать (Playtest) в редакторе.
6. Опубликовать в Steam Workshop.

Пользовательские ассеты добавляются через Asset Browser.

**Не задокументировано:** сохранение (пункт меню Save, автосохранение, горячая клавиша Ctrl+S), undo/redo — ни одна страница вики (включая Mod_Editor_Shortcuts и General_Actions_and_Shortcuts) не упоминает их. Известные пункты меню **File**: New Mod, Publish To Workshop / Publish to Steam Workshop, Validator Mod (так на вики), Published Mods, Delete Mod (упомянут разработчиком в Steam-обсуждении). Также упоминается загрузка существующего проекта «from the file menu» (Importing_*), без точного названия пункта.

---

## 2. Интерфейс редактора

Источники:
- https://workshop.pummelparty.com/wiki/Introduction_to_the_Mod_Editor
- https://workshop.pummelparty.com/wiki/Hierarchy_Window
- https://workshop.pummelparty.com/wiki/Hierarchy_Window_Actions_and_Shortcuts
- https://workshop.pummelparty.com/wiki/Inspector_Window
- https://workshop.pummelparty.com/wiki/Scene_View
- https://workshop.pummelparty.com/wiki/Asset_Browser
- https://workshop.pummelparty.com/wiki/Gameobject
- https://workshop.pummelparty.com/wiki/Mod_Settings
- https://workshop.pummelparty.com/wiki/Mod_Editor_Shortcuts
- https://workshop.pummelparty.com/wiki/General_Actions_and_Shortcuts
- https://workshop.pummelparty.com/wiki/Lighting_Settings
- https://workshop.pummelparty.com/wiki/Screen_Effects
- https://workshop.pummelparty.com/wiki/Tutorials/Creating_Your_First_Mod

### 2.1 Основные окна

- **Hierarchy** — список и структура всех gameobjects сцены. Наверху, жёлтым цветом, находится специальный объект **Mod Settings** (в туториалах называется также Minigame Settings / BoardSettings / «board settings object»), хранящий настройки мода. Выбор объекта здесь выделяет его в Scene View и показывает компоненты в Inspector. Режимы: **Scene Hierarchy** (по умолчанию) и режим редактирования префаба (показывает только корень префаба и его детей; кнопка наверху возвращает в Scene Hierarchy).
- **Inspector** — отображает настройки Mod Settings (когда выбран объект настроек), компоненты выбранного gameobject (имя, layer, active-состояние, вертикальный список компонентов со сворачиваемыми заголовками, кнопка **Add Component** внизу) или import settings выбранного пользовательского ассета. Недоступные пункты в Add Component при наведении показывают причину. Ctrl + ЛКМ по слайдеру позволяет ввести число вручную; ПКМ по заголовку компонента открывает его контекстное меню.
- **Scene View** — 3D-вид сцены с gizmo. Для соединения board spaces gizmos должны быть включены.
- **Asset Browser** (внизу экрана) — встроенные ассеты (props, audio clips, textures, materials) и пользовательские (импортированные изображения, аудио, модели; созданные здесь Prefab Assets и Material Assets). Есть поиск по имени, фильтр по типу (Prop, Prefab, Audio и т.д.) и по тегу размера для props/prefabs (tiny, small, medium, large, huge). Кнопка **Import Asset** — импорт. Папки пользовательских ассетов: `Custom/Props`, `Custom/Textures`, `Custom/Audio`, `Custom/Materials`, `Custom/Prefabs`.
- **Logs (Log Window)** — ошибки и сообщения игры (см. раздел 7).
- **Окна из меню File:** Mod Validator Window, Publish Window, Published Mods Window.

### 2.2 Gameobjects

Создание: ПКМ в Hierarchy (контекстное меню) или вкладка **GameObject** на тулбаре. **Create Empty** создаёт объект без компонентов (в корне, если ничего не выбрано или использован тулбар; дочерним, если ПКМ по объекту). Остальные пункты создают объект с уже прикреплённым компонентом. Новые объекты появляются в 0,0,0. Из туториалов известны пункты: **3D Object > Cube**, **3D Object > Prop**, **Minigame Object > Player Spawn**, **Minigame Object > Item**, **Board Object > Board Space**. Полный список контекстного меню на вики не приведён.

Layers: большинство объектов остаются на слое по умолчанию; объект-пол в Board Mod должен быть на слое **WorldGround**. Active-состояние: отключённый объект скрыт в сцене, его компоненты не работают, но его можно выбрать в Hierarchy (серое имя) и включить в Inspector.

### 2.3 Горячие клавиши и управление

Общие: ЛКМ — выбор/снятие выбора; **Q/W/E/R** — режимы Drag (Pan), Transform, Rotate, Scale (также кнопки на тулбаре); **F10** — скриншот, сохраняется в папку ассетов `Custom/Textures` (используется как preview image); **Z** — переключение handles Pivot/Center; **X** — Local/World; **Esc** — закрыть редактор (в playtest — освободить курсор); **Ctrl + «-» / «+»** — масштаб UI шагами по 10% в диапазоне 50–150%.

Scene View: ПКМ + мышь — осмотр; ПКМ + WASD — движение, Q/E — вниз/вверх; стрелки — движение без ПКМ; колесо — вперёд/назад; Shift — быстрее; средняя кнопка — панорамирование; **F** — фокус на выбранном; Ctrl + ЛКМ — мультивыбор; Ctrl+D — дублировать; Delete — удалить.

Hierarchy: Shift + клик — выбор диапазона; Ctrl + клик — добавить/убрать из выбора; Ctrl+D, F2 (переименовать), Delete.

Asset Browser: клик — выбрать; перетаскивание в Hierarchy/Scene View — разместить prop/prefab; ПКМ — контекстное меню; Ctrl+D, F2, Delete — только для пользовательских ассетов.

### 2.4 Mod Settings (общие для обоих типов)

Редактируются в Inspector при выбранном объекте настроек наверху Hierarchy.
- **Details** (Minigame Details / Board Details): внутриигровые имя, описание (показывается на экране загрузки мини-игры или в лобби доски), preview image (импортированная текстура или скриншот F10). Поля Workshop-листинга — отдельные (см. раздел 8).
- **Music & Ambience**: зацикленная фоновая музыка и ambient-трек, у каждого своя громкость.
- **Lighting Settings**: **Lighting Preset** — 13 встроенных (Day, Default, Evening, Forest, Hell, Maple, Night, Outer Space, Spring, Sunrise, Vaporwave, Watermelon, Winter) или **Custom**; фолдаут **Import Built-in Lighting Profile** для старта с пресета. Custom-группы: Skybox (Stars, Top Color, Horizon Color, Ground Color, Halo Color, Halo Exponent, Halo Strength); Global Light (Use Global Light, Sunlight Direction, Sunlight Color, Sunlight Intensity, Shadow Strength, Sun Shadow Mode: None/Soft/Hard); Ambient Light (Ambient Source: Skybox/Gradient/Color, Ambient Intensity, Ambient Sky/Equator/Ground Color, Ambient Color); Cloud Shadows (Use Cloud Shadows, Primary/Secondary Cloud Speed, Cloud Intensity, Cloud Sparseness, Cloud Size); Fog (Use Fog, Fog Color, Fog Mode: Linear/Exponential/Exponential Squared, Fog Start/End Distance, Fog Density); Shadow Settings (Shadow Distance, Shadow Cascades: 0 или 4). **Custom-профили освещения экспортируются и импортируются как файлы `.json`** и могут переноситься между модами.
- **Screen Effects** (пост-обработка): Ambient Occlusion (Mode, Radius, Thickness Modifier, Intensity, Color, Ambient Only), Bloom (Intensity, Threshold, Soft Knee, Clamp, Diffusion, Anamorphic Ratio, Color), Chromatic Aberration (Intensity), Color Grading (White Balance: Temperature, Tint; Tone: Color Filter, Hue Shift, Saturation, Brightness, Contrast; Channel Mixer), Depth Of Field (Focus Distance, Aperture, Focal Length, Max Blur Size), Grain (Colored, Intensity, Size, Luminance Contribution), Lens Distortion (Intensity, X/Y Multiplier, Center X/Y, Scale), Vignette (Color, Center, Intensity, Smoothness, Roundness, Rounded).

Специфичные для типа настройки — в разделах 3 и 4.

---

## 3. Доски (Board Mod)

Источники:
- https://workshop.pummelparty.com/wiki/Board_Mod
- https://workshop.pummelparty.com/wiki/Your_First_Board (дублирует Board_Mod)
- https://workshop.pummelparty.com/wiki/Tutorials/Building_A_Board_Mod
- https://workshop.pummelparty.com/wiki/Board_Space_Component
- https://workshop.pummelparty.com/wiki/Custom_Board_Space
- https://workshop.pummelparty.com/wiki/Mod_Settings
- https://workshop.pummelparty.com/wiki/Prop_Component

### 3.1 Требования к доске (проверяются Mod Validator)
- Ровно одна клетка типа **Start**.
- Все клетки связаны, нет изолированных участков/петель.
- У каждой клетки есть хотя бы одно исходящее соединение (нет тупиков); у каждой клетки, кроме **Graveyard**, есть входящее соединение.
- Каждая клетка должна быть достижима броском кубика, а не только через Move To Space actions.

Рекомендовано (без этого мод работает, но с артефактами): твёрдый пол (Prop Component с коллизией или Collider) на слое **WorldGround** под всеми клетками и путями; хотя бы одна клетка **Graveyard** (иначе погибшие респавнятся на Start). FAQ: «парящие» игроки после смерти, проваливающиеся/неработающие предметы — признак отсутствия коллайдера или слоя WorldGround у пола.

### 3.2 Клетки (Board Space Component)
Создание: ПКМ в Hierarchy → **Board Object > Board Space** (по умолчанию выдаёт ключи). Компонент нельзя добавить на объект с детьми и нельзя использовать внутри префабов. Поставить чуть выше пола и нажать кнопку **Align board space to ground** в Inspector.

Типы (**Type**): **Pathing** (невидимая, на ней нельзя остановиться, проход не стоит хода — для маршрутизации), **Start** (спавн всех игроков, ровно одна), **Heal** (+10 здоровья), **Gold** (+5 ключей), **Hazard** (5 урона), **Item** (один предмет; Dark Summoning Staff, Arcade Machine, Giga Laser, Nuke Barrel — только из weapons cache), **Recruit** (захват первым игроком, связанные Recruit тоже; владелец выбирает кражу 9–12 здоровья или 6 ключей), **Graveyard** (респавн; при нескольких выбирается самая дальняя от trophy chest; не принимает входящих соединений), **Custom** (префаб + Actions через Board Space Event Component).

Прочие настройки компонента: **Custom Space Prefab** (только Custom; варианты берутся из Mod Settings), **Supports Goal** (может ли тут появляться trophy chest / weapons cache), **Custom Goal Position** (+ **Spawn Rotation**, **Spawn Distance**; недоступно для Pathing/Graveyard и при выключенном Supports Goal), **Can be landed on** (только Custom; при выключении игроки проходят мимо, но событие On Player Passing срабатывает), **Stop Rocket from entering** (только Custom; rocket skewer спешивается на предыдущей клетке), **Start Disabled** (включается через Set Board Space Active Action), **Outgoing Connections** (список исходящих соединений и их типов).

### 3.3 Соединения (пути)
У каждой клетки в Scene View есть синие стрелки-gizmo (gizmos должны быть включены). Клик по стрелке → клик по клетке-назначению создаёт направленное соединение; клик по пустому месту создаёт новую клетку и соединяет с ней; ПКМ отменяет; выбрать соединение и Delete — удалить. Тип перехода задаётся потом в Inspector в **Outgoing Connections**: **Walk** (по умолчанию), **Jump** (прыжок через разрыв/перепад высоты; пригоден для rocket skewers и Bunnies), **Teleport** (мгновенно, без чёрной линии пути, но всё равно стоит хода). У соединения есть и свой **Start Disabled** (включается Set Connection Active Action). Лимита на количество соединений нет, но много исходящих из одной клетки затрудняет выбор.

### 3.4 Custom Board Space
1. Создать prefab с визуалом (в Asset Browser), дочерние объекты с Prop Component (или Particle System, Light и т.п.). Готовый prop **CustomBoardSpace** повторяет стиль игры; его вид меняется Material Asset с шейдером **Custom Board Space Shader**. Start и Graveyard заменить нельзя.
2. На корневой объект префаба (обязательно на корень) добавить **Board Space Event Component** и назначить Actions; без Actions клетка ведёт себя как пустая.
3. В Mod Settings раскрыть **Custom Board Spaces** и добавить запись с префабом.
4. На клетке выставить Type = Custom и выбрать префаб в **Custom Space Prefab**. Один префаб — многоразовый «тип» клетки.

### 3.5 Board Mod Settings
- **Board Details**: **Trophy Chests** (число сундуков по умолчанию), **Weapons Cache** (может ли появляться), **Custom Chest Shuffle Position** (мировая координата для анимации перетасовки Fake Chest).
- **Custom Spaces** — список префабов.
- **Board Size**: **Use Custom Board Size** (иначе считается по клеткам; ограничивает область использования предметов), Left/Right и Forward/Backward size, **Map Center**.
- **Camera Settings**: **Elevation Angle** (угол к плоскости земли), perspective — **Field of View**, **Distance**; orthographic — **View Size**. Туториал упоминает также tilt/distance/FOV и опциональный ортографический режим.

### 3.6 Советы из туториала
Начать с блок-аута твёрдого пола на WorldGround; Start → дальше клетки «кликом по пустому месту»; разнообразить типы, оставляя часть Gold; делать развилки; Graveyard ставить после Start через Pathing-клетку (Start → Graveyard… Start → Pathing → следующая), чтобы респавнившиеся выходили на доску; держать props вне поля камеры; при необходимости задавать Custom Goal Position. Во время плейтеста доски мини-игры пропускаются. Готовый мод туториала: Workshop ID 2897735584 (unlocked).

Запуск доски игроками: подписка через in-game Mod Browser или Steam Workshop → выбор доски в режиме board game (пролистать выбор карт в лобби).

---

## 4. Мини-игры (Minigame Mod)

Источники:
- https://workshop.pummelparty.com/wiki/Minigame_Mod
- https://workshop.pummelparty.com/wiki/Tutorials/Building_A_Minigame_Mod
- https://workshop.pummelparty.com/wiki/Player_Spawn_Component
- https://workshop.pummelparty.com/wiki/Spawner_Component
- https://workshop.pummelparty.com/wiki/Mod_Settings

### 4.1 Требования
Сцена должна содержать точку спавна, с которой могут заспавниться все 8 игроков (вики отмечает, что требования могут расшириться). Совет по дизайну: заставлять игроков взаимодействовать друг с другом.

### 4.2 Спавны (Player Spawn Component, только Minigame Mod)
Создание: **Minigame Object > Player Spawn**. Настройки: **Spawn Shape** — Point / Line (длина, равномерно или случайно) / Circle (радиус, равномерно или случайно); **Spawn Usage Type** — **InitialSpawn** / **Respawn**; **Shared Spawn** (несколько игроков на одной точке при стартовом спавне); **Advanced**: **Allowed Players** (какие игроки могут спавниться; для фиксированных позиций делают 8 спавнов), **Player Count Mask** (точка активна только при определённом числе игроков — например, разные арены для 1–4 и 5–8). Спавны держать над полом.

### 4.3 Minigame Mod Settings
- **Minigame Settings** (в туториале — Minigame Controller): **Rounds**; **End Condition**: **Timer** (с **Round Duration**, секунды), **ObtainPoints** (с **Points to win**), **RemainingPlayersAlive** (с **Players Alive**), **FinishMinigame** (когда для всех сработал Set Placement Action); **Placement Condition**: Most Points / Least Points / Finish Order / Last Man Standing. Это и есть условия победы, счёт и таймер; очки изменяются Change Score Action.
- **Player Settings**: **Player Type** — **Third Person** (камера за игроком) / **Top Down**; движение (скорость, ускорение, замедление, mid-air acceleration, gravity scale, max step height, прыжки вкл/выкл, jump speed, число прыжков в воздухе, twinstick-управление — только Top Down); **Camera** (только Top Down): **Camera Mode** — Static / Follow / Follow All; Distance, View Angle, Position Offset; **Follow Area Shape** — Square / Circle с размером, центром и максимальным смещением; **Punching** (кулаки вкл/выкл, cooldown, урон, оглушение, его длительность); **Stuns** (иммунитет после оглушения); **Respawning** (вкл/выкл, задержка, неуязвимость после респавна); **Event Triggers** (on weapon hit с фильтром по типу оружия, on tick с постоянным или случайным интервалом, on death, on respawn, on round start/end); **Health** (Use health — иначе любой урон смертелен, show health bars, HP); **Name Tags** — Screen Space / World Space / True World Space (по умолчанию).
- Камера для Third Person отдельных настроек на вики не имеет (не задокументировано).

### 4.4 Пример из туториала (сбор предметов)
Пол из Prop (3D Object > Prop, например «GroundMounds 05») с **Collision Type** ≠ None; спавн с Spawn Shape Line/Circle; **Item** (Minigame Object > Item): Item Type **Worn**, Auto Drop After Time = 0, Disappear when Dropped, в On Pickup Actions — Change Score; визуал предмета — префаб с Prop (поле **Item Prefab**); предмет превращён в префаб и размещён 8 раз; End Condition ObtainPoints, Points to Win 10; Player Type Third Person. Респавн предметов — **Spawner Component**: **Type** Always Spawn / **Spawn On Destruction**, **Interval** / **Delay** (фикс. или случайный диапазон), **Spawn Count**, **Prefabs** (случайный выбор), **Locations** OnSpawner / **OnTargets**, **Spawn Points** (список transform, в туториале — пустые объекты с Note Component). Предупреждение: малый Interval при Always Spawn копит объекты и вызывает лаги.

### 4.5 Как мини-игра попадает в игру
После публикации автор автоматически подписан; подписанные мини-игры добавляются в пул для Board- и Minigames-only режимов (в т.ч. на workshop-досках). Чтобы чаще играть конкретный мод, отключите встроенные и прочие мини-игры в ruleset. Хост лобби раздаёт мини-игры из своего ruleset остальным игрокам.

---

## 5. Импорт ассетов

Источники:
- https://workshop.pummelparty.com/wiki/Importing_Models
- https://workshop.pummelparty.com/wiki/Importing_Images
- https://workshop.pummelparty.com/wiki/Importing_Audio
- https://workshop.pummelparty.com/wiki/Mesh_Asset
- https://workshop.pummelparty.com/wiki/Texture_Asset
- https://workshop.pummelparty.com/wiki/Audio_Clip_Asset
- https://workshop.pummelparty.com/wiki/Material_Asset
- https://workshop.pummelparty.com/wiki/Mesh_Renderer_Component
- https://workshop.pummelparty.com/wiki/Mesh_Collider_Component
- https://workshop.pummelparty.com/wiki/Prop_Component
- https://workshop.pummelparty.com/wiki/Simple_Animator_Component

**Общие шаги импорта (одинаковы для всех типов):** открыть Mod Editor → загрузить существующий проект из меню File или создать новый → в Asset Browser внизу экрана нажать **Import Asset** → выбрать тип ассета (**Mesh** / **Texture** / **Audio**) → выбрать файл в проводнике Windows → ассет появляется в Asset Browser в папке Custom/… . Import settings ассета видны в Inspector при его выборе в Asset Browser; после изменения нажать **Apply**.

### 5.1 3D-модели (Mesh)
- Формат: **только `.obj`**.
- Папка: `Custom/Props`.
- Import settings: **Tris** и **Verts** (только чтение), **Recalculate Normals** (использовать нормали из файла или пересчитать; включить и нажать Apply, если нормали выглядят неправильно).
- Лимит: **не более 65 535 вершин**. Более крупные модели могут отображаться, но не гарантированно работают с Mesh Collider Component и с режимом коллизии Mesh у Prop.
- Известная проблема: модель может импортироваться отражённой по одной оси; временное решение — отразить в Blender и т.п.
- Материалы/текстуры: текстурированная модель = Mesh Asset + Texture Asset; текстура назначается в **Material Asset** (слот Albedo), материал — на prop/mesh. MTL-файлы и автоимпорт материалов не упоминаются (не задокументировано). Текстуры корректны при правильной UV-развёртке.
- Использование: **Mesh Renderer Component** (Cast Shadows: Off/On/Two Sided/Shadows Only; Mesh; Materials — список) или **Prop Component** (Prop, Tint Color — не работает с custom materials, **Collision Type**: None/Box/Sphere/Mesh, Shadow, Custom Materials).
- Коллайдеры: **Mesh Collider Component** (Convex — отметить для выпуклых мешей; невыпуклым добавляется «глубина»; Mesh; твёрдый только по внешним граням), а также Box/Capsule/Sphere Collider Components.
- Анимации: импорт скелетных/файловых анимаций **не задокументирован** и не упоминается; есть только **Simple Animator Component** (Use Local Position/Rotation, Time Offset; типы Move Along Line, Orbit Position, Rotate Around Axis, Custom Animation с кривыми) и Play Tween Animation Action.

### 5.2 Изображения (Texture)
- Форматы: **`.png`** (без потерь, прозрачность — для небольших текстур), **`.jpeg`/`.jpg`** (с потерями, без прозрачности — для больших), **`.bmp`** (не рекомендуется).
- Папка: `Custom/Textures` (сюда же попадают скриншоты F10).
- Import options: **Texture Compression** — Normal / High Quality / None (влияет на рантайм, не на размер файла); **Filter Mode** — Point / Bilinear / Trilinear; **Wrap Mode** — Repeat / Clamp / Mirror / Mirror once.
- Лимиты по размеру/разрешению: **не задокументированы**.
- Использование: нельзя назначить напрямую на объект — только через Material Asset (слот **Albedo**; прочие слоты: Metallic, Normal Map, Height Map, Occlusion, Emission). Props с корректной UV: Cube, Plane, Sphere, Capsule, Cylinder, LowPolyQuad, CustomBoardSpace; условно — LowPolyPyramid, BevelCube, BevelCylinder, LowPolyCapsule, LowPolyCylinder; большинство плоскоцветных встроенных props не UV-mapped. Текстура также служит preview image мода (Mod Settings → Minigame Details / Board Details).
- Material Asset создаётся в Asset Browser (ПКМ → Create), папка `Custom/Materials`. Шейдеры: **Standard Shader** (Rendering Mode: Opaque/Cutout/Fade/Transparent, Alpha Cutoff, Albedo, Color, Metallic, Smoothness, Normal Map, Height Map, Occlusion, Emission, Texture Tiling, Texture Offset), **Custom Board Space Shader** (Albedo, Edge Color, Inside Color, Icon Color, Metallic, Smoothness, Icon Scale, tiling/offset), **Particle Shader** (Tint Color, Particle Texture, tiling/offset, Soft Particles Factor, Intensity), **Particle Alpha Blend**.

### 5.3 Аудио
- Формат: **только `.wav`**.
- Папка: `Custom/Audio`.
- Import settings (только чтение): Channel Type (Mono/Stereo), Frequency, Duration.
- Лимиты по размеру/длительности: **не задокументированы**.
- Использование: фоновая музыка/ambience в Mod Settings, **Audio Source Component** в сцене, Play Sound Action.

---

## 6. Префабы

Источники:
- https://workshop.pummelparty.com/wiki/Prefab_Asset
- https://workshop.pummelparty.com/wiki/Prefab_Instance_Component
- https://workshop.pummelparty.com/wiki/Hierarchy_Window

Prefab — переиспользуемая группа GameObjects (под-иерархия). Правка префаба обновляет все его экземпляры. Папка в Asset Browser: `Custom/Prefabs`.

Создание: из Hierarchy — выбрать один родительский объект (мультивыбор не поддерживается) и перетащить в Asset Browser; из Asset Browser — ПКМ → **Create > Prefab** (пустой), затем наполнить.

Редактирование: двойной клик по префабу в Hierarchy, кнопка **Edit Prefab** на Prefab Instance Component в Inspector, или двойной клик в Asset Browser. Hierarchy переходит в режим редактирования префаба (видны только корень и дети; кнопка наверху возвращает в сцену).

Размещение: создать **Prefab Instance** (Prefab Instance Component) и указать **Prefab**. Ограничения: компонент ставится только на пустой GameObject без других компонентов и без детей; после добавления объекту нельзя добавлять детей и другие компоненты; в Hierarchy он получает особую иконку и цвет.

Применение: группы объектов (дом из стен/дверей), визуал для **Item Component** (Item Prefab), объекты для **Spawner Component**, Spawn Prefab Action, Custom Board Space. Board Space Component внутри префабов использовать нельзя.

---

## 7. Плейтест, Log Window, Mod Validator

Источники:
- https://workshop.pummelparty.com/wiki/Tutorials/Creating_Your_First_Mod
- https://workshop.pummelparty.com/wiki/Log_Window
- https://workshop.pummelparty.com/wiki/Mod_Validator
- https://workshop.pummelparty.com/wiki/Tutorials/Building_A_Board_Mod

**Playtest.** Кнопка play вверху по центру. Во время теста мод редактировать нельзя. Кнопка stop завершает тест, pause — пауза, Esc — освобождает курсор. При входе в play mode запускается валидация; при наличии ошибок автоматически открывается Mod Validator. В плейтесте доски мини-игры пропускаются. Сетевой/многопользовательский плейтест — не задокументирован.

**Log Window.** Записывает сообщения о состоянии игры, предупреждения и ошибки; нужен для отладки и для багрепортов по редактору. Справа вверху — счётчики messages / warnings / errors; кнопка копирования выбранной записи в буфер; кнопка **Clear**; строка поиска по ключевому слову.

**Mod Validator.** Открывается через **File > Validator Mod** (так написано на вики), автоматически при входе в play mode с ошибками, и из окна публикации при наличии проблем. Проверка выполняется при каждом плейтесте, при открытии валидатора и перед публикацией. **Errors** (красный «!») обязательны к исправлению перед публикацией; **Warnings** (жёлтый «!») не блокируют публикацию, но могут вызывать неожиданное поведение. Клик по проблеме показывает описание и путь решения; у части есть кнопка **Fix Issue**. Полный список проверок на вики не приведён; известные из других страниц: ровно один Start space, связность и отсутствие тупиков на доске, наличие спавнов на 8 игроков в мини-игре.

---

## 8. Публикация в Steam Workshop

Источники:
- https://workshop.pummelparty.com/wiki/Publishing_to_the_Steam_Workshop
- https://workshop.pummelparty.com/wiki/Published_Mods_Window
- https://workshop.pummelparty.com/wiki/Unlocked_Mod
- https://workshop.pummelparty.com/wiki/Mod_Browser
- https://steamcommunity.com/workshop/discussions/18446744073709551615/3730701797624973127/?appid=880940

**Процесс.** **File > Publish to Steam Workshop** (в туториале — Publish To Workshop) → заполнить окно → **Publish**. Мод загружается в Workshop, открывается Steam overlay со страницей мода. Значения полей можно менять в любое время; сохранение мода хранит их локально, другие игроки видят их только после публикации.

**Поля окна публикации:** **Title** (может отличаться от внутриигрового имени), **Description**, **Language**, **Visibility** — Public (виден в in-game Mod Browser и Workshop) / Unlisted (только по прямой ссылке) / Private (только автору), **Unlock for editing** (см. Unlocked Mod), **Tags** (тип мода ставится автоматически; до трёх дополнительных), **Square Preview** (превью в Workshop и Mod Browser), **Preview videos/images** (картинки и YouTube-ссылки только для страницы Workshop), **Mod Validation** (панель валидатора, если есть предупреждения/ошибки), **Change notes** (только при обновлении).

**Требования:** мод должен пройти валидацию без errors. Размеры/формат thumbnail, лимит размера мода, тексты ошибок — **не задокументированы** (кроме названия «Square Preview», подразумевающего квадратное изображение).

**Обновление:** внести изменения → File > Publish to Steam Workshop → ввести change notes внизу окна → **Update**. Подписчики получают новую версию при следующем запуске игры. Откат: на странице мода в Workshop вкладка **Change Notes** → «Revert to this version», затем переустановить локальную копию через Published Mods (ответ разработчика Charlton, 8 янв 2023).

**Published Mods Window** (**File > Published Mods**): список всех опубликованных модов; действия **Download Mod** / **Install to mod editor** / **Open in mod editor** и переход на страницу Workshop. Используется для восстановления редактируемой копии (удаление, другой компьютер, повреждение). Чтобы заменить локальную копию опубликованной, сначала удалить локальную (**File > Delete Mod** — удаляет только локальную копию, листинг в Workshop не трогает); пока локальная есть, окно просто открывает её. Работает и для locked/private модов, если вы автор.

**Распространение:** игроки подписываются по ссылке Workshop или через **Workshop > Mod Browser** в игре (поиск, сортировка, фильтр по типу, вкладка Personal с опубликованными/сыгранными/подписанными/оценёнными). Хост лобби с включённым модом автоматически раздаёт его остальным.

---

## 9. Где лежат проекты на диске и формат

Источники:
- https://steamcommunity.com/workshop/discussions/18446744073709551615/3730701797624973127/?appid=880940 (ответ разработчика Charlton, январь 2023)
- https://steamcommunity.com/app/880940/discussions/0/4288062841579270741/ (ответ пользователя, март 2024)
- https://www.pcgamingwiki.com/wiki/Pummel_Party (через WebSearch)
- https://workshop.pummelparty.com/wiki/Lighting_Settings

**Путь (по словам разработчика в Steam-обсуждении; на вики не описан):**

```
%USERPROFILE%\AppData\LocalLow\Rebuilt Games\Pummel Party\WorkshopMods\<имя мода>\
```

Каждый мод редактора лежит в своей папке с именем мода. Разработчик советует делать резервную копию этой папки перед **File > Delete Mod**. Пользовательский ответ (2024) указывает ту же папку и для скачанных workshop-модов, с оговоркой «видны только unlocked-моды» — т.е. в редакторе доступны для открытия только unlocked; где именно лежат подписки (эта папка или `steamapps\workshop\content\880940`), **не задокументировано**. PCGamingWiki подтверждает базовую папку сохранений `%USERPROFILE%\AppData\LocalLow\Rebuilt Games\Pummel Party\`. Steam AppID игры — 880940.

**Формат файлов проекта: не задокументирован.** Ни вики, ни обсуждения не называют формат (JSON, бинарный, расширения файлов). Единственный документированный текстовый формат — экспорт/импорт custom lighting profile в **`.json`** (Lighting_Settings). Папка `Mods` в каталоге установки игры (`steamapps\common\Pummel Party\Mods`) относится к сторонним загрузчикам (MelonLoader/BepInEx), а не к Mod Editor. Для уточнения формата нужно заглянуть в `WorkshopMods` на машине с созданным модом.

---

## 10. Все обработанные URL

Успешно прочитаны (вики):
- https://workshop.pummelparty.com/wiki/Main_Page
- https://workshop.pummelparty.com/wiki/Special:AllPages (109 страниц)
- https://workshop.pummelparty.com/wiki/Introduction_to_the_Mod_Editor
- https://workshop.pummelparty.com/wiki/Opening_The_Mod_Editor
- https://workshop.pummelparty.com/wiki/Tutorials/Creating_Your_First_Mod
- https://workshop.pummelparty.com/wiki/Tutorials/Building_A_Board_Mod
- https://workshop.pummelparty.com/wiki/Tutorials/Building_A_Minigame_Mod
- https://workshop.pummelparty.com/wiki/Board_Mod
- https://workshop.pummelparty.com/wiki/Your_First_Board
- https://workshop.pummelparty.com/wiki/Minigame_Mod
- https://workshop.pummelparty.com/wiki/Mod_Settings
- https://workshop.pummelparty.com/wiki/Lighting_Settings
- https://workshop.pummelparty.com/wiki/Screen_Effects
- https://workshop.pummelparty.com/wiki/Hierarchy_Window
- https://workshop.pummelparty.com/wiki/Hierarchy_Window_Actions_and_Shortcuts
- https://workshop.pummelparty.com/wiki/Inspector_Window
- https://workshop.pummelparty.com/wiki/Scene_View
- https://workshop.pummelparty.com/wiki/Asset_Browser
- https://workshop.pummelparty.com/wiki/Gameobject
- https://workshop.pummelparty.com/wiki/Mod_Editor_Shortcuts
- https://workshop.pummelparty.com/wiki/General_Actions_and_Shortcuts
- https://workshop.pummelparty.com/wiki/Custom_Board_Space
- https://workshop.pummelparty.com/wiki/Board_Space_Component
- https://workshop.pummelparty.com/wiki/Player_Spawn_Component
- https://workshop.pummelparty.com/wiki/Spawner_Component
- https://workshop.pummelparty.com/wiki/Prop_Component
- https://workshop.pummelparty.com/wiki/Mesh_Renderer_Component
- https://workshop.pummelparty.com/wiki/Mesh_Collider_Component
- https://workshop.pummelparty.com/wiki/Simple_Animator_Component
- https://workshop.pummelparty.com/wiki/Importing_Models
- https://workshop.pummelparty.com/wiki/Importing_Images
- https://workshop.pummelparty.com/wiki/Importing_Audio
- https://workshop.pummelparty.com/wiki/Mesh_Asset
- https://workshop.pummelparty.com/wiki/Texture_Asset
- https://workshop.pummelparty.com/wiki/Audio_Clip_Asset
- https://workshop.pummelparty.com/wiki/Material_Asset
- https://workshop.pummelparty.com/wiki/Prefab_Asset
- https://workshop.pummelparty.com/wiki/Prefab_Instance_Component
- https://workshop.pummelparty.com/wiki/Log_Window
- https://workshop.pummelparty.com/wiki/Mod_Validator
- https://workshop.pummelparty.com/wiki/Publishing_to_the_Steam_Workshop
- https://workshop.pummelparty.com/wiki/Published_Mods_Window
- https://workshop.pummelparty.com/wiki/Unlocked_Mod
- https://workshop.pummelparty.com/wiki/Mod_Browser

Steam / прочее:
- https://steamcommunity.com/workshop/discussions/18446744073709551615/3730701797624973127/?appid=880940 — путь к WorkshopMods, Delete Mod, восстановление (разработчик)
- https://steamcommunity.com/app/880940/discussions/0/4288062841579270741/ — путь к WorkshopMods (пользователь)
- https://steamcommunity.com/app/880940/discussions/0/1742229167210148773 — тред 2018 г., без полезной информации
- https://steamcommunity.com/app/880940/eventcomments/5047948127380020911 — анонс 2021 г., без полезной информации
- https://steamcommunity.com/sharedfiles/filedetails/?id=3437967775 — оказался гайдом по Hearts of Iron IV, не относится к игре

Недоступны (HTTP 403/429), содержимое получено косвенно через WebSearch:
- https://steamdb.info/patchnotes/10103260 — Update 1.12.1: «Mod Editor Beta», шесть шаблонов мини-игр, Action Editor, импорт PNG/JPG, WAV, OBJ, ссылка на workshop.pummelparty.com
- https://techraptor.net/gaming/news/pummel-party-update-adds-new-minigames-mod-workshop-and-more — обзор обновления (8 дек 2022)
- https://store.steampowered.com/news/app/880940?updates=true — только навигация, текст анонса не получен

Не читались (вне задачи — каталог Actions/Events, прочие компоненты): Action, Action_Editor, Event, Logic_Component, *_Action, Item/Trigger/Weapon/Destructible/Mover/Water/Text/Light/Line_Renderer/Particle_System/Audio_Source/Box/Capsule/Sphere_Collider/Transform/Note/AI_Navigation_Node Components, Component, Rendering_Components, Board_Space_Event_Component, Inspector_Window_Actions_and_Shortcuts, Scene_View_Actions_and_Shortcuts, Asset_Browser_Actions_and_Shortcuts, Tutorial/Creating_Your_First_Mod, Your_First_Board_Map, Your_First_Minigame.

Reddit-тредов по редактору через WebSearch не найдено.
