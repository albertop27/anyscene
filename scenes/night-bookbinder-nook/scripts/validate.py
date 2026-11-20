"""Placement validator for the dressed nook, then pipeline/grounding.py.

blender -b scenes/night-bookbinder-nook/dressed.blend --python scenes/night-bookbinder-nook/scripts/validate.py -- [--no-grounding]
        [--layout] [--report out.json]
Flags: FLOAT (prop's underside, probed on a 7x7 grid, > 1 cm above the nearest surface under it), SUNK (contact points > 1 cm inside the support), CLIP (prop x prop
BVH overlap), FURNITURE (prop mesh, lifted 3 mm, intersecting shell/furniture/shelving), OUT (outside the room box), SCALE (off the
manifest height by > 25 %).
--layout: checking a layout.blend the owner edited by hand. Besides the tagged props it also checks NEW meshes: anything in the
"any top-level mesh without the "built" tag that build.sh --hand puts on everything (an appended or freshly added object).
Summary line: "VALIDATE n issues over m props". Then runs grounding.py (feet-based float check) with --max-gap 2, except with
--layout, where the grid float check covers it (grounding.py's lowest-vertex rays miss a support narrower than the prop).
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
LAYOUT = "--layout" in argv
SKIP_COLLS = ("shell", "furniture", "shelving", "storefront", "ceiling", "night_rig", "_prop_sources", "cameras")


def is_new(o):
    """A mesh the owner added by hand: build.sh --hand tags every object it copies into layout.blend as "built", so an
    untagged top-level mesh is new (added or appended). Duplicates of placed props keep their tags and are checked anyway."""
    return o.type == "MESH" and o.parent is None and not o.get("placed") and not o.get("built")         and not any(c.name in SKIP_COLLS for c in o.users_collection)


props = [o for o in sc.objects if o.visible_get() and (o.get("placed") or (LAYOUT and is_new(o)))]
new_props = [o.name for o in props if not o.get("placed")]
if LAYOUT and not any(o.get("built") for o in sc.objects):
    print("WARNING: no 'built' tags: this file was not made by build.sh --hand, so every untagged mesh counts as new")
issues = []
NOT_SURFACE = ("haze", "drizzle", "rain", "steam", "smoke", "fog", "mist", "volume", "glow")


def all_trees():
    """One BVH per visible mesh (props, furniture, floor, walls), so a prop's rays can skip the prop itself."""
    out = {}
    for o in sc.objects:
        if o.type == "MESH" and o.visible_get() and not o.hide_render and not any(k in o.name.lower() for k in NOT_SURFACE):
            eo = o.evaluated_get(dg)
            me = eo.to_mesh()
            if len(me.polygons):
                mw = o.matrix_world
                out[o.name] = BVHTree.FromPolygons([mw @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
            eo.to_mesh_clear()
    return out


def sunk_depth(o, trees_):
    """How deep the prop's lowest points sit inside something solid: rays go UP from each contact point and must hit the
    underside of an upward-facing surface (a table top seen from inside). Median over the contact points, in metres."""
    eo = o.evaluated_get(dg)
    me = eo.to_mesh()
    vs = [o.matrix_world @ v.co for v in me.vertices]
    eo.to_mesh_clear()
    if len(vs) < 4:
        return 0.0, None
    zmin = min(v.z for v in vs)
    band = max(0.01, 0.03 * (max(v.z for v in vs) - zmin))
    feet = [v for v in vs if v.z <= zmin + band]
    feet = feet[:: max(1, len(feet) // 30)]
    depths, into = [], {}
    for f in feet:
        best = None
        for name, t in trees_.items():
            if name == o.name:
                continue
            loc, nrm, _, dist = t.ray_cast(f + Vector((0, 0, 0.001)), Vector((0, 0, 1)), 0.5)
            if loc is not None and nrm.z > 0.5 and (best is None or dist < best[0]):
                best = (dist, name)
        depths.append(best[0] if best else 0.0)
        if best:
            into[best[1]] = into.get(best[1], 0) + 1
    depths.sort()
    return depths[len(depths) // 2], (max(into, key=into.get) if into else None)


def float_gap(o, trees_, n=7):
    """Contact gap at the prop's real underside. An n x n grid over its footprint: at each point a ray UP from below finds
    the prop's own bottom there (so points over empty parts of an L-shape or a gap between legs are skipped), then a ray
    DOWN from just under that bottom finds the nearest other surface. The prop rests if any point touches, so the gap is
    the smallest one. Works for tilted props and for props wider than their support (a sheet on a book stack); the
    lowest-corner check missed both."""
    own = trees_.get(o.name)
    if own is None:
        return 0.0, None
    lo, hi = world_bb(o)
    probes = []
    for i in range(n):
        for j in range(n):
            x = lo.x + (hi.x - lo.x) * (i + 0.5) / n
            y = lo.y + (hi.y - lo.y) * (j + 0.5) / n
            b = own.ray_cast(Vector((x, y, lo.z - 1.0)), Vector((0, 0, 1)), 1.0 + (hi.z - lo.z) + 0.01)
            if b[0] is not None:
                probes.append(b[0])
    # plus the lowest vertices (feet, base rings): thin legs fall between grid points
    eo = o.evaluated_get(dg)
    me = eo.to_mesh()
    vs = [o.matrix_world @ v.co for v in me.vertices]
    eo.to_mesh_clear()
    if vs:
        band = max(0.01, 0.03 * (hi.z - lo.z))
        feet = [v for v in vs if v.z <= lo.z + band]
        probes += feet[:: max(1, len(feet) // 40)]
    best = None
    for p in probes:
        if True:
            # start 2 cm above the underside: a prop dropped flush sits a hair INTO its support, and a ray starting just
            # below the underside would begin inside the support and report its thickness (a 6.9 cm table top)
            start = p + Vector((0, 0, 0.02))
            near = None
            for name, t in trees_.items():
                if name == o.name:
                    continue
                h = t.ray_cast(start, Vector((0, 0, -1)), 50.0)
                if h[0] is not None and (near is None or h[3] < near[0]):
                    near = (h[3], name)
            if near:
                g = near[0] - 0.02  # distance from the underside down to the surface (negative = resting a hair into it)
                if best is None or g < best[0]:
                    best = (g, near[1])
    if best is None:
        return lo.z, None
    return max(0.0, best[0]), best[1]


TREES = all_trees()


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
        depth, into = sunk_depth(o, TREES)
        if depth > 0.01:
            issues.append(f"SUNK {o.name} {depth * 100:.1f} cm into {into}")
            continue  # its float ray starts inside the support and would report the support's thickness
        gap, under = float_gap(o, TREES)
        if gap > 0.01:
            issues.append(f"FLOAT {o.name} {gap * 100:.1f} cm above {under or 'nothing'}")
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
if new_props:
    print("NEW (added by hand, untagged):", ", ".join(new_props))
print(f"VALIDATE {len(issues)} issues over {len(props)} props")
if "--report" in argv:
    json.dump({"blend": bpy.data.filepath, "props": len(props), "new": new_props, "issues": issues},
              open(argv[argv.index("--report") + 1], "w"), indent=1)

if "--no-grounding" not in argv and not LAYOUT:  # --layout: the grid float check above replaces grounding.py
    sys.argv = ["blender", "--", "--prefix", "bk_", "--max-gap", "2", "--tol", "0.01"]
    runpy.run_path(os.path.join(ROOT, "pipeline", "grounding.py"), run_name="__main__")
    sys.argv = ["blender", "--", "--prefix", "bk_", "--max-gap", "2", "--tol", "0.01", "--all"]
    print("grounding --all (hanging items, check each is meant to hang):")
    runpy.run_path(os.path.join(ROOT, "pipeline", "grounding.py"), run_name="__main__")
