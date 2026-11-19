# night-bookbinder-nook notes (one line per gotcha)

- Build: `scenes/night-bookbinder-nook/build.sh [--skip-prep]` -> shell.blend, dressed.blend, lit.blend, scene.blend. Props missing = named placeholder boxes `bk_<id>` (custom prop `placeholder=1`); re-run build after prep.
- Placed props are named `bk_<id>` so `pipeline/grounding.py --prefix bk_` checks only them (the shell's table top, shelf boards etc. otherwise show up as "floating" parts).
- `bash` heredocs with many quotes/parentheses died on this Windows Git Bash; write scripts with the Write tool instead.
- Drop rays take the highest hit under 5 footprint points: a prop half on a sheet of paper perches at paper height, and a stool near the counter climbs onto it. Floor props use `"single": True` (centre ray only); other props' meshes are skipped as supports (only `support` extras like mats and paper count).
- Clash resolver must test against furniture too (shelf books), with the prop lifted 3 mm; build the furniture BVHs once (shelf_books is one 300-book mesh).
- Books are baked into one mesh with 11 spine materials (`material_index` per face) plus a gilt-band mesh; a mesh per book made the shell slow.
- `ob.color` variation needs Object Info > Color multiplied into Base Color: dress.py patches every source material once (`tinted` flag); generated GLB materials otherwise ignore it.
- Placed library props: glTF objects are QUATERNION; dress sets `rotation_mode = "XYZ"` before `rotation_euler`.
- Lights: Blender spot/point watts are large; 100 W-class values blow out a 3 m room. Pendant spot 120 W, desk spot 45 W, exposure +0.7 AgX gave a readable night at 16-24 spp CPU. Re-tune with real props (shiny brass/glass change a lot): `NOOK_EXPOSURE` env var sets exposure in lights.py.
- Pegboard hole grid is a zero-randomness Voronoi: fine in stills, will moire at distance if the scale is raised.
- Window glass needs `visible_shadow = False` (refractive caustics are off), and the glass is a thin bevelled box, not a plane.
- `Material.use_nodes` is deprecated in 5.x: test `mat.node_tree` instead.
- Pixal3D: prep runs `scripts/blender/canonicalize.py` in a child Blender (`bpy.app.binary_path`), `--ref` = trellis2 GLB of the same id if present; output in props/_canon/. Tested only on a synthetic tilted GLB (30 deg recovered).
- render_stills.py `--gpu` runs gpu_prefs.py via runpy before anything else; without it the render is CPU (OIDN denoise).
