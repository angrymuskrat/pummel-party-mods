# Формат проекта Mod Editor на диске и генерация сцен кодом

Собрано 2026-10-21 декомпиляцией `Assembly-CSharp.dll` (ilspycmd 11.1, игра на Mono, Unity 2021.3.45f2) и сверено с 14 сценами и 58 префабами из `StreamingAssets` и `WorkshopMods`. Инструменты в репозитории: `tools/pmscene.py` (парсер/сериализатор, roundtrip побайтово совпадает на всех образцах) и `tools/pmgen.py` (генератор модов). Пример использования — `packs/abandoned-park/minigames/tickets/build_mod.py`.

## Папка мода

```
WorkshopMods/<Name>/
  Data/MainScene.scene            PMH, иерархия без корня (ignoreRoot)
  Data/ModSettings.json           SimpleMinigameSettings + SimpleModPlayerSettings (JsonUtility)
  Data/Meta.json, WorkshopItem.json, MinigameDefinitionData.json, Lighting.json   JSON
  Data/PostProcessing.data        бинарный (ModDataReaderWriter.SavePostProcessSettings)
  Data/Preview.jpg
  Assets/Props/*.obj + .pmeta     Assets/Textures/*.png|jpg + .pmeta     Assets/Audio/*.wav + .pmeta
  Assets/Prefabs/*.pfab + .pmeta  PMH с настоящим корнем (SaveTransform без ignoreRoot); корень неактивен
  Assets/Materials/*.pmat + .pmeta   .pmat = заглушка «PMAT», данные материала в pmeta.m_shaderData
```

Ассеты находятся сканированием `Assets/**` (`PummelMod.cs`), индекса нет. Отсутствующий `.pmeta` редактор создаёт сам с новым GUID (`PummelAssetImporter.TryCreateOrLoadMetaAsset`), поэтому для ссылок из сцены `.pmeta` надо писать самим. `assetLocation` у внешних ассетов всегда `757b15db-4305-4406-b767-1ec002daa769`.

## PMH (ModHierarchySerializer)

Все строки — .NET `BinaryWriter`: 7-битная длина + UTF-8. Little-endian.

```
string "PMH"  u16 major=1  u16 minor=0
[сцена]   u16 rootCount, затем rootCount объектов
[префаб]  один объект
объект:   string name, bool active, i32 layer, string tag, u16 childCount, дети (рекурсивно)
далее для каждого объекта в порядке обхода (pre-order):
          string transformGuid, i32 n, n × (string typeName, string componentGuid, bool enabled)
далее для каждого компонента в том же порядке:
          u16 k, k × (string propName, i32 size, payload[size])
```

Свойство = публичное свойство класса компонента без `[ModIgnore]` (DeclaredOnly) плюс `guid` из `ModBehaviour`; порядок — порядок объявления. Благодаря `size` незнакомые свойства можно пропускать и переносить как есть.

### Кодировка значений (ModReflectionTypes.WriteType)

| Тип | Байты |
| --- | --- |
| bool / int / float / string | 1 / i32 / f32 / string |
| enum, [Flags] | i32 |
| Vector3 / Color | 3×f32 / 4×f32 (RGBA 0..1) |
| SerializableGuid | string (36 символов) |
| массив | i32 count + элементы |
| ссылка на ассет или компонент (Prop, Material, Mesh, AudioClip, Transform, PummelPrefab…) | bool + string guid (`Extensions.WriteObject`); `00` = null |
| ModComplexFloat | JSON `{"valueType":0|1,"min":x,"max":y}` (0 — константа `min`, 1 — случайно между) |
| ModLogicTrigger | u16 тип + JSON триггера + u16 n + n × (u16 тип действия + JSON действия); при чтении `Actions` берутся из явного списка |
| ModLogicTrigger[] (ModLogic.Triggers) | i32 count + триггеры |

Слои: `WorldGround` = 10 (пол, обязателен для досок), в шаблонах стены `LowPolyCube` стоят на 11.

### Типы триггеров (ModTriggerType) и действий (ModActionType)

Триггеры: None 0, Start 32, Enable 40, Update 48, Hit 64, WeaponHit 80, Timer 96 (`m_interval`: ModComplexFloat), BoardSpace 112, RoundStart 128, RoundEnd 144.

Действия: Wait 32, Kill 64, ChangeHealth 96, ChangeScore 128, SpawnEffect 160, Scale 256, SetColor 288, SetActive 320, PlayTweenAnimation 352, Position 384, Rotation 416, SetGravity 448, SetPlacement 480, ModifyPlayer 512, PlaySound 544, SpawnPrefab 576, HealPlayer 608, DamagePlayer 640, GiveKeys 672, DropKeys 704, GiveTrophy 736, GiveItem 768, SpawnKeys 800, ChangeVelocity 832, MoveSpace 864, ShowMessage 1024, GiveMinigameItem 1056, StunPlayer 1088, DropMinigameItem 1120, MatchTransform 1184, SetPlayerVisual 1248, SetConnectionActive 1280, SetBoardSpaceActive 1312, BoardPopup 1344, RemoveTrophy 1376.

JSON действия: `m_type`, `m_version: 0`, у `TargetAction` — `m_targetFlags` (Source 1 = кто вызвал событие: вошедший в триггер, подобравший предмет; Receiver 2 = объект с компонентом; Advanced 4 = список `m_targets[{"m_assetGUID":{"serializedGuid":…}}]` с GUID компонентов), далее поля класса: `m_operation`/`m_value` (ChangeScore, ChangeHealth), `m_effectType` (SpawnEffect: Wood 0, Blood 1, Explosion 2, Confetti 3, Sparkles 4), `m_messageTarget`/`m_message`/`m_duration` (ShowMessage), `m_seconds` (Wait, ComplexFloat), `m_newState` (SetActive: Enabled 0, Disabled 1, Toggle 2), `m_stunDuration`, `m_value` Vector3 (SetGravity), `m_operation`/`m_space`/`m_localTarget`/`m_velocityDir`/`m_customDir`/`m_speed` (ChangeVelocity: Up 0 … TowardsSource 6, TowardsReceiver 7, Custom 8), `m_clip`/`m_volume` (PlaySound), `m_transformToMatch`/`m_transformValuesToMatch` (MatchTransform, флаги PosX 1 … RotZ 32), `m_color` {r,g,b,a} (SetColor: цель — трансформ или Prop → tint этого Prop; Logic → все дочерние props), `m_tweenType` (PlayTweenAnimation: WorldPosition 0, LocalRotation 1, LocalScale 2, LocalPosition 3, RotateAroundLocalAxis 4, RotateAroundWorldAxis 5, WorldRotation 6)/`m_easeType` (LeanTweenType: linear 1, easeOutQuad 2, easeInQuad 3, easeInOutQuad 4, …)/`m_time`/`m_startValueType`/`m_startValue`/`m_endValueType` (Current 0, Specific 1, Offset 2 — прибавка к текущему)/`m_endValue`/`m_rotationAxis`/`m_rotationDegrees`.

### Схема ключевых компонентов (имя свойства: тип)

- `ModTransform`: position, rotation (Euler), scale: Vector3.
- `ModProp`: prop: ref, tintColor: Color, collisionType: enum (None 0, Box 1, Sphere 2, Mesh 3), shadowCastingMode: enum, customMaterials: ref[].
- `ModTrigger`: TriggerShape (Custom 0, Box 1, Sphere 2, Capsule 3), Size, Center: Vector3, Radius, Height: float, TriggerOnHit/OnEnter/OnExit/OnStay: bool, OnHitActions/OnEnterActions/OnExitActions/OnStayActions: ModLogicTrigger, StayTriggerInterval: float, DisableAfterTriggered, OneUsePerPlayer: bool.
- `ModLogic`: Triggers: ModLogicTrigger[].
- `ModPlayerSpawn`: SharedSpawn: bool, SpawnUsageType: flags (Initial 1, Respawn 2), AllowedPlayers: flags 8 бит, SpawnShape (Point 0, Line 1, Circle 2), PlayerCountMask: flags 8 бит, SpawnDistribution (Step 0, Random 1), LineLength, Radius: float, Advanced: bool.
- `ModSpawner`: Prefabs: ref[], PrefabGUIDs: string[], Interval1, Delay: ComplexFloat (JSON), Type (AlwaysSpawn 0, SpawnOnDestruction 1), LocationType: flags (OnSpawner 1, OnTargets 2), SpawnPoints: ref[] (GUID `ModTransform`), SpawnCount: int.
- `ModMover`: DirectionType (Up 0, Down 1, Left 2, Right 3, Forward 4, Back 5, Custom 6 — локальные оси объекта, Custom = вектор Direction), Direction, Speed (ед/с), RotationAxisType (X 0, Y 1, Z 2, Custom 3 — мировые оси, `Rotate(axis, speed·dt, Space.World)`), RotationAxis (только при Custom), RotationSpeed (град/с).
- `ModWater`: Width, Height: int, CellSize: float, DeepColor, ShallowColor, FrothColor: Color, WaveHeight, WaveSpeed: float. Сетка центрирована на позиции объекта: от −Width·CellSize/2 до +Width·CellSize/2 (`LowPolyWater.cs`, вершины `i·cellSize − cellSize·width/2`).
- `ModSimpleAnimator`: UseLocalPosition, UseLocalRotation, UseLateUpdate: bool, TimeOffset: float, Animations: i32 n + n × JSON анимации. JSON: `AnimationPreset` (Custom 0, Move Along Line 1, Orbit Position 2, Rotate Around Axis 3), `AnimationLayers` [{`rid`}], `m_animationName`, `m_helpText`, у Orbit ещё `m_orbitFrequency`; слои — `references` (`version` 2, `RefIds` с классом `SimpleAnimationLayer`: `AnimationSpeed` (частота/с), `AnimationOffset`, `UseRandomAnimationOffset`, `AnimationType` (позиция 0, поворот 1), `AnimationAxis` (Vector3; для Move Along Line — направление × дистанция), `AnimationCurve` (Unity AnimationCurve, `m_PreInfinity`/`m_PostInfinity` 2)). Образцы сняты 2026-10-22 из `InbuiltMods/Foggy Fall`: Rotate — линейная кривая 0→1; Move Along Line — 0→1→0; Orbit — два слоя X и Z, кривая −1→1→−1, у второго `AnimationOffset` 0.25. Старый формат (`references` `version` 1 с ключами `00000000` и `id`) встречается в шаблоне Third Person Obstacle Course. В `pmgen.py` есть `anim_rotate_around_axis` и `anim_move_along_line` (JSON второго совпадает с Foggy Fall побайтово по содержанию). `TimeOffset` — сдвиг фазы в секундах.
- `ModItem`: ItemType (Carried 0, Weapon 1, Worn 2, Pickup 3), WeaponInfo: JSON ModWeaponInfo, ItemPrefab: ref + ItemPrefabGUID: string (визуальный префаб), … , OnPickupTrigger/OnDropTrigger/OnUseTrigger/OnWhileHeldTrigger: ModLogicTrigger, ItemSlot: enum. Пример из игры (HealthKit): Pickup, CanBeDropped false, DisappearWhenDropped true, AutoDropAfterTime true, OnPickup → ChangeHealth Source Add 40.
- `ModBoxCollider`: center, size. `ModNote`: Text. `ModPrefabInstance`: PrefabReference: ref, PrefabGUID: string.

Полная схема по всем компонентам (включая ModParticleSystem, ModText, ModBoardSpace) печатается командой `python tools/pmscene.py schema <сцены…>`.

## GUID встроенных props (сняты со сцен)

LowPolyCube `cfc9faf9-3852-4dbe-803b-32cec4c94139`, LowPolyPlane `e314a70b-98f2-4459-9214-ef4da97b4e6d` (есть и второй plane `331019a7-e85f-47d4-a19d-703dc99a3fab`), LowPolySphere `c7d7ef4d-4e66-4b08-b91a-d5b0190b74ee`. Остальные встроенные props по имени не найти (каталог Addressables бинарный); брать GUID из сцены, где такой prop расставлен.

## Материалы (PummelMaterial)

`.pmat` на диске — 5 байт (`\x04PMAT`), содержимое в `pmeta.m_shaderData` (массив байт JSON): `"PMAT"`, u8 0, u8 2, i32 n свойств шейдера, n × (string имя, u8 тип: Color 0 / Vector 1 → 4×f32, Float 2 / Range 3 → f32, Texture 4 → ref), i32 число keywords + строки, Vector2 mainTextureScale, Vector2 mainTextureOffset. Список свойств `Standard Decal Receiver` зашит в `pmgen.material_shader_data`.

## ModSettings.json

`EndConditions` — флаги SimpleMinigameEndCondition (Timer 1, ObtainPoints 2, RemainingPlayersAlive 4, FinishMinigame 8); `PlacementCondition` (MostPoints 0, LeastPoints 1, FinishOrder 2, LastManStanding 3); `ChosenPlayerType` (ThirdPerson 0, TopDown 1, TwinStick 2); `SpawnType` PlayerSpawnType (PortalAbove 0, None 1, PortalAboveNoAnimation 2). Остальные поля — см. файл шаблона.

## Поведение игры по коду (декомпиляция 2026-10-21, прочитано 2026-10-22)

- **Спавны.** `ModMinigameValidator.ValidateSpawnPoints`: среди спавнов с `InitialSpawn` нужно ≥ 8 необщих или ≥ 1 общий (`SharedSpawn`), иначе ошибка «There are not enough spawn points for all players». `ModPlayerSpawn.DetermineInitialSpawnPoints` выбирает каждому игроку случайный подходящий спавн; необщий после этого выбывает. Игроку, которому спавна не хватило, позиция не назначается. `Circle` + `Step`: N игроков в точках t = i/N (при N < 3 шаг 0.5) по окружности от +X, лицом к центру; `Line`: вдоль `transform.right`. Точка прижимается к полу лучом вниз.
- **Арифметика очков и здоровья.** `Extensions.PerformOperation`: `Divide` = `(int)((float)i / value)` (отбрасывание дробной части; деление на 0 не меняет значение), `Multiply` = `i * value`. Очки — `short`, обрезаются до ±32767.
- **Событие смерти** (`SimpleModPlayer.KillPlayer` → `onDeathTrigger`): `Source` — убийца или последний, кто нанёс урон; `Receiver` — умерший. Срабатывает только если с респауна прошло больше `respawnInvulnerableTime`. Урон кулаком: `punchDamage` вычитается из `health`; при 0 — смерть. Kill Action убивает сразу.
- **Триггеры игрока в ModSettings.json** (`onDeathTrigger`, `onRespawnTrigger`, `onFirstSpawnTrigger`, `hitTrigger`, …): `m_actions` = `[{"rid": 1000}, …]`, сами действия — в корневом `references` (`version` 2, `RefIds`, класс `ModSystem.Logic.<Имя>Action`, данные как JSON действия). Образец — `InbuiltMods/Aftershock Arena`. В `pmgen.Mod` — поле `player_triggers`.
- **Боты** (`SimpleModPlayer.GetAIInput`, `UpdateTargetType`). Приоритет цели: 1) первый узел `AI Navigation Node` с `Is AI Goal` — все боты идут к нему и стоят; 2) если бот держит оружие — гонится за случайным живым игроком; 3) если на карте есть свободное оружие (`Item Type` = `Weapon`, не в руках) — идёт к ближайшему; 4) иначе бежит в случайную точку пола в пределах ~8 м. Без оружия бот бьёт кулаком при каждом откате удара. Предметы `Pickup` (билеты) боты не ищут. Узлы `AI Navigation Node` с `Connected Nodes` задают граф путей. Путь (`ModAINavigation.GetPath`, проверено 2026-10-25): начало и конец — узлы, ближайшие к боту и к цели **из тех, что видны** (`Physics.Linecast` по слоям 0, `WorldGround`, `WorldWall`, маска 3073); дальше поиск по возрастанию длины пути, но узел помечается при постановке в очередь, а не при извлечении. Поэтому узел-цель, в который ведут связи из нескольких узлов, достаётся первому из них, извлечённому из очереди, — ближайшему к боту по пути, даже если цель стоит у другого. Нет пути — бот идёт к цели по прямой. Список узлов собирается в `Awake`, и `GetAIGoalNode` не проверяет, активен ли узел, поэтому переключить цель через `Set Active` по коду нельзя.
- **Три превью мода.** `Data/Preview.jpg` — картинка в окне «Load a saved mod» (`ModSelectPopup.LoadPreviewImage` → `Texture2D.LoadImage`, формат по содержимому, PNG тоже читается); редактор перезаписывает её снимком камеры окна сцены 640 × 360 JPEG при каждом сохранении (`EditorSystem.SaveCurrentMod` → `SavePreviewScreenshot`). `MinigameDefinitionData.json` → `ScreenshotTextureGuid` — `Preview Image` мини-игры в игре (`Mod Settings` → `Minigame Details`), текстура-ассет; F10 в редакторе делает снимок (`TakePlayModeScreenshot`). `WorkshopItem.json` → `previewImageGuid` — `Square Preview` из окна публикации. `pmgen.Mod.write` не трогает снимок редактора (любой JPEG, кроме шаблонного), `ScreenshotTextureGuid` и `WorkshopItem.json`, если они уже есть; своё превью — `Mod.preview_image`.
- **Сетка ботов кодом:** `pmgen` — `Obj.ai_node()` и `link_ai_nodes(узлы, пары)`; `ConnectedNodes` хранит GUID компонентов `ModAINavigation` (так во всех сценах игры, 24–104 узла). Порог «узел достигнут» — 1.6 м (`m_nodeReachedDist`); после последнего узла бот продолжает идти к точке узла, а не к цели. Генерация по карте занятости — `pummel-party-level-design/scripts/navgen.py`.
- **Спавнер `OnTargets`** (`ModSpawner.Spawn`): у каждого из `Spawn Count` слотов при появлении выбирается случайная свободная точка из `SpawnPoints` (GUID трансформов); занятая возвращается в пул, когда её предмет уничтожен. Спавненный предмет — кинематический (`ModItem`: `isKinematic = true`), висит в точке появления и к движущимся объектам не крепится.
- **Случайность в действиях** (исправлено 2026-10-25). `Wait` с диапазоном, `Spawn Prefab`, `Give Item`, `Move To Space` берут `ModEvent.GetActionRandomness()`: `new Random(Seed)` и пропуск стольких значений, каков номер действия в списке (`CurrentActionIndex`). Поэтому разные `Wait` одной цепочки получают разные числа. Сид создаётся в конструкторе события во время игры: `GameManager.rand.Next()`, а `GameManager.rand` засевается `Guid.NewGuid()` при запуске игры (`GameManager`). Значит, паузы разные в каждом матче. Сериализуется сид только при пересылке события по сети (`ModEvent.Serialize`), не в сцене. Действия `ServerRelay` (`Set Active`, `Play Tween Animation`, `Spawn Prefab`) клиенты выполняют по команде сервера, так что моменты у всех совпадают. Прежняя запись «сид в сцене, паузы одинаковы в каждом матче, одинаковые `Wait` в цепочке дают одно число» была ошибкой.
- **`On Stay` у триггера** (`ModTrigger.OnEvent`, 2026-10-25). Событие шлёт `SimpleModPlayer.OnTriggerStay` только у владельца игрока (`IsOwner`). Интервал общий на триггер: `Time.time − m_lastTriggerTime > Trigger Interval`, но время сбрасывается в `Update`, после физики, — в кадре срабатывания действие получают все игроки внутри, каждый со своим `Source`. Если в кадре два шага физики, сработает дважды.
- **`Kill/Destroy` на объекте** (`KillAction.ExecuteOnTarget`) не вызывает `Destroy`: помечает объект уничтоженным и выключает (`SetActive(false)`). `OnDestroy` компонентов не вызывается, например узел `AI Navigation Node` остаётся в `ModAINavigation.Nodes`.
- **Цель ботов и поиск пути** (2026-10-25). Бот читает позицию цели каждый кадр (`m_curAiTarget = m_aiGoal.transform.position`), так что подвижный узел-цель работает (Mascot Throne: узел — ребёнок летающей короны). `ModAINavigation.GetPath`: старт и финиш — ближайшие узлы к боту и к цели (`FindClosest`, с `Linecast` по слоям 0/10/11); поиск помечает узел при постановке в очередь, а не при извлечении, поэтому путь не всегда кратчайший: в узел с несколькими входами войдут из того соседа, который раньше раскрылся. Узел регистрируется в `Awake`: объект, выключенный в сцене, попадает в список только при первом включении, а до этого `GetNodeID()` = `int.MaxValue` — связь на такой узел из активного обрушит поиск (`BitArray.Get` за границей). Загрузчик сцены выставляет `active` до добавления компонентов (`ModHierarchySerializer`).
- **Удар без здоровья убивает.** При `useHealth` = выкл. `MaxHealth` = 1, а удар вычитает `punchDamage` через `ChangeHealth` → при 0 `KillPlayer` (тряпичная кукла летит от бьющего). Чтобы удар не убивал — `punchDamage` = 0 (только вздрагивание). Отброса у удара нет; его делают в `weaponHitTrigger` (Source — бьющий, Receiver — получивший), но у этого триггера фильтр `m_hitType` (Melee 1, Projectile 2) по умолчанию 0 — тогда он не срабатывает ни на что. `punchStunDuration` приводится к `ushort`: дробные секунды обрезаются, 0.8 → без оглушения.
- **Таймер игрока** (`tickTrigger` в `ModSettings.json`, `Interval` — ComplexFloat): тикает только у живого игрока, пока раунд идёт (`SimpleModPlayer.Update`: `IsOwner && Playable && !IsDead`); событие с `Source` = `Receiver` = сам игрок. Так делаются очки за время выживания (Death Carousel: `Change Score` `Add` 1 раз в секунду). `Change Score` пускает счёт в минус (до −32768).
- **Гравитация** (уточнено 2026-10-25 для Tilt House). `Set Gravity` пишет глобальный `Physics.gravity` и `SetCustomGravity(вектор)` каждому игроку. Игроку достаётся **весь вектор**, а не только длина: каждый кадр `velocity += вектор · m_gravityProportion · dt` (`ApplyCustomForces`). `m_gravityProportion = playerGravity / Physics.gravity.magnitude` считается один раз в `ApplyModSettings` при старте, поэтому вертикаль −9.81 даёт игроку его `playerGravity`, а горизонталь g — боковую тягу g · `playerGravity` / 9.81. На земле боковая тяга работает порогом (`CharacterMover.CalculateVelocity`): после тяги горизонталь по каждой оси шагает к «ввод × бег» с темпом `Acceleration` (есть ввод по этой оси) или `Deceleration` (нет), и если шаг перекрывает разницу, скорость встаёт ровно на цель. Тяга ниже темпа на земле не видна совсем, выше — разгоняет на «тяга − темп» без предела; в воздухе темп — `midAirMovementAcceleration`. При упоре в стену скорость не обнуляется и копится. Модель по кадрам — `packs/abandoned-park/minigames/tilt-house/slide.py`. `SimpleModController` сам ставит −9.81 в `InitializeMinigame` и `OnDestroy`, возвращать вручную не нужно.
- **Движущиеся опоры.** `CharacterMover.DoPlatformMovement` переносит стоящего игрока вслед за трансформом, на который он встал (`Mover`, `Simple Animator`, твины), если на префабе игрока включён `m_movingPlatformImprovements` (значение в коде не видно; Foggy Fall катает игроков на 22 блоках `Move Along Line`). Движущийся коллайдер игрока не толкает — толчки делаются триггером с `Change Player Velocity`. Телепорт игрока (`SimpleModPlayer.TeleportPlayer`, в начале каждого раунда) запомненную опору не сбрасывает. `Mover` работает всегда, пока объект активен, и включить его позже нельзя, не выключив объект; отложенное или ускоряющееся вращение — цепочка `Play Tween Animation` `RotateAroundWorldAxis` + `Wait` той же длительности (Death Carousel).
- **Приём «предмет-приманка для ботов»** (Ticket Rush, 2026-10-22, в игре не проверен): собираемый предмет делается `Weapon` (`Melee`, урон 0) с `AutoDropAfterTime` = вкл., `DropAfterTime` = 0 и `DisappearWhenDropped` = вкл. Подбор касанием, `On Pickup` срабатывает как у `Pickup`, через кадр предмет сбрасывается и уничтожается (`MarkAsDestroyed`, спавнер `Spawn On Destruction` перезапускается). Боты без оружия идут к ближайшему такому предмету.

- **Гонки: финиш, места, возвраты** (прочитано 2026-10-24 для Coaster Run). `Set Placement` → `SimpleModPlayer.SetFinished`: один раз за раунд прибавляет к очкам 100 · (N − k), где k — сколько уже финишировали, и показывает «… finished»; игрок **остаётся в игре** (ходит, бьёт). `FinishMinigame` завершает раунд, когда финишировали все. `Finish Order` отдельной логики не имеет — `BuildResults` берёт очки, поэтому дополнительные очки за рубежи ранжируют тех, кто не добежал. Респаун (`ModPlayerSpawn.DetermineRespawnPoint`) выбирает **случайный** спавн с `Respawn`, так что чекпоинтами спавны быть не могут. Шаблон `Third Person Obstacle Course` возвращает упавших триггерами под секциями: `Position Action` (`Set`, World) на `Source` — он просто ставит `transform.position`. `Match Transform` на игроке после этого вызывает `SimpleModPlayer.TeleportPlayer` (сброс агента, поворот модели и камеры по Y); в `pmgen` — `act_match_transform(..., flags=Targets.SOURCE)`.
- **Прыжки ботов** (`SimpleModPlayer.GetAIInput`): бот жмёт прыжок, как только оторвался от опоры дольше 0.35 · `coyoteTime`, но не чаще раза в 0.5 с. То есть он прыгает, сбегая с края, и разрывы до ~3 м по пути между узлами берёт сам; запрыгивать на уступы выше ступеньки он не умеет.
- **Выстрел игроком** (прочитано 2026-10-25 для Human Cannonball, в игре не проверено):
  - `Change Player Velocity` с `Direction Type` = `Custom` берёт вектор `m_customDir` **без нормализации** и умножает на `Speed` (`ChangeVelocityAction.GetDir`). При `Space` = `Local` вектор умножается на `localToWorldMatrix` объекта из `Local Space Of`: `Source` 0, `Receiver` 1 (у триггера — его объект), `Target` 2. Масштаб тоже входит в вектор. Действие выполняет только владелец игрока, и только живого.
  - В воздухе `CharacterMover` тянет горизонтальную скорость к «ввод × бег» с темпом `midAirMovementAcceleration`: игра пишет его и в `airAcceleration`, и в `airDeceleration` (`SimpleModPlayer.ApplyModSettings`). Шаг идёт вдоль нормали разности, раздельно по X и Z. Поэтому быстрый полёт гасится одинаково при вводе «вперёд», «назад» и без ввода, а вбок доруливают слабее, чем дал бы полный темп. В кадр `Set` расчёт скорости пропускается (`m_velocityWasSet`).
  - Гравитация игрока = `playerGravity` (`ApplyCustomForces`: базовая (0, −9.81, 0) · `playerGravity` / 9.81; вектор целиком, см. «Гравитация»).
- **`ServerRelay` держит цепочку** (`ModActionRunner`). Клиент не выполняет действие `ServerRelay` (`Match Transform`, `Set Active`, `Play Tween`, `Spawn Prefab`), пока сервер его не ретранслирует. Следующие действия ждут его же (тайм-аут 10 с). Так что «`Match Transform` → `Change Player Velocity`» задаёт скорость уже после переноса.
- **Между раундами** (`SimpleModController.RoundEnded`/`StartNewRound`) игра переносит игроков на стартовые спавны, восстанавливает здоровье и снимает флаги финиша. Очки **не** обнуляются. Сцена не перезагружается: выключенные объекты и сдвинутые твинами остаются как были.
  - **Пауза между раундами:** 1 с до переноса на старт (`m_roundResetDelay`) и 2 с до нового раунда (`m_roundStartDelay`).
  - Физика игрока в паузе идёт: `UpdateController` работает у любого живого игрока, только ввод обнулён.
  - Смерти нет: `KillPlayer` пропускает её при `m_isBetweenRounds`.
  - Скорость персонажа перенос не обнуляет (`TeleportPlayer`).
  - Вывод: под каждой смертельной зоной, куда можно упасть в конце раунда, нужен твёрдый пол, иначе игрок падает в пустоту (Human Cannonball, плейтест 2026-10-25).
- **`One Use Per Player` навсегда.** `ModTrigger.m_activatedPlayers` не очищается ни при смерти, ни между раундами. В игре на несколько раундов такой триггер во втором раунде уже молчит.
- **`Round Start` и выключенные объекты.** `RoundStartTrigger` подписывается на `GameManager.Minigame.OnNewRoundStart` в `OnEnable` и отписывается в `OnDisable` (только на сервере). Выключенный объект событие не получает. Отсюда смена раунда без счётчика: этапы `Stage_1..N`, включён первый, каждый по `Round Start` включает следующий и выключает себя (Human Cannonball).
- **Переносимый предмет и отбор** (прочитано 2026-10-25 для Sugar Rush, в игре не проверено):
  - Подбор — касанием: `ModItemTrigger.OnTriggerEnter` на сервере → `SimpleModPlayer.TryGiveItem`, кнопки нет. Стан не мешает.
  - `'While Held' Actions` срабатывают раз в `SecondsBetweenHeldAction` у владельца игрока (`ModItem.UpdateHeld`), `Source` — держащий, `Receiver` — предмет. `'On Drop'` тоже с `Source` = держащий.
  - Сброс (`BeginDropItem`) бросает предмет: старт в 1 м вдоль `(forward + up)` от предмета, скорость 6 м/с туда же плюс скорость игрока. В полёте тяжесть 25 м/с² (`ModItem.FixedUpdate`). Предмет ложится на первую опору с нормалью вверх, в том числе на игрока (`HandleThrownItemCollision`), и снова подбирается. Если `Disappear When Dropped` выключен и предмет упал туда, куда не дойти, — он потерян: спавнер `Spawn On Destruction` ждёт уничтожения.
  - Кнопка сброса работает только при `Can Be Dropped` (`ThrowLastDroppableItem`). `Drop Minigame Item` (`ServerNoRelay`, `ForceDropItemInSlot`) этот флаг не проверяет. В `weaponHitTrigger` действие доходит до сервера: событие удара идёт через `ExecuteTriggerAndRelayEvent`. В `pmgen` — `act_drop_minigame_item`.
  - С `Weapon` в руке кулака нет: удар заменяет взмах предмета (`StartMelee` с `meleeInfo`), это тоже `Melee` для `weaponHitTrigger`. Урон 0 событие не отменяет. Оглушение из удара — `ushort`, дробные секунды обрезаются.
  - Шаблоны префабов в игре загружены активными (`PummelPrefabImporter`: `SetActive(isEnabled)`). Узел `AI Navigation Node` внутри префаба-визуала поэтому, судя по коду, зарегистрируется и из шаблона (`ModAINavigation.Awake` при `IsPlayMode`). Делать из него подвижную цель ботов небезопасно.
- **`Simple Animator` по коду** (`SimpleAnimator`, `SimpleAnimationLayer`):
  - `ModSimpleAnimator` включает `SetServerControlState`: на клиентах время = `SmoothServerTime`, движение синхронно; исходный поворот объекта сохраняется (`m_useBaseRotation`).
  - Слой поворота — `AngleAxis(кривая(t) · 360°, AnimationAxis)` поверх исходного поворота; слой позиции — `кривая(t) · AnimationAxis` от исходной позиции.
  - Пресет `Custom` (0) — произвольные слои, имя «Custom Animation» (`ModSimpleAnimations.CustomAnimation`); в `pmgen` — `anim_swing`.

## Статус проверки в редакторе

2026-10-25: плейтест четырёх модов Rusted Park после второго раунда прожарки — по общему отчёту пользователя «всё работает». Впервые собранные кодом и теперь подтверждённые: `Spawn Prefab` в `onDeathTrigger` (`pmgen.act_spawn_prefab`, Ticket Rush — билет выпадает из умершего), `Modify Player` с `Wait` в `onRespawnTrigger` (Mascot Throne), `Play Tween Animation` и `Set Color` (Death Carousel, Mascot Throne, Coaster Run), `Simple Animator`, `Match Transform` на игроке. Отдельные пункты чеклистов (ощущения, поведение ботов) пользователь построчно не описывал.

2026-10-21: сгенерированный `Ticket Rush Gen` открылся в Mod Editor, Hierarchy показывает все объекты (World, Ticket Spawners, Director), Player.log без ошибок. Значит наши `.pmeta`, префабы `.pfab`, JSON триггеров с пустым `references` и ModSettings редактор принимает. По скриншоту редактора: Log 0 warnings / 0 errors, материалы из `m_shaderData` работают (текстуры на киосках и полу видны), триггеры и спавнеры отображаются гизмо. Плейтест 2026-10-21 (1 игрок + 3 бота, полный раунд до экрана результатов): в Player.log ни исключений, ни ошибок загрузки; `Running Round Start Logic Trigger` — триггер ModLogic выполнился; звук подбора проигрывался. По словам пользователя в игре работало всё из чеклиста: подбор билетов с очками, респаун билетов спавнером, kill-зона пруда с респауном, jump pad (`ChangeVelocity` Up/Set), таймер и места по очкам. Генератор можно считать рабочим для компонентов Prop, Trigger, Logic, PlayerSpawn, Spawner, Item, Water, Mover и материалов. `ModSimpleAnimator` (карусель в Ticket Rush, 2026-10-22) собран, но в редакторе и в игре ещё не проверен.
