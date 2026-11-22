"""Apply the accepted Rusted Park art library to a saved original-ten minigame.

python core_style.py SOURCE_GAME_FOLDER NEW_OUTPUT_FOLDER [--game "Ticket Rush"]
"""

import argparse
from fnmatch import fnmatchcase
import json
from pathlib import Path
import shutil
import struct
import sys
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "tools"))
import pmgen as G
import pmscene as P


# Match scene prop names only. Warning surfaces, pickups, aim marks and beam
# assemblies are deliberately absent. All ten scenes already have a park skyline.
PROFILES = {
    "Ticket Rush": "neon-night", "Mascot Throne": "neon-night",
    "Death Carousel": "rust-dusk", "Mascot Range": "rust-dusk", "Sugar Rush": "rust-dusk",
    "Coaster Run": "overcast-day", "Human Cannonball": "overcast-day",
    "Tilt House": "fog-night", "Searchlights": "fog-night", "Bumper Cars": "damp-service",
}
SURFACES = {
    "Ticket Rush": {
        "cracked_concrete": "Ground_? PondCurb_*", "old_wood": "Crates_* Fence_*",
        "paint_teal": "Booth_[0246]", "paint_plum": "Booth_[1357]", "paint_red_heavy": "BrokenBooth"},
    "Death Carousel": {
        "old_wood": "Deck Crate_*", "paint_cream": "Pole_*", "paint_red_heavy": "Roof",
        "paint_teal_heavy": "SunkenBooth", "rust_iron": "Axle"},
    "Coaster Run": {
        "old_wood": "Station Stairs_* CartBed FinishDeck", "cracked_concrete": "Ditch DitchWall_*",
        "rust_iron": "Rail_L Rail_R Rail_Back Trestle_*", "paint_teal_heavy": "Post"},
    "Mascot Throne": {
        "cracked_concrete": "Plaza Dais", "old_wood": "Bridge_* Crate_*",
        "paint_teal_heavy": "Wall_*", "paint_plum": "Booth_*", "paint_cream": "Beam"},
    "Human Cannonball": {
        "old_wood": "Deck PowderCrate_*", "rust_iron": "Cheek_*", "paint_red_heavy": "Booth_*",
        "cracked_concrete": "FarShore"},
    "Mascot Range": {
        "old_wood": "Deck_* AmmoCrate_*", "paint_teal": "Counter Booth_*",
        "paint_teal_heavy": "Screen", "rust_iron": "Stilt_* Post_? Beam"},
    "Sugar Rush": {
        "old_wood": "Bench_* Crate_*", "paint_red_heavy": "Wall_*[02468] CandyStall_*",
        "paint_cream": "Wall_*[13579]", "paint_plum": "Column_*", "cracked_concrete": "Curb_*"},
    "Tilt House": {
        "old_wood": "Trunk Wardrobe FallenChair Seat Back Arm_*", "paint_plum": "Frame",
        "paint_teal_heavy": "Case Booth_*", "cracked_concrete": "Foundation_* Chimney"},
    "Searchlights": {
        "wet_asphalt": "Plaza", "old_wood": "Crates_* Top Fence_*", "paint_teal_heavy": "TicketOffice",
        "paint_red_heavy": "Roof"},
    "Bumper Cars": {
        "wet_asphalt": "Apron", "rust_iron": "Rail_*", "paint_teal_heavy": "ControlBooth",
        "paint_cream": "TicketBooth_*"},
}
# Local positions on existing fixtures. Lights have no collider or shadows.
LIGHTS = {
    "Ticket Rush": ("Lamppost_[0246]", (.9, 4.7, 0), (.76, .81, 1), 1.6, 10),
    "Death Carousel": ("Lamppost_[0246]", (.9, 4.7, 0), (1, .67, .36), 1.6, 9),
    "Coaster Run": ("Lamppost_[03]", (.9, 4.7, 0), (1, .83, .57), 1.2, 8),
    "Mascot Throne": ("Lamppost_[024]", (.9, 4.7, 0), (.76, .81, 1), 1.6, 10),
    "Human Cannonball": ("Lamppost_[01]", (.9, 4.7, 0), (1, .85, .65), 1.2, 8),
    "Mascot Range": ("Lamppost_[01]", (.9, 4.7, 0), (1, .81, .62), 1.6, 9),
    "Sugar Rush": ("Column_*", (0, .48, 0), (1, .77, .56), 1.4, 9),
    "Tilt House": ("Lamppost_[02]", (.9, 4.7, 0), (.77, .86, 1), 1.3, 9),
    "Bumper Cars": ("Lamppost_[12]", (.9, 4.7, 0), (.78, .94, .86), 1.4, 9),
}


def guid(project, key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"rusted-park/core-art/{project}/{key}"))


def json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


class ArtAssets:
    def __init__(self, game):
        self.game = game
        self.catalog = json.loads((HERE / "materials.json").read_bytes())
        self.assets = {}

    def add(self, kind, name, data, **extra):
        key = f"ParkArt_{name}"
        if key not in self.assets:
            self.assets[key] = G.Asset(kind, key, guid(self.game, key), data=data, meta_extra=extra)
        return self.assets[key].guid

    def prop(self):
        return self.add("prop", "surface_cube", (HERE / "surface_cube.obj").read_bytes())

    def material(self, name, tiling):
        spec = self.catalog[name]
        if f"ParkArt_{name}" not in self.assets:
            self.add("texture", name, (HERE / spec["albedo"]).read_bytes())
        texture = self.assets[f"ParkArt_{name}"]
        key = f"{name}_{tiling[0]:g}_{tiling[1]:g}"
        if f"ParkArt_{key}" not in self.assets:
            shader = G.material_shader_data(texture.guid, smoothness=spec["smoothness"],
                                            metallic=spec["metallic"], tiling=tiling)
            self.add("material", key, b"\x04PMAT", m_shaderName="Standard Decal Receiver",
                     m_shaderData=list(shader))
        return self.assets[f"ParkArt_{key}"].guid

    def files(self):
        for a in self.assets.values():
            ext = {"prop": ".obj", "texture": ".png", "material": ".pmat"}[a.kind]
            dest = Path("Assets", a.folder, a.name + ext)
            meta = a.pmeta()
            if a.kind == "prop":
                meta["m_meshAsset"]["guid"]["serializedGuid"] = guid(self.game, a.name + "/mesh")
            yield dest, a.data
            yield dest.with_suffix(ext + ".pmeta"), json_bytes(meta)


def lamp(parent, game, spec):
    _, pos, rgb, power, radius = spec
    light = G.obj("ParkArt_Light", pos=pos).light(color=(*rgb, 1), intensity=power, radius=radius)
    light.transform_guid = guid(game, parent.transform_guid + "/transform")
    comp = light.components[0]
    comp.guid = guid(game, parent.transform_guid + "/light")
    comp.set("guid", G.enc_guid(comp.guid))
    return light.to_gameobject()


def style_project(folder, game, *, replace_lighting):
    """Style a built scene, preserving existing editor lighting on ordinary rebuilds."""
    folder = Path(folder)
    scene_path = Path("Data/MainScene.scene")
    scene = P.load(str(folder / scene_path))
    art = ArtAssets(game)
    matches = set()
    spec = LIGHTS.get(game)
    rules = [(pattern, material) for material, patterns in SURFACES[game].items()
             for pattern in patterns.split()]
    for obj in scene.objects():
        prop = obj.component("ModProp")
        if not prop:
            continue
        if spec and fnmatchcase(obj.name, spec[0]):
            if not any(c.name == "ParkArt_Light" for c in obj.children):
                obj.children.append(lamp(obj, game, spec))
        for pattern, material in rules:
            if not fnmatchcase(obj.name, pattern):
                continue
            matches.add(material)
            size = struct.unpack("<3f", obj.component("ModTransform").prop("scale").raw)
            mesh = prop.prop("prop").raw
            if mesh == G.enc_ref(G.PROP_PLANE):
                u, v = size[0] * 10, size[2] * 10
            else:
                u, v = sorted(size, reverse=True)[:2]
            tile = art.catalog[material]["tile_metres"]
            tiling = tuple(round(max(1, d / tile), 2) for d in (u, v))
            if mesh in (G.enc_ref(G.PROP_CUBE), G.enc_ref(guid(game, "ParkArt_surface_cube"))):
                prop.set("prop", G.enc_ref(art.prop()))
            prop.set("customMaterials", G.enc_ref_array([art.material(material, tiling)]))
            prop.set("tintColor", G.enc_color((1, 1, 1, 1)))
            break
    if matches != set(SURFACES[game]):
        raise ValueError(f"{game}: missing surfaces for {sorted(set(SURFACES[game]) - matches)}")
    files = dict(art.files())
    files[scene_path] = P.serialize(scene)
    if replace_lighting:
        profile = json.loads((HERE / "lighting" / (PROFILES[game] + ".json")).read_bytes())
        if game == "Coaster Run":
            profile.update(fogStartDistance=130., fogEndDistance=280.)
        meta_path = Path("Data/Meta.json")
        meta = json.loads((folder / meta_path).read_bytes())
        meta["SelectedLightingPreset"] = "Custom"
        files[meta_path] = json_bytes(meta)
        files[Path("Data/Lighting.json")] = json_bytes(profile)
    for rel, data in files.items():
        target = folder / rel
        if not target.exists() or target.read_bytes() != data:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    return str(folder)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--game", choices=PROFILES)
    args = parser.parse_args()
    game = args.game or args.source.name
    if game not in PROFILES:
        parser.error("Select one of the original ten projects with --game")
    shutil.copytree(args.source, args.output)
    style_project(args.output, game, replace_lighting=True)
