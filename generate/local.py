"""Local replacement for generate/fal.mjs (albertop27 fork of AnyScene, branch `local`). Same tool as AnyKit's fork.

Same file layout the kit tools expect, but everything runs on the local ComfyUI through the Art Design playground's
client (no FAL_KEY, no spend):

  ref  --out refs/kit/<id> --prompt "..." [--model krea2|qwen21] [--n 1] [--seed S] [--style-image path ...]
       -> refs/kit/<id>_0.png (.._n) + refs/kit/<id>.json
  3d   --ref refs/kit/<id>_0.png --id <id> [--models trellis2,pixal3d] [--seed S] [--faces 150000] [--texture 2048]
       -> assets/gen/<model>/<id>/model.glb + result.json

Re-running skips outputs that exist (--force to redo). Set PLAYGROUND to the playground root if this repo is not at
<playground>/vendor/anykit. Run with the playground venv: <playground>/.venv/Scripts/python.exe generate/local.py ...

--style-image: the playground has no image-edit model (owner's choice). The flag is accepted and recorded, but for
now style cohesion comes from the shared style paragraph in every prompt (KIT.md), which is what the gates check.
"""
import argparse
import json
import os
import random
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLAYGROUND = Path(os.environ.get("PLAYGROUND", REPO.parents[1]))
sys.path.insert(0, str(PLAYGROUND / "scripts"))
from comfy import client, graphs  # noqa: E402


def ref(a):
    out = (REPO / a.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    meta_path = out.with_suffix(".json") if out.suffix == "" else Path(str(out) + ".json")
    meta_path = Path(str(out) + ".json")
    if meta_path.exists() and not a.force:
        print(f"exists {meta_path.name} (skipped; --force to regenerate)")
        return
    seed = a.seed if a.seed is not None else random.randrange(2**40)
    files, t0 = [], time.time()
    stage = REPO / "generate" / "_stage"
    for i in range(a.n):
        build = graphs.krea2_t2i if a.model == "krea2" else graphs.qwen21_t2i
        g, meta = build(a.prompt, seed + i, prefix=f"anyscene_{out.name}")
        res = client.run(g, stage)
        src = stage / res["files"][0]
        dst = Path(f"{out}_{i}.png")
        shutil.move(str(src), dst)
        files.append(str(dst.relative_to(REPO)).replace("\\", "/"))
    meta_path.write_text(json.dumps({"endpoint": f"local/comfyui/{a.model}", "seconds": round(time.time() - t0, 1),
                                     "input": {"prompt": a.prompt, "seed": seed, "n": a.n,
                                               "style_images": a.style_image or []},
                                     "model": meta, "files": files}, indent=2), encoding="utf-8")
    print(f"saved {files} ({time.time() - t0:.0f} s)")


def three_d(a):
    image = (REPO / a.ref).resolve()
    client.ensure_server()
    name = client.upload_image(str(image))
    seed = a.seed if a.seed is not None else random.randrange(2**31)
    for model in a.models.split(","):
        out = REPO / "assets" / "gen" / model / a.id
        if (out / "model.glb").exists() and not a.force:
            print(f"exists {out.relative_to(REPO)}/model.glb (skipped)")
            continue
        out.mkdir(parents=True, exist_ok=True)
        g, meta = graphs.img2mesh(name, seed, use_trellis=(model == "trellis2"), texture_size=a.texture,
                                  faces=a.faces, prefix=f"anyscene_{a.id}_{model}")
        res = client.run(g, out / "_raw")
        glbs = [f for f in res["files"] if f.endswith(".glb")]
        shutil.move(str(out / "_raw" / glbs[0]), out / "model.glb")
        shutil.rmtree(out / "_raw", ignore_errors=True)
        (out / "result.json").write_text(json.dumps({"endpoint": f"local/comfyui/{model}", "seconds": res["seconds"],
                                                     "input": {"image": str(image), "seed": seed}, "model": meta},
                                                    indent=2), encoding="utf-8")
        print(f"saved {out.relative_to(REPO)}/model.glb ({res['seconds']:.0f} s)")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("ref")
    r.add_argument("--out", required=True)
    r.add_argument("--prompt", required=True)
    r.add_argument("--model", choices=["krea2", "qwen21"], default="krea2")
    r.add_argument("--n", type=int, default=1)
    r.add_argument("--seed", type=int)
    r.add_argument("--style-image", action="append")
    r.add_argument("--force", action="store_true")
    r.set_defaults(func=ref)
    t = sub.add_parser("3d")
    t.add_argument("--ref", required=True)
    t.add_argument("--id", required=True)
    t.add_argument("--models", default="trellis2,pixal3d")
    t.add_argument("--seed", type=int)
    t.add_argument("--faces", type=int, default=150000)
    t.add_argument("--texture", type=int, default=2048)
    t.add_argument("--force", action="store_true")
    t.set_defaults(func=three_d)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
