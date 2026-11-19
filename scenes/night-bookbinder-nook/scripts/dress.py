"""Dress the nook: place the prepped props (or named placeholder boxes when props/<id>.blend is missing), big -> small.

blender -b scenes/night-bookbinder-nook/shell.blend --python scenes/night-bookbinder-nook/scripts/dress.py
-> scenes/night-bookbinder-nook/dressed.blend
Library props face -Y (yaw 90 faces +X, -90 faces -X). x, y in metres; kw: "from" = height a drop ray starts at (just under
whatever is overhead), "z" pins the height (hanging things), "scale", "name", "tint" (ob.color variation), "back" (snap to a wall), "single" (drop on one centre ray: floor props that must never perch on a neighbouring counter).
A placeholder is a cube named ph_<id> with dims from assets.json size and a footprint guess (FOOT), so the whole pipeline
runs before any 3D exists. Every placed object gets custom props placed=1, prop_id, placeholder.
"""
import json
import math
import os
import random
import sys

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(__file__))
import lib  # noqa: E402
from lib import SCN, W, D, H  # noqa: E402

random.seed(5)
man = {a["id"]: a for a in json.load(open(os.path.join(SCN, "assets.json")))["generate"]}
sc = bpy.context.scene

# footprint guesses (x, y) in metres for placeholders; height always comes from the manifest
FOOT = {"book_press": (0.55, 0.5), "paper_cutter": (0.7, 0.45), "sewing_frame": (0.42, 0.3), "desk_lamp": (0.22, 0.28),
        "pendant_lamp": (0.36, 0.36), "paper_roll_rack": (0.45, 0.8), "stool": (0.34, 0.34), "glue_pot": (0.15, 0.15),
        "bone_folder_set": (0.1, 0.1), "leather_stack": (0.4, 0.3), "book_stack": (0.25, 0.18), "thread_spools": (0.2, 0.14),
        "old_radio": (0.3, 0.17), "plant_pot": (0.32, 0.32)}
PH_COLOR = {"book_press": (0.18, 0.18, 0.2), "paper_cutter": (0.3, 0.2, 0.12), "sewing_frame": (0.5, 0.35, 0.18),
            "desk_lamp": (0.05, 0.25, 0.12), "pendant_lamp": (0.7, 0.5, 0.2), "paper_roll_rack": (0.5, 0.4, 0.3),
            "stool": (0.4, 0.28, 0.16), "glue_pot": (0.8, 0.8, 0.75), "bone_folder_set": (0.6, 0.45, 0.35),
            "leather_stack": (0.4, 0.1, 0.08), "book_stack": (0.35, 0.12, 0.1), "thread_spools": (0.55, 0.45, 0.3),
            "old_radio": (0.3, 0.17, 0.08), "plant_pot": (0.15, 0.4, 0.12)}

LV = [0.10, 0.48, 0.86, 1.24, 1.62, 2.0, 2.38]
TABLE, COUNTER, CAB = 1.5, 1.6, 1.5  # ray start heights under the pendant / over the counter / back cabinet
BELOW_BEAM = 2.3

# (id, x, y, yaw, kw)   order = big -> small
LAYOUT = [
    ("book_press", 1.75, 3.45, 0, {"from": BELOW_BEAM, "single": True}),
    ("paper_roll_rack", 3.0, 2.95, -90, {"from": BELOW_BEAM, "single": True, "back": "x1"}),
    ("paper_cutter", 2.65, 3.72, 0, {"from": CAB}),
    ("stool", 2.4, 1.65, 25, {"from": BELOW_BEAM, "single": True}),
    ("plant_pot", 0.65, 0.5, 0, {"from": 0.9, "single": True}),
    ("old_radio", 0.2, 2.38, 90, {"from": LV[4] - 0.03, "back": "x0"}),
    # the table pile
    ("sewing_frame", 1.62, 1.75, 0, {"from": TABLE}),
    ("desk_lamp", 1.4, 2.55, 40, {"from": TABLE}),
    ("glue_pot", 1.3, 2.0, 30, {"from": TABLE}),
    ("book_stack", 1.95, 1.95, 15, {"from": TABLE, "scale": 0.7}),
    ("leather_stack", 1.92, 2.6, 8, {"from": TABLE}),
    ("bone_folder_set", 1.38, 1.5, 0, {"from": TABLE}),
    ("thread_spools", 1.9, 1.35, -10, {"from": TABLE}),
    ("thread_spools", 1.35, 1.9, 40, {"from": TABLE, "name": "thread_spools_2", "scale": 0.85, "tint": True}),
    ("bone_folder_set", 2.0, 2.25, 200, {"from": TABLE, "name": "bone_folder_set_2", "scale": 0.9, "tint": True}),
    ("book_stack", 1.8, 2.8, -20, {"from": TABLE, "name": "book_stack_2", "scale": 0.6, "tint": True}),
    ("glue_pot", 1.7, 2.45, 90, {"from": TABLE, "name": "glue_pot_2", "scale": 0.7, "tint": True}),
    # counter + shelf clutter
    ("book_stack", 2.9, 1.3, 70, {"from": COUNTER, "name": "book_stack_counter", "scale": 0.7, "tint": True}),
    ("thread_spools", 2.85, 1.7, 10, {"from": COUNTER, "name": "thread_spools_counter", "tint": True}),
    ("book_stack", 0.17, 3.25, 90, {"from": LV[2] + 0.4, "name": "book_stack_shelf", "scale": 0.55, "tint": True, "back": "x0", "skip_if_clash": True}),
    # hanging last
    ("pendant_lamp", 1.65, 2.0, 0, {"z": 1.85, "hang": True}),
]

# ---------------------------------------------------------------- helpers
C_PROPS = bpy.data.collections.get("props") or bpy.data.collections.new("props")
sc.collection.children.link(C_PROPS)
C_SRC = bpy.data.collections.new("_prop_sources")
sc.collection.children.link(C_SRC)
C_SRC.hide_render = True
bpy.context.view_layer.layer_collection.children[C_SRC.name].exclude = True  # sources stay out of rays and renders


def tint_materials(ob):
    """Multiply Base Color by Object Info > Color, so ob.color varies instances that share mesh and materials."""
    for slot in ob.material_slots:
        m = slot.material
        if not m or not m.node_tree or m.get("tinted"):
            continue
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue
        oi = nt.nodes.new("ShaderNodeObjectInfo")
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type, mx.blend_type = "RGBA", "MULTIPLY"
        lib.sock(mx, "Factor", "VALUE").default_value = 1.0
        inp = bsdf.inputs["Base Color"]
        if inp.is_linked:
            nt.links.new(inp.links[0].from_socket, lib.sock(mx, "A", "RGBA"))
        else:
            lib.sock(mx, "A", "RGBA").default_value = inp.default_value
        nt.links.new(oi.outputs["Color"], lib.sock(mx, "B", "RGBA"))
        nt.links.new(mx.outputs["Result"], inp)
        m["tinted"] = True


def placeholder_source(pid):
    a = man[pid]
    fx, fy = FOOT.get(pid, (0.2, 0.2))
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * fx, v.co.y * fy, (v.co.z + 0.5) * a["size"]))  # bottom-centre origin
    me = bpy.data.meshes.new(f"ph_{pid}")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    me.materials.append(lib.principled(f"ph_{pid}_mat", PH_COLOR.get(pid, (0.5, 0.5, 0.5)), 0.6))
    ob = bpy.data.objects.new(f"ph_{pid}", me)
    ob["placeholder"] = 1
    return ob


_src = {}


def source(pid):
    if pid in _src:
        return _src[pid]
    path = os.path.join(SCN, "props", f"{pid}.blend")
    if os.path.exists(path):
        with bpy.data.libraries.load(path, link=False) as (fr, to):
            to.objects = [pid]
        src = to.objects[0]
        src.name = f"src_{pid}"
        src["placeholder"] = 0
        for c in list(src.users_collection):
            c.objects.unlink(src)
        src.rotation_mode = "XYZ"  # glTF imports are QUATERNION: rotation_euler would be silently ignored
    else:
        print(f"PLACEHOLDER for {pid} (no props/{pid}.blend)")
        src = placeholder_source(pid)
    C_SRC.objects.link(src)
    tint_materials(src)
    _src[pid] = src
    return src


def world_bb(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))), Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))


def drop(ob, start_z, single=False):
    """Rest the object on the highest support under its footprint (5 rays), ignoring itself (moved out of the way)."""
    bpy.context.view_layer.update()
    lo, hi = world_bb(ob)
    cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
    hx, hy = (hi.x - lo.x) * 0.35, (hi.y - lo.y) * 0.35
    off = ob.location.x - cx, ob.location.y - cy
    ob.location.z = -100
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    best = None
    for dx, dy in (((0, 0),) if single else ((0, 0), (hx, hy), (-hx, hy), (hx, -hy), (-hx, -hy))):
        z = start_z
        while True:  # other props are not supports (only furniture and "support" extras like mats and paper)
            hit, loc, _n, _i, hob, _m = sc.ray_cast(dg, Vector((cx + dx, cy + dy, z)), Vector((0, 0, -1)))
            if hit and hob.get("placed") and not hob.get("support"):
                z = loc.z - 0.002
                continue
            break
        if hit and (best is None or loc.z > best):
            best = loc.z
    ob.location.z = best if best is not None else 0.0
    bpy.context.view_layer.update()
    return best


def tree(o, dg):
    eo = o.evaluated_get(dg)
    me = eo.to_mesh()
    me.transform(o.matrix_world)
    t = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    eo.to_mesh_clear()
    return t


_ftrees = None


def furniture_trees():
    """Static BVHs of the shell/furniture (built once): props must not poke into them."""
    global _ftrees
    if _ftrees is None:
        dg = bpy.context.evaluated_depsgraph_get()
        _ftrees = []
        for o in sc.objects:
            if o.type == "MESH" and o.visible_get() and any(c.name in ("furniture", "shelving", "storefront") for c in o.users_collection)                     and not o.name.startswith(("window_glass", "door_leaf_glass")):
                _ftrees.append((o, world_bb(o), tree(o, dg)))
    return _ftrees


def clashes(ob, others):
    """First object whose mesh intersects ob (ob lifted 3 mm so resting flush is not a hit), or None."""
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = world_bb(ob)
    t = None
    cands = [(o, world_bb(o), None) for o in others if o is not ob] + furniture_trees()
    for o, (blo, bhi), ft in cands:
        if any(hi[k] < blo[k] or bhi[k] < lo[k] for k in range(3)):
            continue
        if t is None:
            eo = ob.evaluated_get(dg)
            me = eo.to_mesh()
            me.transform(lib.Matrix.Translation((0, 0, 0.003)) @ ob.matrix_world)
            t = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
            eo.to_mesh_clear()
        if len(t.overlap(ft or tree(o, dg))) > 20:
            return o
    return None


def resolve(ob, start_z, others, single=False):
    """Spiral-search a clear spot on the same support, re-dropping at every step."""
    if not clashes(ob, others):
        return True
    x0, y0, z0 = ob.location.x, ob.location.y, ob.location.z
    for ring in range(1, 14):
        for k in range(8 * ring):
            ang = 2 * math.pi * k / (8 * ring)
            ob.location = (x0 + 0.04 * ring * math.cos(ang), y0 + 0.04 * ring * math.sin(ang), z0)
            drop(ob, start_z, single)
            if abs(ob.location.z - z0) < 0.02 and not clashes(ob, others):
                return True
    ob.location = (x0, y0, z0)
    return False


def place(pid, x, y, yaw, kw):
    src = source(pid)
    ob = src.copy()
    ob.name = "bk_" + kw.get("name", pid)
    C_PROPS.objects.link(ob)
    s = kw.get("scale", 1.0) * random.uniform(0.98, 1.02)
    ob.scale = (s, s, s)
    ob.rotation_mode = "XYZ"
    ob.rotation_euler = (0, 0, math.radians(yaw + random.uniform(-3, 3)))
    ob.location = (x, y, kw.get("z", 0))
    if kw.get("tint"):
        ob.color = (random.uniform(0.75, 1.05), random.uniform(0.75, 1.0), random.uniform(0.7, 1.0), 1)
    ob["placed"] = True
    ob["prop_id"] = pid
    ob["placeholder"] = src.get("placeholder", 0)
    ob["wall"] = "z" in kw
    ob["scaled"] = "scale" in kw
    bpy.context.view_layer.update()
    b = kw.get("back")
    if b:
        lo, hi = world_bb(ob)
        ob.location.x += (0.03 - lo.x) if b == "x0" else ((W - 0.015) - hi.x)
        bpy.context.view_layer.update()
    if "z" not in kw:
        drop(ob, kw["from"], kw.get("single", False))
    return ob


def small_box(name, w, d, h, mat, x, y, yaw, start_z, support_z=None):
    """Direct-modelled clutter (paper, mat, ruler) with a bottom-centre origin, dropped like a prop."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * w, v.co.y * d, (v.co.z + 0.5) * h))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new("bk_" + name, me)
    C_PROPS.objects.link(ob)
    ob.rotation_mode = "XYZ"
    ob.rotation_euler = (0, 0, math.radians(yaw))
    ob.location = (x, y, 0)
    ob["placed"] = True
    ob["prop_id"] = ""
    ob["support"] = True
    drop(ob, start_z)
    return ob


# ---------------------------------------------------------------- pass 1: base clutter that other props rest on
paper = lib.principled("paper_white", (0.75, 0.72, 0.62), 0.9)
mat_g = lib.principled("cutting_mat_green", (0.04, 0.14, 0.09), 0.6)
card = lib.principled("board_grey", (0.35, 0.33, 0.28), 0.8)
extras = []
extras.append(small_box("cutting_mat", 0.62, 0.42, 0.004, mat_g, 1.62, 1.75, 0, TABLE))
SMALL = [  # name, w, d, h, mat, x, y, yaw  (loose paper, boards, ruler, an open book: the pile that sells the table)
    ("paper_ream", 0.3, 0.21, 0.07, paper, 1.8, 2.55, 12),
    ("paper_sheets_a", 0.3, 0.21, 0.012, paper, 1.62, 2.15, -15),
    ("paper_sheets_b", 0.3, 0.21, 0.008, paper, 1.66, 2.17, 8),
    ("book_board_stack", 0.24, 0.17, 0.04, card, 1.62, 1.28, 5),
    ("steel_ruler", 0.5, 0.03, 0.002, lib.principled("steel_ruler_mat", (0.5, 0.5, 0.52), 0.35, metal=1.0), 1.55, 1.12, 95),
    ("open_book_left", 0.17, 0.24, 0.02, paper, 1.28, 1.2, 10),
    ("open_book_right", 0.17, 0.24, 0.02, paper, 1.45, 1.2, 10),
    ("counter_papers", 0.28, 0.2, 0.02, paper, 2.85, 1.05, 30),
    ("counter_ticket_pad", 0.1, 0.14, 0.015, lib.principled("pad_red", (0.35, 0.06, 0.05), 0.7), 2.95, 1.5, 100),
]
for nm, w, d, h, mt, x, y, yaw in SMALL:
    extras.append(small_box(nm, w, d, h, mt, x, y, yaw, COUNTER if nm.startswith("counter") else TABLE))
# a few small clutter objects can't sit under the lamp rays: counter ones were dropped from COUNTER height

# ---------------------------------------------------------------- pass 2: props
placed = []
for pid, x, y, yaw, kw in LAYOUT:
    ob = place(pid, x, y, yaw, kw)
    placed.append(ob)
    others = [o for o in placed + extras if not o.get("wall")]
    if not kw.get("hang"):
        ok = resolve(ob, kw["from"], others, kw.get("single", False))
        if not ok:
            if kw.get("skip_if_clash"):
                bpy.data.objects.remove(ob)
                placed.remove(ob)
                print("SKIPPED (no clear spot)", pid)
                continue
            print("UNRESOLVED CLASH", ob.name, "with", clashes(ob, others).name)
    print(f"PLACED {ob.name} at {tuple(round(v, 3) for v in ob.location)} placeholder={bool(ob['placeholder'])}")

# the pendant hangs from a cord to the ceiling
pend = sc.objects.get("bk_pendant_lamp")
if pend:
    top = world_bb(pend)[1].z
    lib.cylinder("bk_pendant_cord", (pend.location.x, pend.location.y, (top + H) / 2), 0.006, H - top + 0.01,
                 lib.principled("cord_black_p", (0.01, 0.01, 0.01), 0.5), C_PROPS)
    box_c = lib.cylinder("bk_pendant_canopy", (pend.location.x, pend.location.y, H - 0.02), 0.05, 0.04, lib.principled("canopy_brass", (0.5, 0.35, 0.12), 0.4, metal=1.0), C_PROPS)

# re-drop everything that rests on something once more (props moved by the resolver), then save
for ob in placed + extras:
    if ob.name in sc.objects and not ob.get("wall"):
        pass  # drop heights were set at the final position inside resolve()/place(); the validator re-checks

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SCN, "dressed.blend"))
print("saved dressed:", len(placed), "props,", len(extras), "extras")
