"""Render the hero stills with Cycles.

blender -b scenes/night-bookbinder-nook/scene.blend --python scenes/night-bookbinder-nook/scripts/render_stills.py -- \
    --out <abs dir> [--width 1920] [--spp 64] [--cams cam_door,cam_table,cam_low] [--gpu] [--eevee] [--exposure 0.5] [--tag name]
--eevee: quick check renders with Eevee (GPU, no samples setting). --gpu loads gpu_prefs.py (OptiX) first; without it everything renders on the CPU. Output: <out>/<tag><cam>.png, 2.39:1.
"""
import os
import runpy
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
here = os.path.dirname(os.path.abspath(__file__))
if "--gpu" in argv:
    runpy.run_path(os.path.join(here, "gpu_prefs.py"))
out = os.path.abspath(opt("--out", os.path.join(here, "..", "out")))
os.makedirs(out, exist_ok=True)
width = int(opt("--width", 1920))
sc = bpy.context.scene
if "--eevee" in argv:
    ids = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in ids else "BLENDER_EEVEE"
else:
    sc.render.engine = "CYCLES"
sc.render.resolution_x, sc.render.resolution_y = width, round(width / 2.39)
sc.render.resolution_percentage = 100
sc.cycles.samples = int(opt("--spp", 64))  # ignored by Eevee
sc.cycles.use_denoising = True
sc.cycles.denoiser = "OPTIX" if "--gpu" in argv else "OPENIMAGEDENOISE"
if "--gpu" not in argv:
    sc.cycles.device = "CPU"
if opt("--exposure"):
    sc.view_settings.exposure = float(opt("--exposure"))
sc.render.image_settings.file_format = "PNG"
tag = opt("--tag", "")
for name in opt("--cams", "cam_door,cam_table,cam_low").split(","):
    cam = bpy.data.objects[name]
    sc.camera = cam
    sc.render.filepath = os.path.join(out, f"{tag}{name}.png")
    bpy.ops.render.render(write_still=True)
    print("rendered", sc.render.filepath)
