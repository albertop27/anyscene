#!/usr/bin/env bash
# Build the nook end to end: prep -> shell -> dress -> validate -> lights -> cameras -> scene.blend
# usage: scenes/night-bookbinder-nook/build.sh [--skip-prep] [--hand | --from-layout]   (set BLENDER to override)
#   --hand         stop after dress + validate: copy dressed.blend to layout.blend (never overwrites an existing one) for the
#                  owner to move, add or delete props in Blender. Save it, then run --from-layout.
#   --from-layout  skip prep/shell/dress. Check layout.blend (FLOAT, SUNK, CLIP, FURNITURE, OUT, SCALE, new props, grounding;
#                  report in out/layout/check.json), then light it, add cameras and render Eevee check stills to out/layout/.
#                  It reports problems and goes on; it never moves the owner's props.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
B="${BLENDER:-/c/Program Files/Blender Foundation/Blender 5.3/blender.exe}"
S="$HERE/scripts"
WHERE="$(cygpath -m "$HERE" 2>/dev/null || echo "$HERE")"   # a path Blender can open (Git Bash gives /c/...)
MODE=""; PREP=1
for a in "$@"; do
  case "$a" in --skip-prep) PREP=0 ;; --hand|--from-layout) MODE="$a" ;; *) echo "unknown option $a"; exit 2 ;; esac
done
FILTER="FLOAT|SUNK|CLIP|FURNITURE|OUT|SCALE|NEW|VALIDATE|grounding|Error|Traceback"

if [ "$MODE" = "--from-layout" ]; then
  L="$HERE/layout.blend"
  [ -f "$L" ] || { echo "no layout.blend: run build.sh --hand first"; exit 1; }
  mkdir -p "$HERE/out/layout"
  "$B" -b "$L" -P "$S/validate.py" -- --layout --report "$HERE/out/layout/check.json" | grep -E "$FILTER" || true
  "$B" -b "$L" -P "$S/lights.py" -- "$HERE/lit_layout.blend" | grep -E "lit ->|Error|Traceback"
  "$B" -b "$HERE/lit_layout.blend" -P "$S/cameras.py" -- "$HERE/scene_layout.blend" | grep -E "cameras ->|Error|Traceback"
  "$B" -b "$HERE/scene_layout.blend" -P "$S/render_stills.py" -- --out "$HERE/out/layout" --eevee --width 1280 \
    | grep -E "rendered|Error|Traceback"
  echo "built $HERE/scene_layout.blend; check report and stills in $HERE/out/layout"
  exit 0
fi

if [ "$PREP" = 1 ]; then
  "$B" -b --factory-startup -P "$S/prep.py" | grep -E "PREP|Error|Traceback" || true   # skips props whose GLB is missing
fi
"$B" -b --factory-startup -P "$S/build_shell.py" | grep -E "saved|Error|Traceback"
"$B" -b "$HERE/shell.blend" -P "$S/dress.py" | grep -E "PLACEHOLDER|SKIPPED|UNRESOLVED|saved|Error|Traceback"
"$B" -b "$HERE/dressed.blend" -P "$S/validate.py" | grep -E "$FILTER"
if [ "$MODE" = "--hand" ]; then
  if [ -f "$HERE/layout.blend" ]; then
    echo "layout.blend already exists: left as it is (delete it yourself to start over from dressed.blend)"
  else
    # tag everything the build made, so the check can tell the owner's new objects from build parts
    "$B" -b "$HERE/dressed.blend" --python-expr "import bpy
for o in bpy.data.objects: o['built'] = True
bpy.ops.wm.save_as_mainfile(filepath=r'$WHERE/layout.blend', copy=True)" | grep -E "Error|Traceback" || true
    echo "layout.blend ready: open it in Blender, move/add/delete props and save,"
    echo "then run: build.sh --from-layout"
  fi
  exit 0
fi
"$B" -b "$HERE/dressed.blend" -P "$S/lights.py" -- "$HERE/lit.blend" | grep -E "lit ->|Error|Traceback"
"$B" -b "$HERE/lit.blend" -P "$S/cameras.py" -- "$HERE/scene.blend" | grep -E "cameras ->|Error|Traceback"
echo "built $HERE/scene.blend"
