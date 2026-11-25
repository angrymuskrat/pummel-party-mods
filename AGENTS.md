# AGENTS.md — Pummel Party mods

Тематические карты (доски) для Pummel Party и под каждую — набор тематических мини-игр. Агент здесь — геймдизайнер, справочник по Mod Editor, генератор ассетов и разборщик логов.

**Проектировать только из того, что есть в редакторе.** Источник правды — `.claude/skills/pummel-party-mod-editor/reference/`. Если вики молчит, так и писать; действия и параметры не выдумывать.

**Моды собираются кодом, а не мышкой.** У каждой мини-игры есть `build_mod.py` рядом с `DESIGN.md`, на базе `tools/pmgen.py`. Mod Editor нужен для плейтеста, скриншотов и публикации.

**Действия вне репозитория — только по запросу пользователя:** публикация в Workshop, запуск игры, установка BepInEx в папку Steam. Код против сборок игры (BepInEx) появляется только по явному решению пользователя.

Этот файл — минимум для работы в репозитории. Состав пака и статусы игр — в вики пака ([`packs/abandoned-park/WIKI.md`](packs/abandoned-park/WIKI.md)), порядок правки готовой игры — в [`packs/abandoned-park/EDITING.md`](packs/abandoned-park/EDITING.md). Какой скилл брать — раздел «Скиллы проекта».

## Что за проект

- Основной путь — официальный Mod Editor (Steam Workshop, с обновления 1.12.1): мини-игры и доски без кода игры. Неофициальный путь — плагины BepInEx + HarmonyX, когда редактор не умеет нужного (предметы, правила доски, боты).
- Генерация модов кодом подтверждена плейтестом 2026-10-21: Ticket Rush Gen собран `build_mod.py`, в игре работают предметы, триггеры, спавнеры, материалы, таймер.
- Сейчас один пак — `packs/abandoned-park/` (Rusted Park): доска Rusted · Midway и мини-игры парка.

## Правила

### Источники правды

- **Редактор** — `reference/` скилла `pummel-party-mod-editor`: `logic-catalog.md` (события, действия, компоненты), `scene-format.md` (формат проекта на диске, PMH, материалы, `ModSettings.json`), `editor-workflow.md` (интерфейс, доски, мини-игры, импорт ассетов). Утверждение о редакторе — со ссылкой на страницу вики из `reference/`.
- **Игровые файлы** — встроенные мини-игры (`PummelParty_Data/StreamingAssets/InbuiltMods/`) и шаблоны редактора (`PummelParty_Data/StreamingAssets/WorkshopTemplates/`) как эталоны.
- **Документация равна коду.** Каждое утверждение о компоненте, действии, формате, пути или команде проверяется по `reference/`, игровым файлам или коду (`file:line`) до того, как текст считается готовым. Число в `DESIGN.md` игру не меняет: меняет сборщик.

### Сборка и ассеты

- `build_mod.py` пишет проект в `WorkshopMods`. Сборка поверх установленного проекта может перезаписать ручные правки из редактора: перед ней сохранить копию проекта или собрать под другим именем (`EDITING.md`).
- Новые компоненты и действия добавлять в `tools/pmgen.py` по `scene-format.md`.
- Ассеты генерируются воспроизводимо: скрипт лежит рядом с результатом в `packs/<theme>/assets/`, каталог — `ASSETS.md`. Изменить ресурс — значит изменить его генератор.
- Скрипты пишутся на стандартной библиотеке Python 3.10: PIL и numpy не используются, PNG пишется через `zlib`.

### Пути и публичность

- Репозиторий публичный. Абсолютные пути с именем пользователя и другие данные машины в отслеживаемые файлы не писать: использовать `%USERPROFILE%`, пути от `WorkshopMods/` или от корня репозитория.
- Конкретные пути машины — в личных файлах агента вне git.

## Игра и окружение

- Steam, бэкенд Mono, Unity 2021.3.45f2 (проверено 2026-10-21). Папка данных — `PummelParty_Data` без пробела.
- Проекты редактора — `%USERPROFILE%\AppData\LocalLow\Rebuilt Games\Pummel Party\WorkshopMods\`. Логи — `Player.log` и `Player-prev.log` в папке выше (`...\Rebuilt Games\Pummel Party\`).

## Скиллы проекта

Лежат в `.claude/skills/<name>/` (в git); Codex видит их копию в `.agents/skills/`. `SKILL.md` — источник правды по своему процессу: прочитать его целиком перед применением.

| Скилл | Когда |
| --- | --- |
| `pummel-party-themed-pack` | Новый пак, доска или мини-игра: тема → доска → спецификации на событиях и действиях редактора → ассеты → чеклист |
| `pummel-party-level-design` | Пространство сцены: масштаб, маршруты, ориентиры, детали, движение, «пусто» и «скучно бегать». После каждой правки расстановки — `scripts/plan_view.py` |
| `pummel-party-mod-editor` | Любая задача про редактор: какие события, действия, компоненты; импорт; Log Window, Mod Validator; публикация |
| `pummel-party-bepinex` | Только когда редактор не умеет нужного и пользователь выбрал код-путь |
| `grilling` | Стресс-тест плана, механики или неясной темы |
| `simplest-fix-first` | Перед любым предложением фикса или дизайна: самая простая цепочка, которая даёт механику |
| `deep-investigation` | Поиск причины: «не работает», «не синхронизируется», логи |
| `feynman` | Объяснение «с нуля», тексты для людей (описание в Workshop) |
| `pre-ship` | Самопроверка своего диффа перед «готово» |

## Перед «готово»

| Что изменено | Чем проверить |
| --- | --- |
| Сборщик мини-игры | Собрать в отдельную папку, затем `python -B tools/pmscene.py roundtrip "<проект>/Data/MainScene.scene"`: `OK` значит, что сцена прочитана и записана в те же байты. Пример команды — `EDITING.md`, шаг 3 |
| Расстановка объектов | `plan_view.py` из `pummel-party-level-design`: план сверху, оба разреза, метрики |
| `tools/pmgen.py`, `tools/pmscene.py` | `python -B -m unittest discover -s tools -p "test_*.py"` плюс сборка затронутых игр |
| `DESIGN.md`, вики, правила | Сверка по «Документация равна коду» |

Mod Validator, игровая и сетевая проверка идут в редакторе и в игре; их порядок — [`packs/abandoned-park/PLAYTEST.md`](packs/abandoned-park/PLAYTEST.md). Без запроса агент игру не запускает, поэтому в отчёте эти пункты значатся непроверенными. В отчёте назвать, что проверено и что нет.

## Структура репозитория

```
AGENTS.md                  # правила проекта; CLAUDE.md импортирует этот файл
.claude/skills/            # проектные скиллы (раздел «Скиллы проекта»)
packs/<theme>/             # PACK.md, WIKI.md, EDITING.md, board/, minigames/<game>/ (DESIGN.md, build_mod.py, plan/), assets/
tools/pmscene.py           # парсер и сериализатор MainScene.scene и .pfab (PMH); команда roundtrip
tools/pmgen.py             # генератор модов: сцена, префабы, ассеты с .pmeta, материалы, ModSettings
tools/test_appearance.py   # регрессия pmgen: сохранение при пересборке, поправка OBJ по X
tools/audit_playtest.py    # структурный аудит установленных проектов Rusted Park, только чтение; отсутствующие в папке — SKIP
wiki/                      # заметки о прототипах вне паков
mods/<name>/               # только для BepInEx-плагинов (пока нет)
```

## Связанные документы

| Документ | Что внутри |
| --- | --- |
| [`README.md`](README.md) | Вход: ссылки на вики и на правку игры |
| [`packs/abandoned-park/WIKI.md`](packs/abandoned-park/WIKI.md) | Все мини-игры и доска пака, статусы, игровые проверки, бэклог, оформление |
| [`packs/abandoned-park/EDITING.md`](packs/abandoned-park/EDITING.md) | Как изменить готовую игру и где искать правку |
| [`packs/abandoned-park/PLAYTEST.md`](packs/abandoned-park/PLAYTEST.md) | Порядок игровых и сетевых проверок |
| [`packs/abandoned-park/ART_DIRECTION.md`](packs/abandoned-park/ART_DIRECTION.md), [`assets/ASSETS.md`](packs/abandoned-park/assets/ASSETS.md) | Художественные профили и каталог ассетов |
| [`packs/abandoned-park/board/BOARD.md`](packs/abandoned-park/board/BOARD.md) | Паспорт доски Rusted · Midway |
| [`wiki/Rusted-Park-V3.md`](wiki/Rusted-Park-V3.md) | Прототипы Barrel Bends V3 и Mascot Carts V3 |
