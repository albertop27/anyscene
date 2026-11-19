"""Bookbinder nook: scripted room shell, storefront, shelving, work table, counter, tool wall (no generated props).

blender -b --factory-startup --python scenes/night-bookbinder-nook/scripts/build_shell.py
-> scenes/night-bookbinder-nook/shell.blend
Coordinates: x across (0 = shelf wall, 3.2 = right wall), y from the street wall (0) to the back wall (4.0), z up. Metres.
"""
import math
import os
import random
import sys

import bpy
import bmesh

sys.path.insert(0, os.path.dirname(__file__))
import lib  # noqa: E402
from lib import box, collection, cylinder, plane, add_box, add_cyl, mesh_obj, W, D, H, SCN  # noqa: E402

T = 0.2  # wall thickness (outside the interior box)
random.seed(11)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = "METRIC"
P = lib.principled

# ---------------------------------------------------------------- materials
M = {
    "floor": lib.wood("floor_boards", light=(0.34, 0.21, 0.11), dark=(0.15, 0.085, 0.04), scale=1.2, worn=0.7),
    "wall": lib.wall_paint("plaster_wall", base=(0.55, 0.5, 0.42)),
    "ceiling": lib.wall_paint("plaster_ceiling", base=(0.5, 0.46, 0.4)),
    "beam": lib.wood("beam_wood", light=(0.2, 0.12, 0.06), dark=(0.09, 0.05, 0.025), scale=1.0, worn=0.5),
    "shelfwood": lib.wood("shelf_wood", light=(0.38, 0.24, 0.12), dark=(0.19, 0.11, 0.055), scale=2.0, worn=0.4),
    "tablewood": lib.wood("table_wood", light=(0.3, 0.19, 0.1), dark=(0.14, 0.08, 0.04), scale=1.5, worn=0.7),
    "door": lib.wood("door_wood", light=(0.18, 0.2, 0.17), dark=(0.08, 0.1, 0.085), scale=1.0, worn=0.5),  # painted dark green
    "trim": P("window_trim", (0.1, 0.13, 0.11), 0.5),
    "brass": lib.grimy("brass_fittings", (0.62, 0.45, 0.17), (0.25, 0.17, 0.06), rough=(0.25, 0.5), metal=1.0, amount=0.3, bump=0.05),
    "steel": lib.grimy("tool_steel", (0.5, 0.5, 0.5), (0.18, 0.17, 0.15), rough=(0.3, 0.55), metal=1.0, amount=0.3, bump=0.05),
    "glass": lib.rain_glass("window_rain_glass"),
    "doorglass": P("door_glass", (0.9, 0.95, 0.95), 0.03, **{"Transmission Weight": 1.0}),
    "paper": P("paper_cream", (0.7, 0.62, 0.45), 0.9),
    "kraft": P("paper_kraft", (0.45, 0.3, 0.16), 0.9),
}
SPINES = [(0.33, 0.06, 0.07), (0.07, 0.1, 0.22), (0.5, 0.33, 0.08), (0.08, 0.2, 0.1), (0.42, 0.3, 0.17), (0.6, 0.55, 0.42),
          (0.22, 0.12, 0.07), (0.22, 0.04, 0.06), (0.17, 0.2, 0.24), (0.15, 0.14, 0.07), (0.05, 0.05, 0.05)]
BOOKMATS = [lib.grimy(f"spine_{i}", c, tuple(v * 0.5 for v in c), rough=(0.55, 0.8), amount=0.25, scale=6, bump=0.1) for i, c in enumerate(SPINES)]
GILT = P("gilt", (0.55, 0.4, 0.12), 0.4, metal=1.0)

# pegboard: hardboard with a regular hole grid
pm = bpy.data.materials.new("pegboard")
nt = pm.node_tree
bs = nt.nodes["Principled BSDF"]
tc = nt.nodes.new("ShaderNodeTexCoord")
vo = nt.nodes.new("ShaderNodeTexVoronoi")
vo.inputs["Scale"].default_value = 30
vo.inputs["Randomness"].default_value = 0.0
nt.links.new(tc.outputs["Object"], vo.inputs["Vector"])
hole = lib._ramp(nt, vo.outputs["Distance"], [(0.12, (0.012, 0.008, 0.006)), (0.16, (0.2, 0.14, 0.08))])
nt.links.new(hole.outputs["Color"], bs.inputs["Base Color"])
bs.inputs["Roughness"].default_value = 0.8
M["pegboard"] = pm

C_SHELL, C_ST, C_FURN, C_SHELF, C_CEIL = (collection(n) for n in ("shell", "storefront", "furniture", "shelving", "ceiling"))

# ---------------------------------------------------------------- floor, ceiling, walls
PLANK = 0.16
n_planks = int(W / PLANK) + 2
for i in range(n_planks):  # boards run along y; tops stay at z<=0 (some sink a little), gaps are dark
    x0 = -0.02 + i * PLANK
    sink = random.choice((0, 0, 0.0015, 0.003))
    box(f"floor_plank_{i:02d}", (x0 + 0.002, -0.2, -0.04), (x0 + PLANK - 0.002, D + 0.05, -sink), M["floor"], C_SHELL, bevel=0.0012)
box("floor_base", (-T, -0.5, -0.1), (W + T, D + T, -0.04), P("floor_dark", (0.02, 0.015, 0.01), 0.9), C_SHELL, bevel=0)
box("ceiling_slab", (-T, -T, H), (W + T, D + T, H + 0.1), M["ceiling"], C_CEIL, bevel=0)
for i, y in enumerate((1.3, 3.0)):
    box(f"ceiling_beam_{i + 1}", (0, y - 0.08, H - 0.2), (W, y + 0.08, H), M["beam"], C_CEIL, bevel=0.004)
box("wall_left", (-T, -T, 0), (0, D + T, H), M["wall"], C_SHELL, bevel=0)
box("wall_right", (W, -T, 0), (W + T, D + T, H), M["wall"], C_SHELL, bevel=0)
box("wall_back", (-T, D, 0), (W + T, D + T, H), M["wall"], C_SHELL, bevel=0)

# street wall (y=0) with door (x 2.0..2.9) and a small shop window (x 0.5..1.5, z 0.95..1.9)
DX0, DX1, DH = 2.0, 2.9, 2.05
WX0, WX1, WZ0, WZ1 = 0.5, 1.5, 0.95, 1.9
yw0, yw1 = -T, 0.0
for name, lo, hi in (
    ("wall_street_a", (-T, yw0, 0), (WX0, yw1, H)),
    ("wall_street_b", (WX1, yw0, 0), (DX0, yw1, H)),
    ("wall_street_c", (DX1, yw0, 0), (W + T, yw1, H)),
    ("wall_street_door_top", (DX0, yw0, DH), (DX1, yw1, H)),
    ("wall_street_window_sill", (WX0, yw0, 0), (WX1, yw1, WZ0)),
    ("wall_street_window_top", (WX0, yw0, WZ1), (WX1, yw1, H)),
):
    box(name, lo, hi, M["wall"], C_SHELL, bevel=0)
for name, lo, hi in (("baseboard_left", (0, 0, 0), (0.015, D, 0.1)), ("baseboard_right", (W - 0.015, 0, 0), (W, D, 0.1)),
                     ("baseboard_back", (0, D - 0.015, 0), (W, D, 0.1)), ("baseboard_street", (0, 0, 0), (DX0, 0.015, 0.1))):
    box(name, lo, hi, M["trim"], C_SHELL)

# window: frame + real glass panes (bevelled thin boxes) + sill + sign
ty = -0.12
for name, lo, hi in (("window_frame_bottom", (WX0, ty - 0.04, WZ0), (WX1, ty + 0.12, WZ0 + 0.05)),
                     ("window_frame_top", (WX0, ty - 0.04, WZ1 - 0.05), (WX1, ty + 0.12, WZ1)),
                     ("window_frame_left", (WX0, ty - 0.04, WZ0), (WX0 + 0.05, ty + 0.12, WZ1)),
                     ("window_frame_right", (WX1 - 0.05, ty - 0.04, WZ0), (WX1, ty + 0.12, WZ1)),
                     ("window_mullion", (0.99, ty - 0.01, WZ0), (1.01, ty + 0.09, WZ1))):
    box(name, lo, hi, M["trim"], C_ST)
for k, (gx0, gx1) in enumerate(((WX0 + 0.05, 0.99), (1.01, WX1 - 0.05))):
    box(f"window_glass_{k}", (gx0, ty + 0.02, WZ0 + 0.05), (gx1, ty + 0.032, WZ1 - 0.05), M["glass"], C_ST, bevel=0.0015)
box("window_sill_inner", (WX0 - 0.03, 0.0, WZ0 - 0.03), (WX1 + 0.03, 0.06, WZ0), M["trim"], C_ST)

# door: frame, leaf with a glazed upper panel, brass handle
for name, lo, hi in (("door_frame_l", (DX0, -T, 0), (DX0 + 0.05, 0.02, DH)), ("door_frame_r", (DX1 - 0.05, -T, 0), (DX1, 0.02, DH)),
                     ("door_frame_t", (DX0, -T, DH - 0.05), (DX1, 0.02, DH))):
    box(name, lo, hi, M["trim"], C_ST)
ly0, ly1 = -0.12, -0.075
for name, lo, hi in (("door_leaf_lower", (DX0 + 0.05, ly0, 0.01), (DX1 - 0.05, ly1, 1.15)),
                     ("door_leaf_stile_l", (DX0 + 0.05, ly0, 1.15), (DX0 + 0.17, ly1, DH - 0.05)),
                     ("door_leaf_stile_r", (DX1 - 0.17, ly0, 1.15), (DX1 - 0.05, ly1, DH - 0.05)),
                     ("door_leaf_rail_top", (DX0 + 0.17, ly0, 1.88), (DX1 - 0.17, ly1, DH - 0.05))):
    box(name, lo, hi, M["door"], C_ST)
box("door_leaf_glass", (DX0 + 0.17, ly0 + 0.014, 1.15), (DX1 - 0.17, ly0 + 0.026, 1.88), M["doorglass"], C_ST, bevel=0.0015)
cylinder("door_handle", (DX1 - 0.1, ly1 + 0.04, 1.0), 0.012, 0.1, M["brass"], C_ST, axis="X")

# window sign (reads from the street, glows warm)
sm = bpy.data.materials.new("sign_glow")
sb = sm.node_tree.nodes["Principled BSDF"]
sb.inputs["Base Color"].default_value = (0.9, 0.55, 0.2, 1)
sb.inputs["Emission Color"].default_value = (1.0, 0.5, 0.15, 1)
sb.inputs["Emission Strength"].default_value = 12.0
lib.set_emission_sampling_none(sm)
cv = bpy.data.curves.new("window_sign_text", "FONT")
cv.body = "ENCADERNADOR"
cv.size = 0.085
cv.extrude = 0.003
cv.align_x = "CENTER"
so = bpy.data.objects.new("window_sign", cv)
so.data.materials.append(sm)
C_ST.objects.link(so)
so.rotation_euler = (math.pi / 2, 0, 0)  # faces the street (-Y); from inside you see its back
so.location = (1.0, ty + 0.006, 1.72)
for i, x in enumerate((0.7, 1.3)):  # sign chains
    box(f"window_sign_chain_{i}", (x, ty, 1.77), (x + 0.003, ty + 0.004, WZ1 - 0.05), M["brass"], C_ST, bevel=0)

# street outside: wet pavement + dark backdrop with bokeh lights (seen through the glass, not a diffuse light)
box("pavement", (-4, -4.0, -0.3), (8, -T, 0.0), P("wet_pavement", (0.04, 0.04, 0.045), 0.15), C_SHELL, bevel=0)
bd = plane("street_backdrop", (1.6, -4.0, 1.6), 12, 5, "Y", None, C_SHELL)
bm_ = bpy.data.materials.new("street_backdrop_mat")
bnt = bm_.node_tree
bb = bnt.nodes["Principled BSDF"]
bb.inputs["Base Color"].default_value = (0.01, 0.015, 0.03, 1)
tco = bnt.nodes.new("ShaderNodeTexCoord")
vor = bnt.nodes.new("ShaderNodeTexVoronoi")
vor.inputs["Scale"].default_value = 9
bnt.links.new(tco.outputs["UV"], vor.inputs["Vector"])
rmp = lib._ramp(bnt, vor.outputs["Distance"], [(0.0, (1.0, 0.6, 0.3)), (0.07, (0.01, 0.015, 0.03))])
bnt.links.new(rmp.outputs["Color"], bb.inputs["Emission Color"])
bb.inputs["Emission Strength"].default_value = 3.0
bd.data.materials.append(bm_)
lib.set_emission_sampling_none(bm_)

# ---------------------------------------------------------------- shelf wall (x 0..0.34), books and paper rolls
SD = 0.34
LEVELS = [0.10, 0.48, 0.86, 1.24, 1.62, 2.0, 2.38]  # board centres
UPR = [0.0, 0.93, 1.86, 2.79, 3.72]  # y of upright centres
BT = 0.025
box("shelf_back_panel", (0.0, 0.0, 0.0), (0.015, D, H), M["shelfwood"], C_SHELF, bevel=0)
for i, y in enumerate(UPR):
    box(f"shelf_upright_{i}", (0.015, max(0.0, y - 0.02), 0.0), (SD, min(D, y + 0.02), 2.42), M["shelfwood"], C_SHELF)
for i, z in enumerate(LEVELS):
    box(f"shelf_board_{i}", (0.015, 0.0, z - BT / 2), (SD, D - 0.02, z + BT / 2), M["shelfwood"], C_SHELF)
box("shelf_plinth", (0.015, 0.0, 0.0), (SD, D, 0.09), M["shelfwood"], C_SHELF)
box("shelf_cornice", (0.0, 0.0, 2.42), (SD + 0.04, D, 2.48), M["shelfwood"], C_SHELF)
RADIO_GAP = (2.2, 2.55)  # level 3 (board z 1.24), bay 2: y range kept free for the old_radio

bmB, bmG, bm_paper, bm_kraft = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
nbooks = 0


def set_mat(verts, mi):
    for f in {f for v in verts for f in v.link_faces}:
        f.material_index = mi


def book(lo_y, w, shelf_top, hmax):
    """One standing book on a shelf; spine toward +X. Returns the y after it."""
    global nbooks
    h = random.uniform(0.17, hmax)
    dpt = random.uniform(0.17, 0.26)
    x1 = random.choice((0.30, 0.30, 0.31, 0.285))
    set_mat(add_box(bmB, (x1 - dpt, lo_y, shelf_top), (x1, lo_y + w, shelf_top + h)), random.randrange(len(BOOKMATS)))
    if random.random() < 0.4:  # gilt band across the spine
        bz = shelf_top + h * random.uniform(0.55, 0.85)
        add_box(bmG, (x1, lo_y + 0.002, bz), (x1 + 0.0015, lo_y + w - 0.002, bz + 0.012))
    nbooks += 1
    return lo_y + w


def run(y, yend, top, hmax):
    while y < yend - 0.03:
        if random.random() < 0.06:
            y += random.uniform(0.04, 0.1)
            continue
        w = random.uniform(0.022, 0.06)
        if y + w > yend:
            break
        y = book(y, w, top, hmax)
    return y


for bay in range(4):
    ya, yb = UPR[bay] + 0.03, UPR[bay + 1] - 0.03
    for lv in range(6):  # compartment above board lv
        top = LEVELS[lv] + BT / 2
        hmax = LEVELS[lv + 1] - BT / 2 - top - 0.03
        if lv == 0 and bay in (0, 2):  # standing paper rolls
            y = ya + 0.06
            while y < yb - 0.06:
                r = random.uniform(0.032, 0.05)
                add_cyl(random.choice((bm_paper, bm_kraft)), (0.12 + random.uniform(0, 0.12), y, top + hmax * 0.45), r, hmax * 0.9, "Z", 16)
                y += r * 2 + 0.005
            continue
        y = ya
        if lv == 5 and bay == 1:  # lying rolls, ends toward the room
            for k in range(3):
                for j in range(2 if k < 2 else 1):
                    add_cyl(random.choice((bm_paper, bm_kraft)), (0.18, ya + 0.08 + j * 0.1 + k * 0.012, top + 0.046 + k * 0.095), 0.046, 0.26, "X", 18)
            y = ya + 0.38
        if lv == 3 and bay == 2:
            y = run(y, RADIO_GAP[0] - 0.03, top, hmax)
            run(RADIO_GAP[1] + 0.03, yb, top, hmax)
            continue
        y = run(y, ya + (yb - ya) * random.uniform(0.72, 1.0), top, hmax)
        if yb - y > 0.14 and random.random() < 0.6:  # a couple of leaning books
            for k in range(2):
                yy = y + 0.04 + k * 0.045
                set_mat(add_box(bmB, (0.1, yy, top), (0.3, yy + 0.033, top + hmax * 0.92), lean=-0.22 - 0.05 * k, pivot=(0.2, yy, top)),
                        random.randrange(len(BOOKMATS)))
ob = mesh_obj("shelf_books", bmB, None, C_SHELF, 0.0015)
for m in BOOKMATS:
    ob.data.materials.append(m)
mesh_obj("shelf_book_gilt", bmG, GILT, C_SHELF, 0)
mesh_obj("shelf_paper_rolls", bm_paper, M["paper"], C_SHELF, 0)
mesh_obj("shelf_kraft_rolls", bm_kraft, M["kraft"], C_SHELF, 0)

# ---------------------------------------------------------------- heavy work table 1.8 x 0.9 x 0.9
TX0, TX1, TY0, TY1, TZ = 1.2, 2.1, 1.1, 2.9, 0.9
box("work_table_top", (TX0, TY0, TZ - 0.07), (TX1, TY1, TZ), M["tablewood"], C_FURN, bevel=0.004)
for i, (lx, ly) in enumerate(((TX0 + 0.06, TY0 + 0.06), (TX1 - 0.06, TY0 + 0.06), (TX0 + 0.06, TY1 - 0.06), (TX1 - 0.06, TY1 - 0.06))):
    box(f"work_table_leg_{i}", (lx - 0.05, ly - 0.05, 0), (lx + 0.05, ly + 0.05, TZ - 0.07), M["tablewood"], C_FURN, bevel=0.003)
box("work_table_apron_a", (TX0 + 0.11, TY0 + 0.03, TZ - 0.2), (TX1 - 0.11, TY0 + 0.06, TZ - 0.07), M["tablewood"], C_FURN)
box("work_table_apron_b", (TX0 + 0.11, TY1 - 0.06, TZ - 0.2), (TX1 - 0.11, TY1 - 0.03, TZ - 0.07), M["tablewood"], C_FURN)
box("work_table_stretcher_l", (TX0 + 0.04, TY0 + 0.11, 0.2), (TX0 + 0.07, TY1 - 0.11, 0.26), M["tablewood"], C_FURN)
box("work_table_stretcher_r", (TX1 - 0.07, TY0 + 0.11, 0.2), (TX1 - 0.04, TY1 - 0.11, 0.26), M["tablewood"], C_FURN)
box("work_table_lowshelf", (TX0 + 0.07, TY0 + 0.08, 0.2), (TX1 - 0.07, TY1 - 0.08, 0.225), M["tablewood"], C_FURN)

# ---------------------------------------------------------------- counter (right wall, by the door)
box("counter_body", (2.62, 0.85, 0), (W, 1.85, 0.92), M["shelfwood"], C_FURN, bevel=0.004)
box("counter_top", (2.58, 0.82, 0.92), (W, 1.88, 0.95), M["tablewood"], C_FURN, bevel=0.004)
for i in range(2):
    box(f"counter_panel_{i}", (2.6, 0.9 + i * 0.5, 0.1), (2.62, 1.3 + i * 0.5, 0.82), M["trim"], C_FURN, bevel=0.002)

# ---------------------------------------------------------------- window display shelf with a few books
box("window_display_shelf", (0.55, 0.02, 0.94), (1.45, 0.3, 0.965), M["shelfwood"], C_FURN)
for i, x in enumerate((0.62, 1.38)):
    box(f"window_display_bracket_{i}", (x - 0.01, 0.0, 0.8), (x + 0.01, 0.26, 0.94), M["brass"], C_FURN)
bmD = bmesh.new()
ZT = 0.965
for k, (x, w, h, yaw, lean) in enumerate(((0.62, 0.04, 0.2, 0, 0), (0.66, 0.035, 0.24, 0, 0), (0.7, 0.045, 0.19, 0, 0.3),
                                          (1.28, 0.04, 0.21, 0, 0), (1.32, 0.04, 0.17, 0, 0))):
    vs = add_box(bmD, (x, 0.1, ZT), (x + w, 0.1 + 0.15, ZT + h), lean=lean, pivot=(x, 0.17, ZT))
    set_mat(vs, (k * 3 + 1) % len(BOOKMATS))
set_mat(add_box(bmD, (0.9, 0.08, ZT), (1.12, 0.23, ZT + 0.03), yaw=0.15), 2)  # two books lying flat, a third on top
set_mat(add_box(bmD, (0.92, 0.09, ZT + 0.03), (1.1, 0.22, ZT + 0.055), yaw=-0.1), 6)
set_mat(add_box(bmD, (0.95, 0.1, ZT + 0.055), (1.08, 0.2, ZT + 0.08), yaw=0.2), 0)
ob = mesh_obj("window_display_books", bmD, None, C_FURN, 0.0015)
for m in BOOKMATS:
    ob.data.materials.append(m)

# ---------------------------------------------------------------- tool wall (pegboard) at the back
PX0, PX1, PZ0, PZ1 = 0.45, 1.3, 0.95, 1.95
box("tool_wall_pegboard", (PX0, D - 0.014, PZ0), (PX1, D - 0.002, PZ1), M["pegboard"], C_FURN, bevel=0)
box("tool_wall_ledge", (PX0, D - 0.09, PZ0 - 0.03), (PX1, D - 0.014, PZ0), M["shelfwood"], C_FURN)
bmW, bmS, bmT = bmesh.new(), bmesh.new(), bmesh.new()  # wooden handles, steel, leather
Z = D - 0.014


def hammer(x, z):
    add_box(bmW, (x - 0.012, Z - 0.026, z - 0.12), (x + 0.012, Z - 0.012, z + 0.1))
    add_box(bmS, (x - 0.045, Z - 0.036, z + 0.08), (x + 0.045, Z - 0.012, z + 0.115))


def slim(x, z, length, bm, w=0.015):
    add_box(bm, (x - w / 2, Z - 0.012, z - length / 2), (x + w / 2, Z - 0.006, z + length / 2))


hammer(0.58, 1.78)
hammer(0.7, 1.74)
add_box(bmS, (0.86, Z - 0.012, 1.8), (1.1, Z - 0.008, 1.9))  # saw blade
add_box(bmW, (1.08, Z - 0.03, 1.79), (1.15, Z - 0.008, 1.91))
slim(1.22, 1.7, 0.4, bmS)
slim(0.52, 1.35, 0.3, bmW, 0.02)
slim(0.64, 1.38, 0.24, bmW, 0.02)
for x in (0.78, 0.86, 0.94, 1.02):  # awls / chisels
    add_box(bmW, (x - 0.01, Z - 0.03, 1.42), (x + 0.01, Z - 0.012, 1.55))
    add_box(bmS, (x - 0.003, Z - 0.026, 1.55), (x + 0.003, Z - 0.02, 1.7))
add_box(bmS, (1.157, Z - 0.012, 1.42), (1.169, Z - 0.006, 1.6))  # scissors blades + handles
add_box(bmT, (1.12, Z - 0.02, 1.34), (1.2, Z - 0.012, 1.42))
add_box(bmT, (0.55, Z - 0.03, 1.05), (0.85, Z - 0.012, 1.12))  # leather strop
mesh_obj("tool_wall_wood_handles", bmW, M["shelfwood"], C_FURN, 0.001)
mesh_obj("tool_wall_steel", bmS, M["steel"], C_FURN, 0.0008)
mesh_obj("tool_wall_leather", bmT, P("strop_leather", (0.12, 0.06, 0.03), 0.6), C_FURN, 0)

# ---------------------------------------------------------------- back-right cabinet for the paper cutter; dim bulb at the back
box("back_cabinet", (2.2, 3.45, 0), (3.15, 3.97, 0.78), M["shelfwood"], C_FURN, bevel=0.004)
box("back_cabinet_top", (2.17, 3.42, 0.78), (3.17, 3.98, 0.81), M["tablewood"], C_FURN, bevel=0.004)
bm_bulb = bpy.data.materials.new("back_bulb_glow")
bp = bm_bulb.node_tree.nodes["Principled BSDF"]
bp.inputs["Emission Color"].default_value = (1.0, 0.65, 0.3, 1)
bp.inputs["Emission Strength"].default_value = 25.0
lib.set_emission_sampling_none(bm_bulb)
bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=0.035, location=(1.9, 3.3, 2.12))
bo = bpy.context.object
bo.name = "back_bulb"
bo.data.materials.append(bm_bulb)
lib.link(bo, C_FURN)
cylinder("back_bulb_cord", (1.9, 3.3, 2.38), 0.004, 0.44, P("cord_black", (0.01, 0.01, 0.01), 0.5), C_FURN)
cylinder("back_bulb_socket", (1.9, 3.3, 2.17), 0.017, 0.05, M["brass"], C_FURN)

for o in bpy.data.objects:  # glass must not cast shadows (refractive caustics are off)
    if "glass" in o.name:
        o.visible_shadow = False

os.makedirs(SCN, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SCN, "shell.blend"))
print("saved shell", len(bpy.data.objects), "objects,", nbooks, "books")
