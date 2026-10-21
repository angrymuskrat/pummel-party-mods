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

JSON действия: `m_type`, `m_version: 0`, у `TargetAction` — `m_targetFlags` (Source 1 = кто вызвал событие: вошедший в триггер, подобравший предмет; Receiver 2 = объект с компонентом; Advanced 4 = список `m_targets[{"m_assetGUID":{"serializedGuid":…}}]` с GUID компонентов), далее поля класса: `m_operation`/`m_value` (ChangeScore, ChangeHealth), `m_effectType` (SpawnEffect: Wood 0, Blood 1, Explosion 2, Confetti 3, Sparkles 4), `m_messageTarget`/`m_message`/`m_duration` (ShowMessage), `m_seconds` (Wait, ComplexFloat), `m_newState` (SetActive: Enabled 0, Disabled 1, Toggle 2), `m_stunDuration`, `m_value` Vector3 (SetGravity), `m_operation`/`m_space`/`m_localTarget`/`m_velocityDir`/`m_customDir`/`m_speed` (ChangeVelocity: Up 0 … TowardsSource 6, TowardsReceiver 7, Custom 8), `m_clip`/`m_volume` (PlaySound), `m_transformToMatch`/`m_transformValuesToMatch` (MatchTransform, флаги PosX 1 … RotZ 32).

### Схема ключевых компонентов (имя свойства: тип)

- `ModTransform`: position, rotation (Euler), scale: Vector3.
- `ModProp`: prop: ref, tintColor: Color, collisionType: enum (None 0, Box 1, Sphere 2, Mesh 3), shadowCastingMode: enum, customMaterials: ref[].
- `ModTrigger`: TriggerShape (Custom 0, Box 1, Sphere 2, Capsule 3), Size, Center: Vector3, Radius, Height: float, TriggerOnHit/OnEnter/OnExit/OnStay: bool, OnHitActions/OnEnterActions/OnExitActions/OnStayActions: ModLogicTrigger, StayTriggerInterval: float, DisableAfterTriggered, OneUsePerPlayer: bool.
- `ModLogic`: Triggers: ModLogicTrigger[].
- `ModPlayerSpawn`: SharedSpawn: bool, SpawnUsageType: flags (Initial 1, Respawn 2), AllowedPlayers: flags 8 бит, SpawnShape (Point 0, Line 1, Circle 2), PlayerCountMask: flags 8 бит, SpawnDistribution (Step 0, Random 1), LineLength, Radius: float, Advanced: bool.
- `ModSpawner`: Prefabs: ref[], PrefabGUIDs: string[], Interval1, Delay: ComplexFloat (JSON), Type (AlwaysSpawn 0, SpawnOnDestruction 1), LocationType: flags (OnSpawner 1, OnTargets 2), SpawnPoints: ref[] (GUID `ModTransform`), SpawnCount: int.
- `ModMover`: DirectionType (Up 0, Down 1, Left 2, Right 3, Forward 4, Back 5, Custom 6 — локальные оси объекта, Custom = вектор Direction), Direction, Speed (ед/с), RotationAxisType (X 0, Y 1, Z 2, Custom 3 — мировые оси, `Rotate(axis, speed·dt, Space.World)`), RotationAxis (только при Custom), RotationSpeed (град/с).
- `ModWater`: Width, Height: int, CellSize: float, DeepColor, ShallowColor, FrothColor: Color, WaveHeight, WaveSpeed: float.
- `ModItem`: ItemType (Carried 0, Weapon 1, Worn 2, Pickup 3), WeaponInfo: JSON ModWeaponInfo, ItemPrefab: ref + ItemPrefabGUID: string (визуальный префаб), … , OnPickupTrigger/OnDropTrigger/OnUseTrigger/OnWhileHeldTrigger: ModLogicTrigger, ItemSlot: enum. Пример из игры (HealthKit): Pickup, CanBeDropped false, DisappearWhenDropped true, AutoDropAfterTime true, OnPickup → ChangeHealth Source Add 40.
- `ModBoxCollider`: center, size. `ModNote`: Text. `ModPrefabInstance`: PrefabReference: ref, PrefabGUID: string.

Полная схема по всем компонентам (включая ModParticleSystem, ModText, ModBoardSpace) печатается командой `python tools/pmscene.py schema <сцены…>`.

## GUID встроенных props (сняты со сцен)

LowPolyCube `cfc9faf9-3852-4dbe-803b-32cec4c94139`, LowPolyPlane `e314a70b-98f2-4459-9214-ef4da97b4e6d` (есть и второй plane `331019a7-e85f-47d4-a19d-703dc99a3fab`), LowPolySphere `c7d7ef4d-4e66-4b08-b91a-d5b0190b74ee`. Остальные встроенные props по имени не найти (каталог Addressables бинарный); брать GUID из сцены, где такой prop расставлен.

## Материалы (PummelMaterial)

`.pmat` на диске — 5 байт (`\x04PMAT`), содержимое в `pmeta.m_shaderData` (массив байт JSON): `"PMAT"`, u8 0, u8 2, i32 n свойств шейдера, n × (string имя, u8 тип: Color 0 / Vector 1 → 4×f32, Float 2 / Range 3 → f32, Texture 4 → ref), i32 число keywords + строки, Vector2 mainTextureScale, Vector2 mainTextureOffset. Список свойств `Standard Decal Receiver` зашит в `pmgen.material_shader_data`.

## ModSettings.json

`EndConditions` — флаги SimpleMinigameEndCondition (Timer 1, ObtainPoints 2, RemainingPlayersAlive 4, FinishMinigame 8); `PlacementCondition` (MostPoints 0, LeastPoints 1, FinishOrder 2, LastManStanding 3); `ChosenPlayerType` (ThirdPerson 0, TopDown 1, TwinStick 2); `SpawnType` PlayerSpawnType (PortalAbove 0, None 1, PortalAboveNoAnimation 2). Остальные поля — см. файл шаблона.

## Статус проверки в редакторе

2026-10-21: сгенерированный `Ticket Rush Gen` открылся в Mod Editor, Hierarchy показывает все объекты (World, Ticket Spawners, Director), Player.log без ошибок. Значит наши `.pmeta`, префабы `.pfab`, JSON триггеров с пустым `references` и ModSettings редактор принимает. По скриншоту редактора: Log 0 warnings / 0 errors, материалы из `m_shaderData` работают (текстуры на киосках и полу видны), триггеры и спавнеры отображаются гизмо. Плейтест 2026-10-21 (1 игрок + 3 бота, полный раунд до экрана результатов): в Player.log ни исключений, ни ошибок загрузки; `Running Round Start Logic Trigger` — триггер ModLogic выполнился; звук подбора проигрывался. По словам пользователя в игре работало всё из чеклиста: подбор билетов с очками, респаун билетов спавнером, kill-зона пруда с респауном, jump pad (`ChangeVelocity` Up/Set), таймер и места по очкам. Генератор можно считать рабочим для компонентов Prop, Trigger, Logic, PlayerSpawn, Spawner, Item, Water, Mover и материалов.
