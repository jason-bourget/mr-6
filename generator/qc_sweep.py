"""Run the art QC gate over every existing library image and report failures.

Usage:
    python generator/qc_sweep.py                 # check all, write failures file
    python generator/qc_sweep.py --limit 10      # spot-check

Writes failing problem ids (one per line) to generator/qc_failures.txt.
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import artkit

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"

parser = argparse.ArgumentParser()
parser.add_argument("--limit", type=int, default=0)
args = parser.parse_args()


def key_from_file(name):
    p = ROOT / name
    if p.exists():
        lines = p.read_text(encoding="utf-8").strip().splitlines()
        if lines:
            return lines[0].strip() or None
    return None


try:
    import anthropic
except ImportError:
    sys.exit("pip install anthropic")

_akey = os.environ.get("ANTHROPIC_API_KEY") or key_from_file("anthropic_apikey.txt")
client = anthropic.Anthropic(api_key=_akey) if _akey else anthropic.Anthropic()

manifest = json.loads((CONTENT / "manifest.json").read_text(encoding="utf-8"))
rels = manifest["problems"]
if args.limit:
    rels = rels[:args.limit]


def check(rel):
    p = json.loads((CONTENT / rel).read_text(encoding="utf-8"))
    img = CONTENT / p["image"]
    if not img.suffix == ".webp" or not img.exists():
        return (p["id"], False, ["no webp image"])
    ok, problems = artkit.qc_image(client, img.read_bytes())
    return (p["id"], ok, problems)


failures = []
checked = 0
with ThreadPoolExecutor(max_workers=4) as pool:
    futures = {pool.submit(check, rel): rel for rel in rels}
    for fut in as_completed(futures):
        try:
            pid, ok, problems = fut.result()
        except Exception as err:
            print(f"  [error] {futures[fut]}: {err}", flush=True)
            continue
        checked += 1
        if not ok:
            failures.append(pid)
            print(f"  [FAIL] {pid}: {'; '.join(problems)}", flush=True)
        elif checked % 20 == 0:
            print(f"  ...{checked} checked", flush=True)

out = Path(__file__).resolve().parent / "qc_failures.txt"
out.write_text("\n".join(sorted(failures)) + ("\n" if failures else ""), encoding="utf-8")
print(f"\n[done] {checked} checked, {len(failures)} failed -> {out.name}")
