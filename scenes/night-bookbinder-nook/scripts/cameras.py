"""Three hero stills (2.39:1) for the nook.

blender -b <lit.blend> --python scenes/night-bookbinder-nook/scripts/cameras.py -- <out.blend>
cam_door : from the door looking down the room toward the press, 24 mm
cam_table: over the work table, close, 50 mm, focus on the sewing frame
cam_low  : 30 cm off the floor along the table legs and the stool, 30 mm (floating-prop check)
"""
import math
import os
import sys

import bpy
from mathutils import Vector

out = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = 1920, 804  # 2.39:1


def obj_pos(name, dz=0.0, default=(0, 0, 0)):
    o = sc.objects.get(name)
    if not o:
        return Vector(default)
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector((sum(p.x for p in pts) / 8, sum(p.y for p in pts) / 8, sum(p.z for p in pts) / 8 + dz))


def empty(name, loc):
    e = bpy.data.objects.get(name) or bpy.data.objects.new(name, None)
    if e.name not in sc.collection.objects:
        sc.collection.objects.link(e)
    e.location = loc
    return e


def camera(name, loc, target, lens, focus, fstop):
    cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36
    cd.sensor_fit = "HORIZONTAL"
    cd.clip_start = 0.05
    cam = bpy.data.objects.get(name) or bpy.data.objects.new(name, cd)
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_mode = "XYZ"
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cd.dof.use_dof = True
    cd.dof.focus_object = empty(f"focus_{name}", focus)
    cd.dof.aperture_fstop = fstop
    return cam


press = obj_pos("bk_book_press", 0.0, (1.75, 3.45, 0.55))
frame = obj_pos("bk_sewing_frame", 0.0, (1.62, 1.75, 1.15))

door = camera("cam_door", (2.45, 0.32, 1.55), (1.85, 3.5, 0.95), 24, press, 5.6)
table = camera("cam_table", (2.05, 0.5, 1.7), frame + Vector((0, 0, 0.0)), 50, frame, 2.8)
low = camera("cam_low", (0.95, 0.4, 0.30), (2.05, 1.7, 0.33), 30, (2.4, 1.65, 0.3), 4.0)
sc.camera = door
bpy.ops.wm.save_as_mainfile(filepath=out)
print("cameras ->", out)
