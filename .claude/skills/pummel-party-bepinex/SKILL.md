---
name: pummel-party-bepinex
description: Use when a Pummel Party mod needs more than the official Mod Editor allows (new items, changed board rules, bot behaviour, global game rules) and the user agrees to the unofficial code path — a BepInEx + HarmonyX plugin against the game's Unity assemblies. Covers backend detection (Mono vs IL2CPP), decompilation, patch points, plugin layout, build, install location and multiplayer testing. Do not use for minigames or boards — those belong to the official editor (pummel-party-mod-editor).
---

# Pummel Party — код-моды на BepInEx + HarmonyX

Официальный Mod Editor покрывает только мини-игры и доски. Всё остальное — новые предметы, правила доски, боты, глобальные правила — делается патчами игрового кода. Это путь первопроходца: готового сообщества BepInEx-модов для Pummel Party не найдено, и каждый патч игры может сломать мод.

## Шаг 0 — подтвердить, что путь нужен

Прежде чем писать плагин, назвать одной фразой, чего именно не умеет редактор (сверить с `pummel-party-mod-editor/reference/logic-catalog.md`). Если задача ложится в мини-игру или доску — остановиться и идти официальным путём.

## Шаг 1 — определить бэкенд

Папка игры: `<Steam>\steamapps\common\Pummel Party\`.

| Есть файл | Бэкенд | Стек |
| --- | --- | --- |
| `Pummel Party_Data\Managed\Assembly-CSharp.dll` | Mono | BepInEx 5.x + HarmonyX, декомпиляция напрямую |
| `GameAssembly.dll` + `Pummel Party_Data\il2cpp_data\` | IL2CPP | BepInEx 6 (Bleeding Edge, IL2CPP build) + Il2CppInterop; метаданные через Il2CppDumper |

Версию Unity взять из `Pummel Party.exe` (свойства файла) или `Pummel Party_Data\globalgamemanagers`; от неё зависит, какой .NET target брать для плагина.

На 2026-10-21 бэкенд не проверен: игра не установлена на рабочем ПК. Первый шаг любой сессии по этому скиллу — проверить таблицу выше и записать результат в этот файл.

## Шаг 2 — декомпилировать и найти точку патча

- Mono: открыть `Assembly-CSharp.dll` в ILSpy или dnSpyEx; искать по строкам UI и именам предметов.
- IL2CPP: Il2CppDumper → `DummyDll`, читать их в ILSpy; логику в IL видно не будет, только сигнатуры — патчи строятся по именам методов и наблюдению в рантайме.
- Для каждой точки патча записать: класс, метод, сигнатура, что он делает, какой prefix/postfix нужен. Без этой записи патч не писать.

## Шаг 3 — структура плагина

```
mods/<mod-name>/
  <ModName>.csproj        # net472 (Mono) или net6.0 (IL2CPP BepInEx 6); ссылки на BepInEx и Assembly-CSharp через HintPath, без копирования DLL игры в репо
  Plugin.cs               # [BepInPlugin(GUID, Name, Version)], один класс-точка входа
  Patches/<Feature>Patches.cs   # по файлу на фичу, [HarmonyPatch] с явным именем метода
  README.md               # что делает, какая версия игры проверена, как ставить
```

- GUID вида `com.<author>.pummelparty.<mod>`; версия SemVer.
- DLL игры не коммитить; `.gitignore` на `bin/`, `obj/`, `*.dll` вне `lib/`.
- Логировать через `Logger.LogInfo` плагина, не `Debug.Log`.

## Шаг 4 — сборка и установка

1. Поставить BepInEx нужной ветки в папку игры (распаковать в корень, запустить игру один раз, чтобы появились `BepInEx/plugins` и `BepInEx/config`).
2. `dotnet build -c Release`; результат копировать в `BepInEx\plugins\<ModName>\`.
3. Проверять `BepInEx\LogOutput.log`: плагин должен загрузиться без исключений Harmony.

## Шаг 5 — мультиплеер

Мод с изменённой логикой должен стоять у всех игроков, иначе рассинхрон. Правила:

- Патчи, меняющие состояние игры, тестировать минимум на двух клиентах (второй ПК или вторая копия через Steam family/offline, если это возможно).
- Чисто клиентские патчи (UI, косметика) помечать в README как «safe without peers».
- Хост-авторитетные правила описать отдельно: какой клиент считает результат и как это реплицируется.

## Что отдаю пользователю

Запуск игры, установка BepInEx в папку Steam и любые действия в Steam Workshop — по запросу пользователя, не автоматически. Я собираю DLL, пишу инструкцию и указываю, куда положить файл.
