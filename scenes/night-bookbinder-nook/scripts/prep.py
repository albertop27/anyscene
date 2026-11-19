"""Prep generated props into props/<id>.blend (real scale, bottom-centre origin, front -Y, decimated, textures <= 2K).

blender -b --factory-startup --python scenes/night-bookbinder-nook/scripts/prep.py -- [id ...]
For each id in assets.json (all, or the ids given): model = picks.json[id]["model"] ("trellis2" | "pixal3d"; default trellis2 when the
prop has no pick). Reads assets/gen/<model>/<id>/model.glb (relative to the repo root). A missing GLB is skipped (dress.py then uses
a placeholder box). Pixal3D meshes are levelled and front-faced first with scripts/blender/canonicalize.py of the playground,
--ref = the trellis2 GLB of the same id when it exists; the canonical GLB is kept in props/_canon/<id>.glb.
TRELLIS 2 and the canonicalized Pixal3D both face -Y, so no further turn (picks.json may add "yaw": degrees for a stubborn one).
Heroes <= 150k tris, others <= 60k. Gotchas: glTF imports use QUATERNION rotation (we only transform mesh data), images arrive packed:
only images we resized are re-packed (re-packing an untouched one drops its data and the prop renders magenta).
"""
import json
import math
import os
import subprocess
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = os.environ.get("ANYSCENE_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCN = os.path.join(ROOT, "scenes", "night-bookbinder-nook")
CANON = os.environ.get("CANONICALIZE", r"canonicalize.py")
MAX_TEX = 2048
HERO_TRIS, OTHER_TRIS = 150_000, 60_000

man = {a["id"]: a for a in json.load(open(os.path.join(SCN, "assets.json")))["generate"]}
_pp = os.path.join(SCN, "picks.json")
picks = json.load(open(_pp)) if os.path.exists(_pp) else {}
only = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def glb_for(pid, model):
    return os.path.join(ROOT, "assets", "gen", model, pid, "model.glb")


def canonicalize(pid):
    """Level + front-face a Pixal3D GLB in a child Blender; returns the path to use (raw GLB if it fails)."""
    src = glb_for(pid, "pixal3d")
    out_dir = os.path.join(SCN, "props", "_canon")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{pid}.glb")
    cmd = [bpy.app.binary_path, "-b", "--factory-startup", "-P", CANON, "--", src, out, "--report", os.path.join(out_dir, f"{pid}.json")]
    ref = glb_for(pid, "trellis2")
    if os.path.exists(ref):
        cmd += ["--ref", ref]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        print("PREP canonicalize FAILED", pid, (r.stdout + r.stderr)[-400:])
        return src
    return out


def prep(pid):
    a = man[pid]
    model = picks.get(pid, {}).get("model", "trellis2")
    glb = glb_for(pid, model)
    if not os.path.exists(glb):
        print(f"PREP SKIP {pid}: no {glb}")
        return
    if model == "pixal3d":
        glb = canonicalize(pid)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=glb)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    for o in bpy.data.objects:
        o.select_set(o.type == "MESH")
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.parent = None
    bpy.context.view_layer.update()
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)  # bake node transforms into the mesh
    for o in [o for o in bpy.data.objects if o is not ob]:
        bpy.data.objects.remove(o)
    yaw = -math.radians(picks.get(pid, {}).get("yaw", 0))
    if yaw:
        ob.data.transform(Matrix.Rotation(yaw, 4, "Z"))
    vs = [v.co for v in ob.data.vertices]
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    s = a["size"] / ((hi - lo).z if a["fit"] == "h" else max(hi - lo))
    ob.data.transform(Matrix.Translation(-Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))))  # bottom centre
    ob.data.transform(Matrix.Scale(s, 4))
    ob.rotation_mode = "XYZ"  # glTF objects are QUATERNION: rotation_euler would be ignored
    ob.location, ob.rotation_euler, ob.scale = (0, 0, 0), (0, 0, 0), (1, 1, 1)
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    budget = HERO_TRIS if a.get("hero") else OTHER_TRIS
    if tris > budget:
        m = ob.modifiers.new("dec", "DECIMATE")
        m.ratio = budget / tris
        bpy.ops.object.modifier_apply(modifier="dec")
    for p in ob.data.polygons:
        p.use_smooth = True
    for img in bpy.data.images:  # textures <= 2K; re-pack ONLY what we resized
        if img.size[0] and max(img.size) > MAX_TEX:
            f = MAX_TEX / max(img.size)
            img.scale(max(1, int(img.size[0] * f)), max(1, int(img.size[1] * f)))
            img.pack()
    ob.name = pid
    for i, slot in enumerate(ob.material_slots):
        if slot.material:
            slot.material.name = f"{pid}_mat{i}"
    coll = bpy.data.collections.new(pid)
    bpy.context.scene.collection.children.link(coll)
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    coll.objects.link(ob)
    ob["source_model"] = model
    ob["tris"] = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    os.makedirs(os.path.join(SCN, "props"), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SCN, "props", f"{pid}.blend"))
    d = ob.dimensions
    print(f"PREP {pid} {model} tris {tris}->{ob['tris']} dims {d.x:.2f}x{d.y:.2f}x{d.z:.2f}")


for pid in man:
    if only and pid not in only:
        continue
    try:
        prep(pid)
    except Exception as e:  # keep going: the other props still get prepped
        print("PREP FAILED", pid, repr(e))
