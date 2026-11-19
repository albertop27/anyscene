#!/usr/bin/env bash
# Build the nook end to end: prep -> shell -> dress -> validate -> lights -> cameras -> scene.blend
# usage: scenes/night-bookbinder-nook/build.sh [--skip-prep]   (run from anywhere; set BLENDER to override)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
B="${BLENDER:-/c/Program Files/Blender Foundation/Blender 5.3/blender.exe}"
S="$HERE/scripts"
if [ "${1:-}" != "--skip-prep" ]; then
  "$B" -b --factory-startup -P "$S/prep.py" | grep -E "PREP|Error|Traceback" || true   # skips props whose GLB is missing
fi
"$B" -b --factory-startup -P "$S/build_shell.py" | grep -E "saved|Error|Traceback"
"$B" -b "$HERE/shell.blend" -P "$S/dress.py" | grep -E "PLACEHOLDER|SKIPPED|UNRESOLVED|saved|Error|Traceback"
"$B" -b "$HERE/dressed.blend" -P "$S/validate.py" | grep -E "FLOAT|CLIP|FURNITURE|OUT|SCALE|VALIDATE|grounding|Error|Traceback"
"$B" -b "$HERE/dressed.blend" -P "$S/lights.py" -- "$HERE/lit.blend" | grep -E "lit ->|Error|Traceback"
"$B" -b "$HERE/lit.blend" -P "$S/cameras.py" -- "$HERE/scene.blend" | grep -E "cameras ->|Error|Traceback"
echo "built $HERE/scene.blend"
