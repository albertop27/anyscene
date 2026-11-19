"""Placement validator for the dressed nook, then pipeline/grounding.py.

blender -b scenes/night-bookbinder-nook/dressed.blend --python scenes/night-bookbinder-nook/scripts/validate.py -- [--no-grounding]
Flags: FLOAT (lowest point > 1 cm above the support under it), CLIP (prop x prop BVH overlap), FURNITURE (prop mesh, lifted 3 mm,
intersecting shell/furniture/shelving), OUT (outside the room box), SCALE (off the manifest height by > 25 %).
Summary line: "VALIDATE n issues over m props". Then runs grounding.py (feet-based float check) with --max-gap 2.
"""
import json
import os
import runpy
import sys

import bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(__file__))
from lib import ROOT, SCN, W, D, H  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
man = {a["id"]: a for a in json.load(open(os.path.join(SCN, "assets.json")))["generate"]}
sc = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()
props = [o for o in sc.objects if o.get("placed") and o.visible_get()]
issues = []


def world_bb(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))), Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))


def mesh_tree(o, lift=0.0):
    eo = o.evaluated_get(dg)
    me = eo.to_mesh()
    me.transform(Matrix.Translation((0, 0, lift)) @ o.matrix_world)
    t = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    eo.to_mesh_clear()
    return t


for o in props:
    lo, hi = world_bb(o)
    if lo.x < -0.02 or lo.y < -0.02 or hi.x > W + 0.02 or hi.y > D + 0.02 or hi.z > H + 0.01:
        issues.append(f"OUT {o.name} bb {tuple(round(v, 2) for v in lo)}..{tuple(round(v, 2) for v in hi)}")
    if not o.get("wall"):
        z0 = o.location.z
        o.location.z = -100  # out of the way of its own ray
        bpy.context.view_layer.update()
        dg2 = bpy.context.evaluated_depsgraph_get()
        # same 5-ray footprint probe as dress.drop(): a prop half on a sheet of paper is resting, not floating
        cx, cy, hx, hy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2, (hi.x - lo.x) * 0.35, (hi.y - lo.y) * 0.35
        best = None
        for dx, dy in ((0, 0), (hx, hy), (-hx, hy), (hx, -hy), (-hx, -hy)):
            h_, l_, n, i, ob_, m = sc.ray_cast(dg2, Vector((cx + dx, cy + dy, lo.z + 0.02)), Vector((0, 0, -1)))
            if h_ and (best is None or l_.z > best[0]):
                best = (l_.z, ob_)
        o.location.z = z0
        bpy.context.view_layer.update()
        gap = (lo.z - best[0]) if best else lo.z
        hit, ob = best is not None, (best[1] if best else None)
        if gap > 0.01:
            issues.append(f"FLOAT {o.name} {gap * 100:.1f} cm above {ob.name if hit else 'nothing'}")
    a = man.get(o.get("prop_id"))
    if a and not o.get("scaled"):
        got = o.dimensions.z if a["fit"] == "h" else max(o.dimensions)
        if abs(got / a["size"] - 1) > 0.25:
            issues.append(f"SCALE {o.name} {got:.2f} m vs {a['size']} m")

dg = bpy.context.evaluated_depsgraph_get()
boxes = {o.name: world_bb(o) for o in props}
trees = {o.name: mesh_tree(o) for o in props}
names = list(trees)
for i, a_ in enumerate(names):
    for b_ in names[i + 1:]:
        (alo, ahi), (blo, bhi) = boxes[a_], boxes[b_]
        if any(ahi[k] < blo[k] or bhi[k] < alo[k] for k in range(3)):
            continue
        n = len(trees[a_].overlap(trees[b_]))
        if n > 40:
            issues.append(f"CLIP {a_} x {b_} ({n} tri pairs)")

FURN_COLLS = ("shell", "furniture", "shelving", "storefront", "ceiling")
furn = [o for o in sc.objects if o.type == "MESH" and o.visible_get() and any(c.name in FURN_COLLS for c in o.users_collection)
        and not o.name.startswith(("floor", "pavement", "street", "window_glass", "door_leaf_glass", "baseboard"))]
ftrees = {f.name: (mesh_tree(f), world_bb(f)) for f in furn}
for o in props:
    t = mesh_tree(o, 0.003)  # lifted 3 mm: resting flush on the support is not a hit
    alo, ahi = boxes[o.name]
    for fname, (ft, (blo, bhi)) in ftrees.items():
        if any(ahi[k] < blo[k] or bhi[k] < alo[k] for k in range(3)):
            continue
        n = len(t.overlap(ft))
        if n > 20:
            issues.append(f"FURNITURE {o.name} x {fname} ({n} tri pairs)")

for s in issues:
    print(s)
print(f"VALIDATE {len(issues)} issues over {len(props)} props")

if "--no-grounding" not in argv:
    sys.argv = ["blender", "--", "--prefix", "bk_", "--max-gap", "2", "--tol", "0.01"]
    runpy.run_path(os.path.join(ROOT, "pipeline", "grounding.py"), run_name="__main__")
    sys.argv = ["blender", "--", "--prefix", "bk_", "--max-gap", "2", "--tol", "0.01", "--all"]
    print("grounding --all (hanging items, check each is meant to hang):")
    runpy.run_path(os.path.join(ROOT, "pipeline", "grounding.py"), run_name="__main__")
