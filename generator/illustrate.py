"""============================================================
Mr 6 — Illustrator
Generates reference-conditioned, QC-gated artwork for problems
that still use placeholder art (or --force to regenerate).
Images are produced with the canonical Mr 6 reference via
OpenAI images/edits, then checked by Claude vision (artkit).

Usage:
    python generator/illustrate.py              # illustrate anything without a WebP
    python generator/illustrate.py --only duplicatus-of-the-deep --force
    python generator/illustrate.py --force      # regenerate everything
    python generator/illustrate.py --quality high
    python generator/illustrate.py --workers 3

Keys: OPENAI_API_KEY env var or openai_apikey.txt (required);
      ANTHROPIC_API_KEY env var or anthropic_apikey.txt (for the QC gate).
============================================================"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import artkit

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"

parser = argparse.ArgumentParser(description="Generate on-model art for Mr 6 adventures")
parser.add_argument("--only", help="illustrate a single problem id")
parser.add_argument("--ids-file", help="file with one problem id per line; regenerate those (implies --force)")
parser.add_argument("--force", action="store_true", help="regenerate even if a WebP exists")
parser.add_argument("--quality", default="medium", choices=["low", "medium", "high"])
parser.add_argument("--workers", type=int, default=3, help="parallel requests (default 3)")
args = parser.parse_args()


def key_from_file(name):
    p = ROOT / name
    if p.exists():
        lines = p.read_text(encoding="utf-8").strip().splitlines()
        if lines:
            return lines[0].strip() or None
    return None


OPENAI_KEY = os.environ.get("OPENAI_API_KEY") or key_from_file("openai_apikey.txt")
if not OPENAI_KEY:
    sys.exit("[fail] No OpenAI key found — set OPENAI_API_KEY or create openai_apikey.txt.")

try:
    import anthropic
    _akey = os.environ.get("ANTHROPIC_API_KEY") or key_from_file("anthropic_apikey.txt")
    ANTHROPIC = anthropic.Anthropic(api_key=_akey) if _akey else anthropic.Anthropic()
except Exception:
    ANTHROPIC = None
    print("[warn] Anthropic client unavailable — art QC gate is OFF for this run.")

# Hand-written scene direction for the starter pack; newer problems carry imagePrompt.
SCENES = {
    "potion-of-six-strengths":
        "In a moonlit enchanted forest, Mr 6 gathers glowing red berries, blue mushrooms and "
        "silver leaves into a bubbling green cauldron while a huge but goofy iron-skinned ogre "
        "lumbers between distant trees.",
    "sleeping-giants-snores":
        "A colossal gentle giant sleeps across a starlit valley like a range of hills, snoring "
        "big Zzz clouds, while tiny Mr 6 tiptoes toward a tunnel beneath him under a full moon.",
    "bridge-trolls-toll":
        "At golden sunset, a big grumpy but comical troll blocks an old stone bridge over a "
        "river while Mr 6 counts silver coins from three little pouches, a castle on the far hill.",
    "gloomwings-fireflies":
        "In a pitch-dark magical forest, Mr 6 holds up a glass jar glowing with golden fireflies, "
        "lighting a lost puppy nearby, while a giant velvety shadow bat with purple eyes looms in the "
        "treetops.",
    "sneakfingers-pies":
        "On moonlit village rooftops, a sneaky hooded thief dashes away clutching a berry pie, "
        "dripping a trail of berries, while Mr 6 points up at him from the cobblestone street below "
        "beside a warm bakery window full of pies.",
    "screechias-egg-heist":
        "On a dramatic sunset cliff, Mr 6 climbs toward nests full of pearly dragon eggs while a "
        "flamboyant feathered harpy shrieks and circles overhead.",
    "duplicatus-of-the-deep":
        "A gigantic teal sea serpent rises from moonlit ocean waves, towering over a small fishing "
        "boat where Mr 6 stands bravely at the prow with sword raised.",
    "hydrania-hundred-headed":
        "In a misty green swamp, a many-headed hydra with eight snaky necks glares down at Mr 6, "
        "who calmly offers up a wheel of cheese instead of his sword.",
    "wizard-halflings-curse":
        "At purple dusk, Mr 6 gallops on horseback toward a dark wizard tower while behind him a "
        "gentle stone giant shrinks amid swirling violet curse sparkles.",
    "gobblegrims-gold":
        "Inside a torch-lit cave, a scrawny goblin king with a crooked crown perches atop a huge "
        "glittering mountain of gold coins as Mr 6 strides in with sword drawn.",
    "skeleton-legion":
        "In a green-torch-lit crypt, neat rows of comical rattling skeleton soldiers march toward "
        "Mr 6, who braces behind his glowing golden shield with the number 6.",
    "mirror-witch-multiplia":
        "In a grand hall of ornate mirrors under moonlight, a cackling witch splits into fading "
        "copies of herself while Mr 6 polishes his shield into a mirror to show her reflection.",
    "duskwings-lantern":
        "On a starless black crag, Mr 6 holds a blazing golden lantern high, revealing a huge "
        "shadow dragon half-dissolving into the darkness at the edge of the light.",
    "grimtides-flood":
        "In a storm, Mr 6 rows a small boat through rising waves toward a lighthouse where three "
        "children wait on a high ledge, while giant teal sea-monster tentacles rise from the water.",
    "grimscales-armor":
        "Before a volcanic backdrop, an armored wyvern covered in black iron plates rears up as Mr 6 "
        "strikes with his glowing sword, golden sparks flying off the armor.",
    "torchfire-wolves":
        "On dark moonless hills near a sheep pen, Mr 6 raises a bright torch as a circle of shadow "
        "wolves with amber eyes dissolves into wisps at the edge of the firelight.",
    "blackmaws-treasure":
        "At warm sunset on a cliff road above a village, Mr 6 stands proudly beside three open "
        "treasure chests overflowing with gold while a big defeated bandit sits glumly nearby.",
    "frostfang-ice-wyrm":
        "A long serpentine ice wyrm winds down from glacier peaks toward a snowy valley of villages, "
        "half frozen and half warmly lit, as Mr 6 rides hard on horseback through the snow.",
}


def scene_for(problem):
    return SCENES.get(problem["id"]) or problem.get("imagePrompt") or (
        f"Mr 6 bravely faces {problem['monster']}. {problem['story']}"
    )


def illustrate(rel):
    path = CONTENT / rel
    problem = json.loads(path.read_text(encoding="utf-8"))
    pid = problem["id"]

    has_webp = (CONTENT / "images" / f"{pid}.webp").exists()
    if not args.force and (has_webp and problem.get("image", "").endswith(".webp")):
        return (pid, "skipped (already has WebP)")
    if args.only and pid != args.only:
        return (pid, None)

    webp, note = artkit.generate_scene(
        OPENAI_KEY, scene_for(problem), anthropic_client=ANTHROPIC,
        quality=args.quality, log=lambda m: print(f"  [{pid}]{m}", flush=True),
    )
    image_rel = f"images/{pid}.webp"
    (CONTENT / image_rel).write_bytes(webp)
    problem["image"] = image_rel
    path.write_text(json.dumps(problem, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    suffix = f" [warn: {note}]" if note else ""
    return (pid, f"OK -> {image_rel} ({len(webp) // 1024} KB){suffix}")


def main():
    manifest = json.loads((CONTENT / "manifest.json").read_text(encoding="utf-8"))
    rels = manifest["problems"]
    if args.ids_file:
        wanted = {line.strip() for line in Path(args.ids_file).read_text(encoding="utf-8").splitlines() if line.strip()}
        rels = [r for r in rels if Path(r).stem in wanted]
        args.force = True
        missing = wanted - {Path(r).stem for r in rels}
        if missing:
            print(f"[warn] ids not found in manifest: {', '.join(sorted(missing))}")
    if args.only:
        rels = [r for r in rels if Path(r).stem == args.only]
        if not rels:
            sys.exit(f"[fail] No problem with id '{args.only}'")

    print(f"[illustrator] {len(rels)} problem(s) to consider - quality: {args.quality}"
          f" - QC: {'ON' if ANTHROPIC else 'OFF'}")
    done = failed = skipped = warned = 0

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(illustrate, rel): rel for rel in rels}
        for fut in as_completed(futures):
            rel = futures[fut]
            try:
                pid, msg = fut.result()
                if msg is None:
                    continue
                if msg.startswith("skipped"):
                    skipped += 1
                else:
                    done += 1
                    if "[warn" in msg:
                        warned += 1
                print(f"  [{pid}] {msg}", flush=True)
            except Exception as err:
                failed += 1
                print(f"  [{Path(rel).stem}] FAILED: {err}", flush=True)

    print(f"\n[done] {done} illustrated ({warned} with QC warnings), "
          f"{skipped} skipped, {failed} failed.")
    if failed:
        print("[hint] Re-run the same command — finished images are kept, only missing ones retry.")


if __name__ == "__main__":
    main()
