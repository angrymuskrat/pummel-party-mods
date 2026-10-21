"""Парсер и сериализатор MainScene.scene (формат PMH) редактора Pummel Party.

Формат восстановлен из ModHierarchySerializer / ModReflectionTypes (Assembly-CSharp.dll, Mono):

    string "PMH", u16 major=1, u16 minor=0
    u16 rootCount, затем rootCount объектов; объект, рекурсивно:
        string name, bool active, i32 layer, string tag, u16 childCount, дети…
    (сцена пишется с ignoreRoot: у невидимого корня нет ни имени, ни компонентов)
    для каждого объекта в порядке обхода: string transformGuid, i32 n, n × (string typeName, string guid, bool enabled)
    для каждого компонента в том же порядке: u16 k, k × (string propName, i32 size, payload[size])

Строки — .NET BinaryWriter: 7-битная длина + UTF-8. Свойства хранятся с именем и размером,
поэтому незнакомые свойства сохраняются как сырые байты и записываются обратно без потерь.

CLI:  python pmscene.py dump <scene>        — дерево объектов и компонентов со свойствами
      python pmscene.py roundtrip <scene…>  — проверка побайтового совпадения parse→write
      python pmscene.py schema <scene…>     — сводка: тип компонента → имена свойств и размеры
"""
from __future__ import annotations

import io
import struct
import sys
from dataclasses import dataclass, field

MAGIC = "PMH"


# ---------------------------------------------------------------- бинарные примитивы

class Reader:
    def __init__(self, data: bytes):
        self.b = data
        self.p = 0

    def read(self, n: int) -> bytes:
        if self.p + n > len(self.b):
            raise EOFError(f"нужно {n} байт на смещении {self.p}, в файле {len(self.b)}")
        out = self.b[self.p:self.p + n]
        self.p += n
        return out

    def u8(self): return self.read(1)[0]
    def bool(self): return self.u8() != 0
    def u16(self): return struct.unpack("<H", self.read(2))[0]
    def i32(self): return struct.unpack("<i", self.read(4))[0]
    def f32(self): return struct.unpack("<f", self.read(4))[0]

    def varint(self) -> int:
        shift, value = 0, 0
        while True:
            byte = self.u8()
            value |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return value
            shift += 7

    def string(self) -> str:
        return self.read(self.varint()).decode("utf-8")

    @property
    def eof(self): return self.p >= len(self.b)


class Writer:
    def __init__(self):
        self.out = bytearray()

    def raw(self, data: bytes): self.out += data
    def u8(self, v: int): self.out.append(v & 0xFF)
    def bool(self, v: bool): self.u8(1 if v else 0)
    def u16(self, v: int): self.out += struct.pack("<H", v)
    def i32(self, v: int): self.out += struct.pack("<i", v)
    def f32(self, v: float): self.out += struct.pack("<f", v)

    def varint(self, v: int):
        while True:
            byte = v & 0x7F
            v >>= 7
            if v:
                self.u8(byte | 0x80)
            else:
                self.u8(byte)
                return

    def string(self, s: str):
        data = s.encode("utf-8")
        self.varint(len(data))
        self.raw(data)

    def bytes(self) -> bytes: return bytes(self.out)


# ---------------------------------------------------------------- модель сцены

@dataclass
class Property:
    name: str
    raw: bytes

    def __repr__(self):
        return f"{self.name}[{len(self.raw)}]"


@dataclass
class Component:
    type_name: str
    guid: str
    enabled: bool = True
    props: list[Property] = field(default_factory=list)

    def prop(self, name: str) -> Property | None:
        for p in self.props:
            if p.name == name:
                return p
        return None

    def set(self, name: str, raw: bytes):
        p = self.prop(name)
        if p is None:
            self.props.append(Property(name, raw))
        else:
            p.raw = raw


@dataclass
class GameObject:
    name: str
    active: bool = True
    layer: int = 0
    tag: str = "Untagged"
    children: list[GameObject] = field(default_factory=list)
    transform_guid: str = ""
    components: list[Component] = field(default_factory=list)

    def walk(self):
        """Обход в порядке сериализации (pre-order)."""
        yield self
        for c in self.children:
            yield from c.walk()

    def component(self, type_name: str) -> Component | None:
        for c in self.components:
            if c.type_name == type_name:
                return c
        return None

    def find(self, name: str) -> GameObject | None:
        for go in self.walk():
            if go.name == name:
                return go
        return None


@dataclass
class Scene:
    major: int
    minor: int
    roots: list[GameObject] = field(default_factory=list)
    prefab: bool = False  # .pfab: один настоящий корень без u16-счётчика

    def objects(self):
        out = []
        for r in self.roots:
            out.extend(r.walk())
        return out

    def find(self, name: str) -> GameObject | None:
        for go in self.objects():
            if go.name == name:
                return go
        return None


# ---------------------------------------------------------------- чтение

def _read_hierarchy(r: Reader) -> GameObject:
    go = GameObject(name=r.string(), active=r.bool(), layer=r.i32(), tag=r.string())
    n = r.u16()
    go.children = [_read_hierarchy(r) for _ in range(n)]
    return go


def parse(data: bytes, prefab: bool = False) -> Scene:
    """prefab=True — файл .pfab: записан с настоящим корнем (SaveTransform без ignoreRoot)."""
    r = Reader(data)
    magic = r.string()
    if magic != MAGIC:
        raise ValueError(f"не PMH-файл: сигнатура {magic!r}")
    major, minor = r.u16(), r.u16()
    if prefab:
        roots = [_read_hierarchy(r)]
    else:
        roots = [_read_hierarchy(r) for _ in range(r.u16())]
    scene = Scene(major, minor, roots, prefab=prefab)
    objects = scene.objects()
    all_components: list[Component] = []
    for go in objects:
        go.transform_guid = r.string()
        n = r.i32()
        for _ in range(n):
            c = Component(type_name=r.string(), guid=r.string(), enabled=r.bool())
            go.components.append(c)
            all_components.append(c)
    for c in all_components:
        k = r.u16()
        for _ in range(k):
            name = r.string()
            size = r.i32()
            c.props.append(Property(name, r.read(size)))
    if not r.eof:
        raise ValueError(f"после сцены остались {len(data) - r.p} байт")
    return scene


def load(path: str) -> Scene:
    with open(path, "rb") as fh:
        return parse(fh.read(), prefab=path.lower().endswith(".pfab"))


# ---------------------------------------------------------------- запись

def _write_hierarchy(w: Writer, go: GameObject):
    w.string(go.name)
    w.bool(go.active)
    w.i32(go.layer)
    w.string(go.tag)
    w.u16(len(go.children))
    for c in go.children:
        _write_hierarchy(w, c)


def serialize(scene: Scene) -> bytes:
    w = Writer()
    w.string(MAGIC)
    w.u16(scene.major)
    w.u16(scene.minor)
    if scene.prefab:
        if len(scene.roots) != 1:
            raise ValueError("у префаба ровно один корень")
    else:
        w.u16(len(scene.roots))
    for root in scene.roots:
        _write_hierarchy(w, root)
    all_components: list[Component] = []
    for go in scene.objects():
        w.string(go.transform_guid)
        w.i32(len(go.components))
        for c in go.components:
            w.string(c.type_name)
            w.string(c.guid)
            w.bool(c.enabled)
            all_components.append(c)
    for c in all_components:
        w.u16(len(c.props))
        for p in c.props:
            w.string(p.name)
            w.i32(len(p.raw))
            w.raw(p.raw)
    return w.bytes()


def save(scene: Scene, path: str):
    with open(path, "wb") as fh:
        fh.write(serialize(scene))


# ---------------------------------------------------------------- CLI

def _dump(scene: Scene):
    print(f"PMH {scene.major}.{scene.minor}")

    def rec(go: GameObject, depth: int):
        flags = "" if go.active else " [inactive]"
        extra = f" layer={go.layer}" if go.layer else ""
        tagx = f" tag={go.tag}" if go.tag != "Untagged" else ""
        print(f"{'  ' * depth}{go.name}{flags}{extra}{tagx}")
        for c in go.components:
            en = "" if c.enabled else " [disabled]"
            print(f"{'  ' * depth}  - {c.type_name}{en}: {', '.join(map(repr, c.props))}")
        for ch in go.children:
            rec(ch, depth + 1)

    for root in scene.roots:
        rec(root, 0)


def _schema(paths: list[str]):
    seen: dict[str, dict[str, set[int]]] = {}
    for path in paths:
        for go in load(path).objects():
            for c in go.components:
                d = seen.setdefault(c.type_name, {})
                for p in c.props:
                    d.setdefault(p.name, set()).add(len(p.raw))
    for t in sorted(seen):
        print(t)
        for name, sizes in seen[t].items():
            print(f"    {name}: {sorted(sizes)}")


def main(argv: list[str]):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, paths = argv[0], argv[1:]
    if cmd == "dump":
        _dump(load(paths[0]))
    elif cmd == "roundtrip":
        ok = True
        for path in paths:
            data = open(path, "rb").read()
            try:
                same = serialize(parse(data, prefab=path.lower().endswith(".pfab"))) == data
            except Exception as exc:  # noqa: BLE001 — отчёт по каждому файлу
                same, exc_text = False, f" ({exc})"
            else:
                exc_text = ""
            ok &= same
            print(f"{'OK ' if same else 'FAIL'} {len(data):>7} B  {path}{exc_text}")
        return 0 if ok else 1
    elif cmd == "schema":
        _schema(paths)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
