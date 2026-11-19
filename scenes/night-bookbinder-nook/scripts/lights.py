"""Night practicals, haze and render settings for the nook.

blender -b <dressed.blend> --python scenes/night-bookbinder-nook/scripts/lights.py -- <out.blend>
Practicals: brass pendant over the table (spot just under the rim, ~2700 K), desk lamp (spot under its shade), warm window-sign
glow, cool street spill through the glass (~6500 K, low), a dim bulb at the back. Weak fills only, hidden from camera/glossy/
transmission. Idempotent: rebuilds collection "night_rig".
"""
import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
import lib  # noqa: E402
from lib import W, D, H  # noqa: E402

out = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
sc = bpy.context.scene

old = bpy.data.collections.get("night_rig")
if old:
    for o in list(old.objects):
        bpy.data.objects.remove(o)
    bpy.data.collections.remove(old)
rig = bpy.data.collections.new("night_rig")
sc.collection.children.link(rig)


def kelvin(k):
    """Approximate blackbody RGB (Tanner Helland fit)."""
    t = k / 100.0
    r = 255 if t <= 66 else 329.698727446 * ((t - 60) ** -0.1332047592)
    g = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * ((t - 60) ** -0.0755148492)
    b = 255 if t >= 66 else (0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307)
    c = lambda v: max(0.0, min(255.0, v)) / 255.0
    return (c(r), c(g), c(b))


def light(name, kind, loc, energy, k, target=None, **kw):
    d = bpy.data.lights.new(name, kind)
    d.energy = energy
    d.color = kelvin(k)
    for a, v in kw.items():
        setattr(d, a, v)
    o = bpy.data.objects.new(name, d)
    rig.objects.link(o)
    o.location = loc
    o.visible_camera = o.visible_glossy = o.visible_transmission = False  # a light, not a bright disc in the glass
    if target is not None:  # lights shine along local -Z
        o.rotation_mode = "XYZ"
        o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return o


def verts(ob):
    return [ob.matrix_world @ v.co for v in ob.data.vertices]


# --- world: almost black, a hint of blue
w = sc.world or bpy.data.worlds.new("night")
sc.world = w
bg = w.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.004, 0.006, 0.012, 1)
bg.inputs["Strength"].default_value = 1.0
bd = sc.objects.get("street_backdrop")
if bd:  # visible through the glass, but must not flood the room with diffuse light
    bd.visible_diffuse = False
    bd.visible_volume_scatter = False

# --- brass pendant over the table: spot just under the rim (shade is a closed mesh), plus a tiny glow
pend = sc.objects.get("bk_pendant_lamp")
pc = Vector((1.65, 2.0, 1.85))
if pend:
    vs = verts(pend)
    zmin = min(v.z for v in vs)
    low = [v for v in vs if v.z < zmin + 0.02]
    pc = Vector((sum(v.x for v in low) / len(low), sum(v.y for v in low) / len(low), zmin))
light("pendant_spot", "SPOT", pc + Vector((0, 0, -0.01)), 120, 2700, pc - Vector((0, 0, 1.0)), spot_size=math.radians(105), spot_blend=0.6, shadow_soft_size=0.04)
light("pendant_glow", "POINT", pc + Vector((0, 0, 0.06)), 4, 2700, shadow_soft_size=0.04)

# --- desk lamp: warm spot under its shade, aimed at the sewing frame
lamp = sc.objects.get("bk_desk_lamp")
frame = sc.objects.get("bk_sewing_frame")
fc = (frame.matrix_world @ Vector((0, 0, 0.12))) if frame else Vector((1.62, 1.75, 1.0))
if lamp:
    vs = verts(lamp)
    zmin, zmax = min(v.z for v in vs), max(v.z for v in vs)
    top = [v for v in vs if v.z > zmin + 0.55 * (zmax - zmin)]  # the shade is the high end of the jointed arm
    rim = min(v.z for v in top)
    sx, sy = sum(v.x for v in top) / len(top), sum(v.y for v in top) / len(top)
    shade = Vector((sx, sy, rim - 0.01))
else:
    shade = Vector((1.9, 2.3, 1.2))
light("desk_lamp_spot", "SPOT", shade, 45, 2900, fc, spot_size=math.radians(70), spot_blend=0.5, shadow_soft_size=0.025)

# --- warm window-sign glow: a small area behind the sign (inside), spilling onto the display shelf and floor by the window
light("sign_glow", "AREA", (1.0, 0.12, 1.72), 12, 2200, (1.0, 1.2, 0.9), shape="RECTANGLE", size=0.7, size_y=0.12)

# --- cool street spill through the glass: low, a soft area outside the window aimed down the room
light("street_spill", "AREA", (1.0, -1.6, 1.3), 25, 6500, (1.3, 2.0, 0.5), shape="RECTANGLE", size=1.0, size_y=0.9)
light("streetlamp_rim", "SPOT", (0.2, -3.0, 3.5), 100, 6500, (1.0, 0.4, 0.8), spot_size=math.radians(35), spot_blend=0.8, shadow_soft_size=0.15)

# --- dim bulb at the back (matches the emissive bulb mesh in the shell)
light("back_bulb_light", "POINT", (1.9, 3.3, 2.12), 8, 2400, shadow_soft_size=0.04)

# --- weak fills (hidden from camera/glossy/transmission, set above): a faint bounce so the dark side reads
fill = light("fill_ceiling_bounce", "AREA", (1.6, 2.0, H - 0.05), 3, 3200, (1.6, 2.0, 0.0), shape="RECTANGLE", size=2.2, size_y=3.0)
fill.data.use_shadow = True

# --- haze: one volume box over the interior (cheap light shafts)
fog = bpy.data.meshes.new("haze")
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1)
bm.to_mesh(fog)
bm.free()
fo = bpy.data.objects.new("haze", fog)
rig.objects.link(fo)
fo.location = (W / 2, D / 2, H / 2)
fo.scale = (W - 0.02, D - 0.02, H - 0.02)
fm = bpy.data.materials.get("haze_vol") or bpy.data.materials.new("haze_vol")
nt = fm.node_tree
for n in list(nt.nodes):
    if n.type != "OUTPUT_MATERIAL":
        nt.nodes.remove(n)
pv = nt.nodes.new("ShaderNodeVolumePrincipled")
pv.inputs["Density"].default_value = 0.012
pv.inputs["Anisotropy"].default_value = 0.4
pv.inputs["Color"].default_value = (0.85, 0.85, 0.85, 1)
nt.links.new(pv.outputs["Volume"], nt.nodes["Material Output"].inputs["Volume"])
fo.data.materials.append(fm)
fo.visible_glossy = False

# --- dense emissive meshes must not become light samplers
for m in bpy.data.materials:
    if m.node_tree and any(n.type == "BSDF_PRINCIPLED" and n.inputs["Emission Strength"].default_value > 0 for n in m.node_tree.nodes):
        lib.set_emission_sampling_none(m)

# --- render settings
sc.render.engine = "CYCLES"
c = sc.cycles
c.samples = 128
c.device = "CPU"
c.use_denoising = True
c.volume_step_rate = 2.0
c.max_bounces = 8
c.caustics_reflective = False
c.caustics_refractive = False
c.blur_glossy = 1.0
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
sc.view_settings.exposure = float(os.environ.get("NOOK_EXPOSURE", "0.7"))
sc.render.fps = 24

bpy.ops.wm.save_as_mainfile(filepath=out)
print("lit ->", out)
