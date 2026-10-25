"""Генератор модов Pummel Party Mod Editor: сцена (PMH), префабы (.pfab), ассеты с .pmeta и JSON настроек.

Строится поверх pmscene.py. Все числа и форматы взяты из декомпилированного Assembly-CSharp
(ModReflectionTypes, ModHierarchySerializer, ModSystem.Logic.*, PummelMaterial) и сверены
с файлами встроенных модов. Что ещё не проверено в редакторе — помечено «не проверено».

Минимальный пример:

    mod = Mod("My Minigame")
    ground = mod.add(obj("Ground", pos=(0, 0, 0), layer=LAYER_WORLD_GROUND)
                     .prop(PROP_PLANE, scale=(4, 1, 4)))
    mod.add(obj("Spawn").player_spawn(shape=SpawnShape.CIRCLE, radius=10))
    mod.write(r"%USERPROFILE%\\AppData\\LocalLow\\Rebuilt Games\\Pummel Party\\WorkshopMods")
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import struct
import uuid
from dataclasses import dataclass, field

import pmscene as P

# ---------------------------------------------------------------- константы из игры

GAME_TEMPLATES = (r"C:\Program Files (x86)\Steam\steamapps\common\Pummel Party"
                  r"\PummelParty_Data\StreamingAssets\WorkshopTemplates\Minigames")
ASSET_LOCATION_EXTERNAL = "757b15db-4305-4406-b767-1ec002daa769"  # AssetLocationGuid.External
GUID_EMPTY = "00000000-0000-0000-0000-000000000000"
PNG_SIGNATURE = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])

LAYER_DEFAULT = 0
LAYER_WORLD_GROUND = 10   # GameManager.WorldGroundLayer
LAYER_WORLD_WALL = 11     # так помечены LowPolyCube в шаблоне Minimal Third Person

# GUID встроенных props, снятые со сцен шаблонов (имя объекта → prop)
PROP_CUBE = "cfc9faf9-3852-4dbe-803b-32cec4c94139"     # LowPolyCube
PROP_PLANE = "e314a70b-98f2-4459-9214-ef4da97b4e6d"    # LowPolyPlane (шаблон Minimal Third Person)
PROP_SPHERE = "c7d7ef4d-4e66-4b08-b91a-d5b0190b74ee"   # LowPolySphere


class Collision:      # PropCollisionType
    NONE, BOX, SPHERE, MESH = 0, 1, 2, 3


class Shadow:         # UnityEngine.Rendering.ShadowCastingMode
    OFF, ON, TWO_SIDED, SHADOWS_ONLY = 0, 1, 2, 3


class TriggerShape:   # ModTriggerShape
    CUSTOM, BOX, SPHERE, CAPSULE = 0, 1, 2, 3


class SpawnShape:     # ModPlayerSpawnShape
    POINT, LINE, CIRCLE = 0, 1, 2


class SpawnUsage:     # ModSpawnUsageType (flags)
    INITIAL, RESPAWN, BOTH = 1, 2, 3


class SpawnerType:    # ModSpawnerType
    ALWAYS, ON_DESTRUCTION = 0, 1


class SpawnerLocation:  # ModSpawnerLocationType (flags)
    ON_SPAWNER, ON_TARGETS = 1, 2


class ItemType:       # ModItemType
    CARRIED, WEAPON, WORN, PICKUP = 0, 1, 2, 3


class Targets:        # ModActionTargets (flags)
    SOURCE = 1    # кто вызвал событие (вошедший в триггер, подобравший предмет)
    RECEIVER = 2  # объект, на котором стоит компонент
    ADVANCED = 4  # явный список компонентов по GUID


class Op:             # ModActionOperation
    SET, ADD, SUB, MUL, DIV = 0, 1, 2, 3, 4


class Effect:         # SpawnEffectType
    WOOD, BLOOD, EXPLOSION, CONFETTI, SPARKLES = 0, 1, 2, 3, 4


class MsgTarget:      # ShowMessageTarget
    EVERYONE, TARGET = 1, 2


class ActiveState:    # SetActiveType
    ENABLED, DISABLED, TOGGLE = 0, 1, 2


class VelocityDir:    # ChangeVelocityAction.VelocityDirection
    UP, DOWN, LEFT, RIGHT, FORWARD, BACKWARD, TOWARDS_SOURCE, TOWARDS_RECEIVER, CUSTOM = range(9)


class MoverDir:       # ModMover.ModMoverDirection (движение по локальной оси объекта; Custom — вектор m_direction)
    UP, DOWN, LEFT, RIGHT, FORWARD, BACK, CUSTOM = range(7)


class MoverAxis:      # ModMover.ModMoverRotationAxis (ось в мировых координатах, Space.World)
    X, Y, Z, CUSTOM = range(4)


class Tween:          # ModTweenType (PlayTweenAnimationAction)
    WORLD_POSITION, LOCAL_ROTATION, LOCAL_SCALE, LOCAL_POSITION, ROTATE_LOCAL_AXIS, ROTATE_WORLD_AXIS, WORLD_ROTATION = range(7)


class TweenValue:     # ModTweenValue: Offset — прибавка к текущему значению
    CURRENT, SPECIFIC, OFFSET = range(3)


class Ease:           # LeanTweenType (начало списка; 0 — notUsed)
    LINEAR, EASE_OUT_QUAD, EASE_IN_QUAD, EASE_IN_OUT_QUAD, EASE_IN_CUBIC, EASE_OUT_CUBIC = range(1, 7)


class Trigger:        # ModTriggerType
    NONE, START, ENABLE, UPDATE, HIT, WEAPON_HIT, TIMER, BOARD_SPACE, ROUND_START, ROUND_END = (
        0, 32, 40, 48, 64, 80, 96, 112, 128, 144)


class Action:         # ModActionType
    WAIT, KILL, CHANGE_HEALTH, CHANGE_SCORE, SPAWN_EFFECT = 32, 64, 96, 128, 160
    SCALE, SET_COLOR, SET_ACTIVE, PLAY_TWEEN, POSITION, ROTATION = 256, 288, 320, 352, 384, 416
    SET_GRAVITY, SET_PLACEMENT, MODIFY_PLAYER, PLAY_SOUND, SPAWN_PREFAB = 448, 480, 512, 544, 576
    CHANGE_VELOCITY, SHOW_MESSAGE, GIVE_MINIGAME_ITEM, STUN_PLAYER = 832, 1024, 1056, 1088
    DROP_MINIGAME_ITEM, MATCH_TRANSFORM, SET_PLAYER_VISUAL = 1120, 1184, 1248


class EndCondition:   # SimpleMinigameEndCondition (flags)
    TIMER, OBTAIN_POINTS, REMAINING_ALIVE, FINISH = 1, 2, 4, 8


class Placement:      # SimpleMinigamePlacementCondition
    MOST_POINTS, LEAST_POINTS, FINISH_ORDER, LAST_MAN_STANDING = 0, 1, 2, 3


class PlayerType:     # SimpleModPlayerType
    THIRD_PERSON, TOP_DOWN, TWIN_STICK = 0, 1, 2


def new_guid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------- кодировщики значений свойств

def _w() -> P.Writer:
    return P.Writer()


def enc_bool(v: bool) -> bytes: return b"\x01" if v else b"\x00"
def enc_i32(v: int) -> bytes: return struct.pack("<i", int(v))
def enc_f32(v: float) -> bytes: return struct.pack("<f", float(v))
def enc_vec3(v) -> bytes: return struct.pack("<fff", *[float(x) for x in v])
def enc_color(c) -> bytes: return struct.pack("<ffff", *[float(x) for x in c])


def enc_string(s: str) -> bytes:
    w = _w(); w.string(s); return w.bytes()


def enc_guid(g: str) -> bytes:
    return enc_string(g)


def enc_ref(guid: str | None) -> bytes:
    """Ссылка на ассет/компонент: bool «есть» + строка GUID (Extensions.WriteObject)."""
    if not guid:
        return b"\x00"
    w = _w(); w.bool(True); w.string(guid); return w.bytes()


def enc_ref_array(guids: list[str]) -> bytes:
    w = _w(); w.i32(len(guids))
    for g in guids:
        w.raw(enc_ref(g))
    return w.bytes()


def enc_guid_array(guids: list[str]) -> bytes:
    w = _w(); w.i32(len(guids))
    for g in guids:
        w.string(g)
    return w.bytes()


def _json(obj) -> str:
    return json.dumps(obj, indent=4, ensure_ascii=False)


def enc_json(obj) -> bytes:
    return enc_string(_json(obj))


def complex_float(value: float, max_value: float | None = None) -> dict:
    """ModComplexFloat: константа или случайное между двумя значениями."""
    if max_value is None:
        return {"valueType": 0, "min": float(value), "max": float(value)}
    return {"valueType": 1, "min": float(value), "max": float(max_value)}


# ---------------------------------------------------------------- действия (JSON по классам ModSystem.Logic)

def _targets(flags: int, guids: list[str] | None):
    return {"m_targetFlags": flags,
            "m_targets": [{"m_assetGUID": {"serializedGuid": g}} for g in (guids or [])]}


# классы действий для SerializeReference в ModSettings.json (ModSystem.Logic.*Action)
ACTION_CLASS = {Action.KILL: "KillAction", Action.CHANGE_HEALTH: "ChangeHealthAction", Action.CHANGE_SCORE: "ChangeScoreAction",
                Action.SPAWN_EFFECT: "SpawnEffectAction", Action.PLAY_SOUND: "PlaySoundAction", Action.SHOW_MESSAGE: "ShowMessageAction",
                Action.CHANGE_VELOCITY: "ChangeVelocityAction", Action.MODIFY_PLAYER: "ModifyPlayerAction",
                Action.WAIT: "WaitAction"}


def _action(type_id: int, flags: int = Targets.SOURCE, targets: list[str] | None = None, **fields) -> tuple[int, dict]:
    d = {"m_type": type_id, "m_version": 0}
    if flags is not None:
        d.update(_targets(flags, targets))
    d.update(fields)
    return type_id, d


def act_kill(flags=Targets.SOURCE, targets=None):
    return _action(Action.KILL, flags, targets)


def act_change_score(value: int, op=Op.ADD, flags=Targets.SOURCE, targets=None):
    return _action(Action.CHANGE_SCORE, flags, targets, m_operation=op, m_value=int(value))


def act_change_health(value: int, op=Op.ADD, flags=Targets.SOURCE, targets=None):
    return _action(Action.CHANGE_HEALTH, flags, targets, m_operation=op, m_value=int(value))


def act_spawn_effect(effect=Effect.EXPLOSION, flags=Targets.SOURCE, targets=None):
    return _action(Action.SPAWN_EFFECT, flags, targets, m_effectType=effect)


def act_show_message(message: str, duration=2.0, to=MsgTarget.EVERYONE, flags=Targets.SOURCE, targets=None):
    return _action(Action.SHOW_MESSAGE, flags, targets, m_messageTarget=to, m_message=message, m_duration=float(duration))


def act_wait(seconds: float, max_seconds: float | None = None):
    return _action(Action.WAIT, None, None, m_seconds=complex_float(seconds, max_seconds))


def act_set_active(state=ActiveState.ENABLED, targets: list[str] | None = None, flags=Targets.ADVANCED):
    return _action(Action.SET_ACTIVE, flags, targets, m_newState=state)


def act_stun(duration=1.0, flags=Targets.SOURCE, targets=None):
    return _action(Action.STUN_PLAYER, flags, targets, m_stunDuration=float(duration))


def act_set_gravity(vec=(0, -9.81, 0)):
    return _action(Action.SET_GRAVITY, None, None, m_value={"x": vec[0], "y": vec[1], "z": vec[2]})


def act_modify_player_speed(multiplier: float, flags=Targets.SOURCE, targets=None):
    """Modify Player Action, режим MovementSpeedMultiplier (0…100): maxSpeed, разгон и торможение игрока × multiplier
    (SimpleModPlayer.SetMovementSpeedMultiplier); при респауне игра сама возвращает 1. Не проверено."""
    return _action(Action.MODIFY_PLAYER, flags, targets, m_playerActionType=0, m_movementSpeed=float(multiplier),
                   m_gravity={"x": 0.0, "y": -9.81, "z": 0.0})


def act_set_placement(flags=Targets.SOURCE, targets=None):
    return _action(Action.SET_PLACEMENT, flags, targets)


def act_change_velocity(speed: float, direction=VelocityDir.TOWARDS_RECEIVER, op=Op.SET, space=0,
                        custom=(0, 0, 0), flags=Targets.SOURCE, targets=None):
    return _action(Action.CHANGE_VELOCITY, flags, targets, m_operation=op, m_space=space, m_localTarget=1,
                   m_velocityDir=direction, m_customDir={"x": custom[0], "y": custom[1], "z": custom[2]},
                   m_speed=float(speed))


def act_play_sound(clip_guid: str | None, volume=1.0, flags=Targets.RECEIVER, targets=None):
    return _action(Action.PLAY_SOUND, flags, targets,
                   m_clip={"m_assetGUID": {"serializedGuid": clip_guid or GUID_EMPTY}}, m_volume=float(volume))


def act_set_color(color, flags=Targets.ADVANCED, targets: list[str] | None = None):
    """Цель — трансформ или Prop: меняет tint у Prop на объекте; Logic — у всех дочерних props (SetColorAction). Не проверено."""
    return _action(Action.SET_COLOR, flags, targets, m_color={"r": color[0], "g": color[1], "b": color[2], "a": color[3]})


def act_play_tween(targets: list[str], kind=Tween.LOCAL_POSITION, end=(0, 0, 0), end_type=TweenValue.OFFSET, seconds=1.0,
                   ease=Ease.LINEAR, start=(0, 0, 0), start_type=TweenValue.CURRENT, axis=(0, 1, 0), degrees=0.0,
                   flags=Targets.ADVANCED):
    """Одноразовый твин (LeanTween). axis/degrees — только для ROTATE_*_AXIS. Не проверено."""
    def v(p): return {"x": p[0], "y": p[1], "z": p[2]}
    return _action(Action.PLAY_TWEEN, flags, targets, m_tweenType=kind, m_easeType=ease, m_time=float(seconds),
                   m_startValueType=start_type, m_startValue=v(start), m_endValueType=end_type, m_endValue=v(end),
                   m_rotationAxis=v(axis), m_rotationDegrees=float(degrees))


def act_match_transform(transform_guid: str, targets: list[str] | None = None, values=63, flags=Targets.ADVANCED):
    """values — флаги TransformValues: PositionX=1,Y=2,Z=4, RotationX=8,Y=16,Z=32 (63 = всё).
    Цель-игрок (flags=Targets.SOURCE) переносится через SimpleModPlayer.TeleportPlayer с поворотом камеры по Y."""
    return _action(Action.MATCH_TRANSFORM, flags, targets,
                   m_transformToMatch={"m_assetGUID": {"serializedGuid": transform_guid}},
                   m_transformValuesToMatch=values)


# ---------------------------------------------------------------- триггеры (ModLogicTrigger)

def enc_trigger(trigger_type: int, actions: list[tuple[int, dict]], **extra) -> bytes:
    """u16 тип + JSON триггера (без действий внутри) + u16 n + n × (u16 тип + JSON действия).
    Игра при чтении заменяет Actions тем, что прочитала из явного списка (ModReflectionTypes.ReadType)."""
    w = _w()
    w.u16(trigger_type)
    body = {"m_type": trigger_type, "m_actions": []}
    body.update(extra)
    body["references"] = {"version": 2, "RefIds": []}
    w.string(_json(body))
    w.u16(len(actions))
    for type_id, data in actions:
        w.u16(type_id)
        w.string(_json(data))
    return w.bytes()


def trig_start(*actions): return enc_trigger(Trigger.START, list(actions))
def trig_enable(*actions): return enc_trigger(Trigger.ENABLE, list(actions))
def trig_round_start(*actions): return enc_trigger(Trigger.ROUND_START, list(actions))
def trig_round_end(*actions): return enc_trigger(Trigger.ROUND_END, list(actions))


def trig_timer(interval: float, *actions, max_interval: float | None = None):
    return enc_trigger(Trigger.TIMER, list(actions), m_interval=complex_float(interval, max_interval))


def enc_trigger_array(triggers: list[bytes]) -> bytes:
    w = _w(); w.i32(len(triggers))
    for t in triggers:
        w.raw(t)
    return w.bytes()


EMPTY_TRIGGER = enc_trigger(Trigger.NONE, [])


# ---------------------------------------------------------------- Simple Animator (анимации по образцу InbuiltMods)

def _curve_key(time: float, value: float, in_slope: float, out_slope: float) -> dict:
    return {"serializedVersion": "3", "time": time, "value": value, "inSlope": in_slope, "outSlope": out_slope,
            "tangentMode": 0, "weightedMode": 0, "inWeight": 0.0, "outWeight": 0.0}


def _anim_layer(speed: float, anim_type: int, axis, keys: list[dict], offset=0.0) -> dict:
    """SimpleAnimationLayer: AnimationType 0 — позиция, 1 — поворот; m_PreInfinity/m_PostInfinity 2 = зацикливание."""
    return {"AnimationSpeed": float(speed), "AnimationOffset": float(offset), "UseRandomAnimationOffset": False,
            "AnimationType": anim_type, "AnimationAxis": {"x": float(axis[0]), "y": float(axis[1]), "z": float(axis[2])},
            "AnimationCurve": {"serializedVersion": "2", "m_Curve": keys, "m_PreInfinity": 2, "m_PostInfinity": 2,
                               "m_RotationOrder": 4}}


def _animation(preset: int, name: str, help_text: str, layers: list[dict], **extra) -> dict:
    d = {"AnimationPreset": preset, "AnimationLayers": [{"rid": 1000 + i} for i in range(len(layers))],
         "m_animationName": name, "m_helpText": help_text}
    d.update(extra)
    d["references"] = {"version": 2, "RefIds": [
        {"rid": 1000 + i, "type": {"class": "SimpleAnimationLayer", "ns": "", "asm": "Assembly-CSharp"}, "data": layer}
        for i, layer in enumerate(layers)]}
    return d


def anim_move_along_line(frequency: float, offset=(0, 1, 0)) -> dict:
    """Пресет 1: туда-обратно по отрезку от стартовой точки до start + offset; frequency — циклов в секунду
    (кривая 0→1→0 с плоскими касательными, как у блоков Foggy Fall)."""
    return _animation(1, "Move Along Line",
                      "Moves an object back and forth smoothly along a line. \nThe line is defined by a direction vector from "
                      "the object's starting point. \nThe distance describes how far the object moves along the line before returning.",
                      [_anim_layer(frequency, 0, offset, [_curve_key(0.0, 0.0, 0.0, 0.0), _curve_key(0.5, 1.0, 0.0, 0.0),
                                                          _curve_key(1.0, 0.0, 0.0, 0.0)])])


def anim_rotate_around_axis(frequency: float, axis=(0, 1, 0)) -> dict:
    """Пресет 3: непрерывное вращение; frequency — оборотов в секунду (линейная кривая 0→1, как в Foggy Fall)."""
    return _animation(3, "Rotate Around Axis",
                      "Continuously rotates an object around a given axis. \nFrequency is in number rotations around the axis per second.",
                      [_anim_layer(frequency, 1, axis, [_curve_key(0.0, 0.0, 0.0, 1.0), _curve_key(1.0, 1.0, 1.0, 0.0)])])


# ---------------------------------------------------------------- объекты и компоненты

@dataclass
class Obj:
    """Строитель одного gameobject. Методы-компоненты возвращают self для цепочек."""
    name: str
    pos: tuple = (0.0, 0.0, 0.0)
    rot: tuple = (0.0, 0.0, 0.0)
    scale: tuple = (1.0, 1.0, 1.0)
    layer: int = LAYER_DEFAULT
    active: bool = True
    tag: str = "Untagged"
    children: list[Obj] = field(default_factory=list)
    components: list[P.Component] = field(default_factory=list)
    transform_guid: str = field(default_factory=new_guid)

    # --- GUID-ы для ссылок из действий (Advanced targets, SpawnPoints и т.п.)
    def guid_of(self, type_name: str) -> str:
        if type_name == "ModTransform":
            return self.transform_guid
        for c in self.components:
            if c.type_name == type_name:
                return c.guid
        raise KeyError(f"{self.name}: нет компонента {type_name}")

    def _comp(self, type_name: str, props: list[tuple[str, bytes]], enabled=True) -> P.Component:
        c = P.Component(type_name=type_name, guid=new_guid(), enabled=enabled)
        c.props = [P.Property(n, raw) for n, raw in props]
        c.props.append(P.Property("guid", enc_guid(c.guid)))
        self.components.append(c)
        return c

    def add(self, child: Obj) -> Obj:
        self.children.append(child)
        return child

    def prop(self, prop_guid: str, tint=(1, 1, 1, 1), collision=Collision.MESH, shadow=Shadow.ON,
             materials: list[str] | None = None, enabled=True) -> Obj:
        self._comp("ModProp", [
            ("prop", enc_ref(prop_guid)),
            ("tintColor", enc_color(tint)),
            ("collisionType", enc_i32(collision)),
            ("shadowCastingMode", enc_i32(shadow)),
            ("customMaterials", enc_ref_array(materials or [])),
        ], enabled)
        return self

    def trigger(self, shape=TriggerShape.BOX, size=(1, 1, 1), center=(0, 0, 0), radius=0.5, height=2.0,
                on_enter: list | None = None, on_exit: list | None = None, on_stay: list | None = None,
                on_hit: list | None = None, stay_interval=0.5, disable_after=False, one_use_per_player=False) -> Obj:
        self._comp("ModTrigger", [
            ("TriggerShape", enc_i32(shape)),
            ("Size", enc_vec3(size)),
            ("Center", enc_vec3(center)),
            ("Radius", enc_f32(radius)),
            ("Height", enc_f32(height)),
            ("TriggerOnHit", enc_bool(on_hit is not None)),
            ("TriggerOnEnter", enc_bool(on_enter is not None)),
            ("TriggerOnExit", enc_bool(on_exit is not None)),
            ("TriggerOnStay", enc_bool(on_stay is not None)),
            ("OnHitActions", enc_trigger(Trigger.NONE, on_hit or [])),
            ("OnEnterActions", enc_trigger(Trigger.NONE, on_enter or [])),
            ("OnExitActions", enc_trigger(Trigger.NONE, on_exit or [])),
            ("OnStayActions", enc_trigger(Trigger.NONE, on_stay or [])),
            ("StayTriggerInterval", enc_f32(stay_interval)),
            ("DisableAfterTriggered", enc_bool(disable_after)),
            ("OneUsePerPlayer", enc_bool(one_use_per_player)),
        ])
        return self

    def logic(self, *triggers: bytes) -> Obj:
        self._comp("ModLogic", [("Triggers", enc_trigger_array(list(triggers)))])
        return self

    def player_spawn(self, shape=SpawnShape.POINT, usage=SpawnUsage.BOTH, shared=True, line_length=5.0,
                     radius=5.0, distribution=0, allowed_players=0xFF, count_mask=0xFF, advanced=False) -> Obj:
        self._comp("ModPlayerSpawn", [
            ("SharedSpawn", enc_bool(shared)),
            ("SpawnUsageType", enc_i32(usage)),
            ("AllowedPlayers", enc_i32(allowed_players)),
            ("SpawnShape", enc_i32(shape)),
            ("PlayerCountMask", enc_i32(count_mask)),
            ("SpawnDistribution", enc_i32(distribution)),
            ("LineLength", enc_f32(line_length)),
            ("Radius", enc_f32(radius)),
            ("Advanced", enc_bool(advanced)),
        ])
        return self

    def spawner(self, prefab_guids: list[str], interval=(5.0, None), delay=(0.0, None), kind=SpawnerType.ALWAYS,
                location=SpawnerLocation.ON_SPAWNER, spawn_points: list[str] | None = None, count=1) -> Obj:
        self._comp("ModSpawner", [
            ("Prefabs", enc_ref_array(prefab_guids)),
            ("PrefabGUIDs", enc_guid_array(prefab_guids)),
            ("Interval1", enc_json(complex_float(*interval))),
            ("Delay", enc_json(complex_float(*delay))),
            ("Type", enc_i32(kind)),
            ("LocationType", enc_i32(location)),
            ("SpawnPoints", enc_ref_array(spawn_points or [])),
            ("SpawnCount", enc_i32(count)),
        ])
        return self

    def mover(self, direction_type=MoverDir.CUSTOM, direction=(0, 0, 0), speed=0.0, rotation_axis_type=MoverAxis.Y,
              rotation_axis=(0, 1, 0), rotation_speed=0.0) -> Obj:
        """Update: position += speed * dir (dir по MoverDir, локальные оси объекта); Rotate(axis, rotation_speed, Space.World).
        rotation_axis используется только при MoverAxis.CUSTOM."""
        self._comp("ModMover", [
            ("DirectionType", enc_i32(direction_type)),
            ("Direction", enc_vec3(direction)),
            ("Speed", enc_f32(speed)),
            ("RotationAxisType", enc_i32(rotation_axis_type)),
            ("RotationAxis", enc_vec3(rotation_axis)),
            ("RotationSpeed", enc_f32(rotation_speed)),
        ])
        return self

    def simple_animator(self, *animations: dict, local_position=True, local_rotation=True, time_offset=0.0) -> Obj:
        """ModSimpleAnimator: Animations = i32 n + n × JSON анимации (пресет + слои SimpleAnimationLayer
        через SerializeReference, формат RefIds version 2 — как в InbuiltMods/Foggy Fall). Анимации — anim_*()."""
        w = _w(); w.i32(len(animations))
        for a in animations:
            w.string(_json(a))
        self._comp("ModSimpleAnimator", [
            ("UseLocalPosition", enc_bool(local_position)),
            ("UseLocalRotation", enc_bool(local_rotation)),
            ("UseLateUpdate", enc_bool(False)),
            ("TimeOffset", enc_f32(time_offset)),
            ("Animations", w.bytes()),
        ])
        return self

    def water(self, width=20, height=20, cell=1.0, deep=(0.0, 0.38, 0.78, 0.69), shallow=(0.11, 0.73, 0.5, 0.69),
              froth=(1, 1, 1, 1), wave_height=0.1, wave_speed=1.75) -> Obj:
        self._comp("ModWater", [
            ("Width", enc_i32(width)),
            ("Height", enc_i32(height)),
            ("CellSize", enc_f32(cell)),
            ("DeepColor", enc_color(deep)),
            ("ShallowColor", enc_color(shallow)),
            ("FrothColor", enc_color(froth)),
            ("WaveHeight", enc_f32(wave_height)),
            ("WaveSpeed", enc_f32(wave_speed)),
        ])
        return self

    def ai_node(self, is_goal=False) -> Obj:
        """ModAINavigation: узел графа ботов. Связи ставит link_ai_nodes (ссылки на GUID компонента, как в InbuiltMods)."""
        self._comp("ModAINavigation", [("ConnectedNodes", enc_ref_array([])), ("IsAIGoal", enc_bool(is_goal))])
        return self

    def box_collider(self, center=(0, 0, 0), size=(1, 1, 1)) -> Obj:
        self._comp("ModBoxCollider", [("center", enc_vec3(center)), ("size", enc_vec3(size))])
        return self

    def note(self, text: str) -> Obj:
        self._comp("ModNote", [("Text", enc_string(text))])
        return self

    def prefab_instance(self, prefab_guid: str) -> Obj:
        self._comp("ModPrefabInstance", [("PrefabReference", enc_ref(prefab_guid)), ("PrefabGUID", enc_guid(prefab_guid))])
        return self

    def item(self, item_type=ItemType.PICKUP, visual_prefab_guid: str | None = None, on_pickup: list | None = None,
             on_drop=None, on_use=None, while_held=None, unique_pickup=False, priority=0, can_drop=True,
             disappear_when_dropped=False, auto_drop=False, drop_after=10.0, drop_on_death=True,
             slot=0, hold_anim=0, cooldown=1.0, weapon_info: dict | None = None) -> Obj:
        """weapon_info — полный JSON ModWeaponInfo (копия DEFAULT_WEAPON_INFO с правками); WeaponType 0 = Melee."""
        self._comp("ModItem", [
            ("ItemType", enc_i32(item_type)),
            ("WeaponInfo", enc_json(weapon_info or DEFAULT_WEAPON_INFO)),
            ("ItemPrefab", enc_ref(visual_prefab_guid)),
            ("ItemPrefabGUID", enc_guid(visual_prefab_guid or GUID_EMPTY)),
            ("ItemHoldAnimation", enc_i32(hold_anim)),
            ("ItemBeaconColor", enc_i32(0)),
            ("CustomItemBeaconColor", enc_color((1, 1, 1, 1))),
            ("CanBeDropped", enc_bool(can_drop)),
            ("DisappearWhenDropped", enc_bool(disappear_when_dropped)),
            ("AutoDropAfterTime", enc_bool(auto_drop)),
            ("DropAfterTime", enc_f32(drop_after)),
            ("UniqueDropPrefab", enc_bool(False)),
            ("DropOnDeath", enc_bool(drop_on_death)),
            ("DroppedItemPrefab", enc_ref(None)),
            ("DroppedItemPrefabGUID", enc_guid(GUID_EMPTY)),
            ("PickupSoundType", enc_i32(0)),
            ("UniquePickup", enc_bool(unique_pickup)),
            ("ItemPickupPriority", enc_i32(priority)),
            ("WeaponType", enc_i32(0)),
            ("Cooldown", enc_f32(cooldown)),
            ("HasLimitedUses", enc_bool(False)),
            ("DropAfterUses", enc_i32(3)),
            ("OnPickupTrigger", enc_trigger(Trigger.NONE, on_pickup or [])),
            ("OnDropTrigger", enc_trigger(Trigger.NONE, on_drop or [])),
            ("OnUseTrigger", enc_trigger(Trigger.NONE, on_use or [])),
            ("OnWhileHeldTrigger", enc_trigger(Trigger.NONE, while_held or [])),
            ("SecondsBetweenHeldAction", enc_f32(1.0)),
            ("HeldPositionOffset", enc_vec3((0, 0, 0))),
            ("HeldRotationOffset", enc_vec3((0, 0, 0))),
            ("ItemSlot", enc_i32(slot)),
        ])
        return self

    # --- в модель pmscene
    def to_gameobject(self) -> P.GameObject:
        go = P.GameObject(name=self.name, active=self.active, layer=self.layer, tag=self.tag,
                          transform_guid=self.transform_guid)
        t = P.Component(type_name="ModTransform", guid=self.transform_guid, enabled=True)
        t.props = [P.Property("position", enc_vec3(self.pos)), P.Property("rotation", enc_vec3(self.rot)),
                   P.Property("scale", enc_vec3(self.scale)), P.Property("guid", enc_guid(self.transform_guid))]
        go.components = [t] + list(self.components)
        go.children = [c.to_gameobject() for c in self.children]
        return go


def link_ai_nodes(nodes: list[Obj], edges) -> None:
    """Записывает ConnectedNodes. edges — пары (i, j) индексов в nodes; связь направленная: бот идёт из i в j
    (ModAINavigation.GetPath обходит ConnectedNodes узла). Для двусторонней связи передать обе пары."""
    out: dict[int, list[str]] = {i: [] for i in range(len(nodes))}
    for i, j in edges:
        g = nodes[j].guid_of("ModAINavigation")
        if g not in out[i]:
            out[i].append(g)
    for i, n in enumerate(nodes):
        c = next(c for c in n.components if c.type_name == "ModAINavigation")
        c.set("ConnectedNodes", enc_ref_array(out[i]))


def obj(name: str, pos=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), layer=LAYER_DEFAULT, active=True) -> Obj:
    return Obj(name, tuple(pos), tuple(rot), tuple(scale), layer, active)


# ---------------------------------------------------------------- ассеты (.pmeta) и материалы

def _pmeta_base(name: str, guid: str, tags: list[str], folder: str, atlas_index: int) -> dict:
    return {"enabled": True, "name": name, "guid": {"serializedGuid": guid}, "tags": tags, "assetTypeString": "",
            "atlasIndex": atlas_index, "atlasPtrIndex": 2147483647,
            "assetLocation": {"serializedGuid": ASSET_LOCATION_EXTERNAL}, "assetFolder": folder}


@dataclass
class Asset:
    kind: str          # prop | texture | audio | prefab | material
    name: str
    guid: str
    source: str | None = None    # путь к исходному файлу (obj/png/wav)
    data: bytes | None = None    # содержимое для prefab/material
    meta_extra: dict = field(default_factory=dict)

    @property
    def folder(self) -> str:
        return {"prop": "Props", "texture": "Textures", "audio": "Audio", "prefab": "Prefabs", "material": "Materials"}[self.kind]

    @property
    def file_name(self) -> str:
        if self.source:
            return os.path.basename(self.source)
        return self.name + {"prefab": ".pfab", "material": ".pmat"}[self.kind]

    def pmeta(self) -> dict:
        tags = {"prop": ["props"], "texture": ["textures"], "audio": ["audio", "wav"], "prefab": ["prefabs"],
                "material": ["materials"]}[self.kind]
        atlas = {"prop": 0, "texture": 2147483647, "audio": 1, "prefab": 2, "material": 0}[self.kind]
        d = _pmeta_base(self.name, self.guid, tags, f"/{self.folder}/", atlas)
        if self.kind == "prop":
            d["m_meshAsset"] = dict(_pmeta_base(self.name, new_guid(), ["meshes"], "", 2147483647), m_recalculateNormals=False)
        elif self.kind == "texture":
            d.update(m_compression=0, m_filter=1, m_wrapMode=0)
        elif self.kind == "prefab":
            d["isEnabled"] = True
        d.update(self.meta_extra)
        return d


# Свойства шейдера Standard Decal Receiver в порядке записи PummelMaterial.Serialize (снято с Corner_Red.pmat.pmeta)
_STD_SHADER_PROPS = [
    ("_Color", 0), ("_MainTex", 4), ("_Cutoff", 3), ("_Glossiness", 3), ("_GlossMapScale", 3),
    ("_SmoothnessTextureChannel", 2), ("_Metallic", 3), ("_MetallicGlossMap", 4), ("_SpecularHighlights", 2),
    ("_GlossyReflections", 2), ("_BumpScale", 2), ("_BumpMap", 4), ("_Parallax", 3), ("_ParallaxMap", 4),
    ("_OcclusionStrength", 3), ("_OcclusionMap", 4), ("_EmissionColor", 0), ("_EmissionMap", 4), ("_DetailMask", 4),
    ("_DetailAlbedoMap", 4), ("_DetailNormalMapScale", 2), ("_DetailNormalMap", 4), ("_UVSec", 2), ("_Mode", 2),
    ("_SrcBlend", 2), ("_DstBlend", 2), ("_ZWrite", 2),
]
_STD_SHADER_DEFAULTS = {
    "_Color": (1, 1, 1, 1), "_Cutoff": 0.5, "_Glossiness": 0.5, "_GlossMapScale": 1.0, "_SmoothnessTextureChannel": 0.0,
    "_Metallic": 0.0, "_SpecularHighlights": 1.0, "_GlossyReflections": 1.0, "_BumpScale": 1.0, "_Parallax": 0.02,
    "_OcclusionStrength": 1.0, "_EmissionColor": (0, 0, 0, 1), "_DetailNormalMapScale": 1.0, "_UVSec": 0.0,
    "_Mode": 0.0, "_SrcBlend": 1.0, "_DstBlend": 0.0, "_ZWrite": 1.0,
}


def material_shader_data(albedo_guid: str | None, color=(1, 1, 1, 1), smoothness=0.5, metallic=0.0,
                         tiling=(1.0, 1.0), offset=(0.0, 0.0)) -> bytes:
    """Байты m_shaderData для материала Standard Decal Receiver (формат PMAT 0.2). Не проверено в редакторе."""
    w = _w()
    w.string("PMAT"); w.u8(0); w.u8(2)
    w.i32(len(_STD_SHADER_PROPS))
    values = dict(_STD_SHADER_DEFAULTS, _Color=color, _Glossiness=smoothness, _Metallic=metallic)
    for name, kind in _STD_SHADER_PROPS:
        w.string(name); w.u8(kind)
        if kind in (0, 1):
            w.raw(enc_color(values[name]))
        elif kind in (2, 3):
            w.f32(values[name])
        elif kind == 4:
            w.raw(enc_ref(albedo_guid if name == "_MainTex" else None))
    w.i32(0)  # keywords
    w.f32(tiling[0]); w.f32(tiling[1]); w.f32(offset[0]); w.f32(offset[1])
    return w.bytes()


DEFAULT_WEAPON_INFO = {
    "weaponHitType": 0, "spawnBulletEffect": True, "bulletColor": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0},
    "spawnTrailEffect": False, "trailStartColor": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0},
    "trailEndColor": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0}, "trailWidth": 0.25, "trailLength": 25.0,
    "fireSound": 1, "customFireSound": {"m_assetGUID": {"serializedGuid": GUID_EMPTY}},
    "beamSound": 1, "customBeamSound": {"m_assetGUID": {"serializedGuid": GUID_EMPTY}},
    "basicInfo": {"cooldown": 1.0, "damage": 1},
    "scanInfo": {"weaponSpreadType": 0, "horizontalSpreadAngle": {"x": -5.0, "y": 5.0},
                 "verticalSpreadAngle": {"x": -5.0, "y": 5.0}, "shotCount": 1, "range": 100.0, "hitOnce": True,
                 "beamDamageCooldown": 0.25},
    "areaInfo": {"weaponAreaShape": 0, "radius": 1.0},
    "meleeInfo": {"damage": 10, "range": 2.0, "attackAnimation": 0},
    "stunOnHit": False, "stunDuration": 1.0, "fireType": 0,
}


# ---------------------------------------------------------------- мод целиком

@dataclass
class Mod:
    name: str
    template: str = "Minimal Third Person"   # откуда брать Lighting/PostProcessing/Preview/InputHelp
    roots: list[Obj] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    description: str = ""
    # Minigame settings
    rounds: int = 1
    round_duration: float = 60.0
    points_to_win: int = 5
    placement: int = Placement.MOST_POINTS
    end_conditions: int = EndCondition.TIMER
    player_type: int = PlayerType.THIRD_PERSON
    min_players_alive: int = 1
    settings_overrides: dict = field(default_factory=dict)   # прямые правки в SimpleModPlayerSettings
    # триггеры игрока в SimpleModPlayerSettings: {"onDeathTrigger": [act_*(...)], ...}; в событии смерти
    # Source — убийца (или последний, кто нанёс урон), Receiver — умерший (SimpleModPlayer.KillPlayer)
    player_triggers: dict = field(default_factory=dict)
    preview_image: str | None = None   # PNG/JPG для Data/Preview.jpg (окно Load a saved mod), если редактор ещё не снял своё
    music_guid: str | None = None      # аудио-ассет мода вместо музыки шаблона (SimpleMinigameSettings.MusicGUID); не проверено
    min_players: int = 2
    max_players: int = 8

    def add(self, o: Obj) -> Obj:
        self.roots.append(o)
        return o

    # --- ассеты
    def add_file_asset(self, kind: str, path: str) -> Asset:
        a = Asset(kind, os.path.splitext(os.path.basename(path))[0], new_guid(), source=path)
        self.assets.append(a)
        return a

    def add_prefab(self, root: Obj) -> Asset:
        """Префаб = .pfab с настоящим корнем; корень неактивен, как у всех префабов игры."""
        root.active = False
        scene = P.Scene(1, 0, [root.to_gameobject()], prefab=True)
        a = Asset("prefab", root.name, new_guid(), data=P.serialize(scene))
        self.assets.append(a)
        return a

    def add_material(self, name: str, albedo: Asset | None, **kw) -> Asset:
        a = Asset("material", name, new_guid(), data=b"\x04PMAT",
                  meta_extra={"m_shaderName": "Standard Decal Receiver",
                              "m_shaderData": list(material_shader_data(albedo.guid if albedo else None, **kw))})
        self.assets.append(a)
        return a

    # --- запись
    def write(self, workshop_mods_dir: str) -> str:
        root = os.path.join(os.path.expandvars(workshop_mods_dir), self.name)
        data_dir = os.path.join(root, "Data")
        os.makedirs(data_dir, exist_ok=True)
        tpl = os.path.join(GAME_TEMPLATES, self.template, "Data")
        for fn in ("Lighting.json", "PostProcessing.data"):
            shutil.copyfile(os.path.join(tpl, fn), os.path.join(data_dir, fn))
        # Что пользователь задал в редакторе, пересборка не трогает:
        # - Data/Preview.jpg редактор перезаписывает снимком камеры сцены при каждом сохранении (EditorSystem.SavePreviewScreenshot);
        #   свой файл кладём, только если там пусто, шаблонная картинка или наш прошлый файл. Наш — PNG (Texture2D.LoadImage
        #   читает и PNG), редактор всегда пишет JPEG (EncodeToJPG), поэтому чей файл, видно по сигнатуре;
        # - ScreenshotTextureGuid (Mod Settings → Minigame Details → Preview Image) и WorkshopItem.json (publishedFileId,
        #   Square Preview, видимость) берём из уже существующих файлов мода.
        preview = os.path.join(data_dir, "Preview.jpg")
        current = open(preview, "rb").read() if os.path.exists(preview) else None
        template_preview = open(os.path.join(tpl, "Preview.jpg"), "rb").read()
        if current is None or current == template_preview or current[:8] == PNG_SIGNATURE:
            with open(preview, "wb") as fh:
                fh.write(open(self.preview_image, "rb").read() if self.preview_image else template_preview)
        old_mdd = self._read_json(data_dir, "MinigameDefinitionData.json")
        old_workshop = self._read_json(data_dir, "WorkshopItem.json")

        scene = P.Scene(1, 0, [o.to_gameobject() for o in self.roots])
        P.save(scene, os.path.join(data_dir, "MainScene.scene"))

        for a in self.assets:
            folder = os.path.join(root, "Assets", a.folder)
            os.makedirs(folder, exist_ok=True)
            target = os.path.join(folder, a.file_name)
            if a.source:
                shutil.copyfile(a.source, target)
            else:
                with open(target, "wb") as fh:
                    fh.write(a.data)
            with open(target + ".pmeta", "w", encoding="utf-8") as fh:
                json.dump(a.pmeta(), fh, ensure_ascii=False, separators=(",", ":"))

        self._write_json(data_dir, "Meta.json", {
            "MetaDataVersion": 1, "ModVersion": 1, "ModCreatedVersion": 1, "Name": self.name, "ModType": 3,
            "LastModified": _dt.datetime.now().astimezone().isoformat(),
            "SelectedLightingPreset": "Default", "SelectedPostProcessingPreset": "Default", "IsUnlocked": False})
        if old_workshop is None:
            self._write_json(data_dir, "WorkshopItem.json", {
                "Version": 0, "title": self.name, "description": self.description, "language": "english", "metaData": "",
                "visibility": 2, "tags": ["Minigame"], "isInternal": False, "previewFiles": [], "publishedFileId": 256,
                "previewImageGuid": {"serializedGuid": GUID_EMPTY}})
        with open(os.path.join(tpl, "MinigameDefinitionData.json"), encoding="utf-8") as fh:
            mdd = json.load(fh)
        if old_mdd and old_mdd.get("ScreenshotTextureGuid"):
            mdd["ScreenshotTextureGuid"] = old_mdd["ScreenshotTextureGuid"]
        mdd.update(MinigameName=self.name, Description=self.description, MinPlayers=self.min_players, MaxPlayers=self.max_players)
        self._write_json(data_dir, "MinigameDefinitionData.json", mdd)
        with open(os.path.join(tpl, "ModSettings.json"), encoding="utf-8") as fh:
            ms = json.load(fh)
        ms["SimpleMinigameSettings"].update(
            NumberOfRounds=self.rounds, RoundDuration=float(self.round_duration), PointsToWin=self.points_to_win,
            PlacementCondition=self.placement, EndConditions=self.end_conditions, ChosenPlayerType=self.player_type,
            MinPlayersAlive=self.min_players_alive)
        if self.music_guid:
            ms["SimpleMinigameSettings"]["MusicGUID"] = {"serializedGuid": self.music_guid}
        ms["SimpleModPlayerSettings"].update(self.settings_overrides)
        refs = []
        for trig_name, actions in self.player_triggers.items():
            trig = ms["SimpleModPlayerSettings"][trig_name]
            trig["m_actions"] = []
            for type_id, data in actions:
                rid = 1000 + len(refs)
                trig["m_actions"].append({"rid": rid})
                refs.append({"rid": rid, "type": {"class": ACTION_CLASS[type_id], "ns": "ModSystem.Logic", "asm": "Assembly-CSharp"},
                             "data": data})
        ms["references"] = {"version": 2, "RefIds": refs}   # SerializeReference, как в InbuiltMods/Aftershock Arena
        self._write_json(data_dir, "ModSettings.json", ms)
        return root

    @staticmethod
    def _read_json(folder: str, name: str) -> dict | None:
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8-sig") as fh:
            return json.load(fh)

    @staticmethod
    def _write_json(folder: str, name: str, data: dict):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=4, ensure_ascii=False)
