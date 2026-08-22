"""============================================================
Mr 6 — Story Forge
Batch-generates new word problems (Claude API) and matching
anime-storybook images (OpenAI gpt-image-1), then adds them
to the game's content pool.

Usage:
    python generator/generate.py                    # 3 problems per tier, with images
    python generator/generate.py --count 5          # 5 per tier
    python generator/generate.py --tier knight      # one tier only
    python generator/generate.py --no-images        # problems only (placeholder art)
    python generator/generate.py --model claude-opus-5

Setup (one time):
    pip install anthropic

Keys (either source works):
    ANTHROPIC_API_KEY env var, anthropic_apikey.txt, or an `ant auth login` profile
    OPENAI_API_KEY env var or openai_apikey.txt
============================================================"""

import argparse
import base64
import io
import json
import math
import os
import re
import sys
import urllib.request
from pathlib import Path

try:
    import anthropic
except ImportError:
    sys.exit("The Anthropic SDK is missing — run:  pip install anthropic")

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"

# ---------------- CLI args ----------------

parser = argparse.ArgumentParser(description="Forge new Mr 6 adventures")
parser.add_argument("--count", type=int, default=3, help="problems per tier (1-20)")
parser.add_argument("--tier", default="champion", choices=["squire", "knight", "champion", "all"])
parser.add_argument("--model", default="claude-opus-5")
parser.add_argument("--no-images", action="store_true", help="skip image generation")
args = parser.parse_args()

COUNT = max(1, min(20, args.count))
TIERS = ["squire", "knight", "champion"] if args.tier == "all" else [args.tier]
WANT_IMAGES = not args.no_images

# ---------------- key loading ----------------

def key_from_file(name):
    p = ROOT / name
    if p.exists():
        first = p.read_text(encoding="utf-8").strip().splitlines()
        if first:
            return first[0].strip() or None
    return None

anthropic_key = os.environ.get("ANTHROPIC_API_KEY") or key_from_file("anthropic_apikey.txt")
openai_key = os.environ.get("OPENAI_API_KEY") or key_from_file("openai_apikey.txt")

# With no explicit key, the SDK still resolves `ant auth login` profiles on its own.
client = anthropic.Anthropic(api_key=anthropic_key) if anthropic_key else anthropic.Anthropic()

if WANT_IMAGES and not openai_key:
    print("[warn] No OpenAI key found (OPENAI_API_KEY or openai_apikey.txt) — using placeholder art.")

# ---------------- world bible ----------------

TIER_SPECS = {
    "squire": """TIER "squire" (ages 5-8): single-step addition or subtraction within 25,
skip counting by 2s/5s/10s, or very simple repeated addition (like 3 groups of 4).
Numbers stay small. One step of reasoning only. Very short sentences.""",
    "knight": """TIER "knight" (ages 8-10): multiplication and division facts, doubling/halving
chains (2-3 steps), simple multi-step problems (e.g. total then compare), arrays
(rows x columns). Answers stay under 100 in most cases.""",
    "champion": """TIER "champion" (ages 10-13): fractions of a quantity, percentages,
decimals and money, ratios and rates (per hour, per day, speed), rounding-up division
("how many lanterns needed"), multi-step problems combining two or three operations,
averages, and finding an unknown ("what number times 7 gives 84"). Answers may be
decimals. One single numeric answer. Numbers chosen so scratch paper suffices —
challenging but never tedious.""",
}

ARCHETYPES = """Monster-gimmick archetypes to riff on (invent NEW monsters/settings, don't copy):
- A monster that doubles/splits when struck (exponential growth — the trick is to THINK first)
- A curse that halves something every hour (repeated halving)
- Recovered treasure shared equally among villagers (division)
- A toll, price, or recipe requiring adding several amounts (addition/subtraction)
- Enemies marching in rows and columns (arrays/multiplication)
- A rescue race against rising water / spreading ice / burning fuse (rates & time)
- Armor or magic that blocks a fraction/percent of an attack
- Gathering ingredients or fireflies to power a spell (counting up / difference)
- A monster with regrowing parts: remove 1, N grow back (step-by-step tracking)"""

SAFETY = """Tone rules: storybook-brave, never gory. Monsters poof, flee, shrink,
turn friendly, or are outwitted — nobody is hurt on-page. Some problems should be
rescues, sharing, or clever escapes rather than combat. Mr 6 is kind, clever, and
a little funny. Victory text should reward the THINKING, not the hitting."""

# ---------------- output schema ----------------

PROBLEM_SCHEMA = {
    "type": "object",
    "properties": {
        "problems": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "kebab-case slug, unique, e.g. 'thornback-bramble-beast'"},
                    "title": {"type": "string"},
                    "monster": {"type": "string", "description": "Monster's full name, e.g. 'Thornback the Bramble Beast'"},
                    "story": {"type": "string", "description": "2-3 sentence setup starring Mr 6"},
                    "question": {"type": "string", "description": "The single math question, ending in a question mark"},
                    "answer": {"type": "number"},
                    "unit": {"type": "string", "description": "Short unit like 'feet', 'coins', 'heads'"},
                    "check": {"type": "string", "description": "Pure arithmetic expression that evaluates to the answer, e.g. '8*2*2*2' or 'ceil(6/4)'. Only digits, + - * / ( ) . and ceil/floor/round."},
                    "distractors": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "description": "Exactly 3 plausible wrong answers modeling real kid mistakes (stopped a step early, wrong operation, reported an intermediate number). All distinct, none equal to the answer."},
                    "hint": {"type": "string", "description": "A gentle hint that scaffolds the first step without giving the answer"},
                    "victory": {"type": "string", "description": "1-2 sentence triumphant, funny resolution"},
                    "imagePrompt": {"type": "string", "description": "One-sentence visual description of the battle scene (monster, setting, mood) for an illustrator"},
                },
                "required": ["id", "title", "monster", "story", "question", "answer",
                             "unit", "check", "distractors", "hint", "victory", "imagePrompt"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["problems"],
    "additionalProperties": False,
}

# ---------------- answer verification ----------------

ALLOWED_CHECK = re.compile(r"^[\d\s+\-*/().,]*$")

def verify_check(expr, answer):
    """Evaluate the model's arithmetic self-check safely and compare to the answer."""
    if not isinstance(expr, str) or not expr.strip():
        return False
    cleaned = re.sub(r"(Math\.)?(ceil|floor|round)", "", expr)
    if not ALLOWED_CHECK.match(cleaned):
        return False
    safe_expr = expr.replace("Math.", "")
    try:
        value = eval(safe_expr, {"__builtins__": {}},
                     {"ceil": math.ceil, "floor": math.floor, "round": round})
        return isinstance(value, (int, float)) and math.isfinite(value) and abs(value - answer) < 1e-9
    except Exception:
        return False

# ---------------- problem generation ----------------

def load_existing():
    manifest = json.loads((CONTENT / "manifest.json").read_text(encoding="utf-8"))
    problems = []
    for rel in manifest["problems"]:
        try:
            problems.append(json.loads((CONTENT / rel).read_text(encoding="utf-8")))
        except Exception:
            pass  # skip broken entries
    return manifest, problems

def generate_problems(tier, count, existing):
    existing_names = ", ".join(f"{p['id']} ({p.get('monster', '?')})" for p in existing) or "none yet"

    prompt = f"""You are the Story Forge for "Mr 6 — Knight of Numbers", a math word-problem
game for kids. Mr 6 is a living, heroic number six — a brave walking numeral "6" with
arms, legs, a little knight helmet, a blue cape and a sword. He fights monsters and
saves the helpless — by out-THINKING them. Every battle is won by solving one math
problem. Stories may playfully lean on him being a number (he IS a six), but never
make the joke the whole story.

{TIER_SPECS[tier]}

{ARCHETYPES}

{SAFETY}

Already-used adventures (do NOT reuse these monsters, ids, or core scenarios):
{existing_names}

Write {count} brand-new problems for tier "{tier}". Every problem must:
- have exactly one numeric answer (no two-part answers, no units in the answer)
- be genuinely solvable from the numbers given, with no ambiguity
- weave the math INTO the monster's gimmick, like the classics: a sea monster that
  doubles in size when struck, a hydra that regrows 3 heads per slice
- have a "check" expression whose value EQUALS the answer exactly
- have exactly 3 "distractors": plausible wrong answers a real kid would reach by a
  common mistake (one step short, wrong operation, an intermediate number from the
  story). Distinct from each other and from the answer — the game shows all four as
  multiple choice.
- have an imagePrompt describing the scene (monster, setting, lighting/mood) in one sentence

Set the "tier" implicitly — I will add it. Vary settings (sea, sky, crypt, market,
glacier, volcano, library, swamp...) and vary operations across the set."""

    response = client.beta.messages.create(
        model=args.model,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": PROBLEM_SCHEMA}},
    )

    if response.stop_reason == "refusal":
        raise RuntimeError("The model declined this generation request.")
    text = "".join(b.text for b in response.content if b.type == "text")
    problems = json.loads(text)["problems"]
    for p in problems:
        p["tier"] = tier
    return problems

# ---------------- image generation ----------------

CHARACTER_SHEET = """Mr 6 is NOT a human — he is a living, heroic NUMBER SIX. His body
is a big, bold, clearly readable numeral "6" about as tall as a person: smooth, rounded,
glossy golden-bronze, shaped exactly like the digit 6. Exactly two eyes sit SIDE BY SIDE high on
the numeral's upper stem, well above the loop — never inside the loop, and never more
than two eyes; the loop of the 6 stays plain and empty like a belly. His eyes are
steely, narrowed and intelligent — half-lidded with small sharp pupils and strong
expressive eyebrows, one eyebrow arched in a wry, knowing, confident look, like a
razor-sharp wit sizing up his opponent. NEVER wide, round, vacant, surprised or goofy
cartoon eyes. He has NO nose and NO beak — only eyes, eyebrows, and at most a subtle
confident mouth line on the smooth golden numeral. Thin sturdy arms and legs extend from the numeral's
body, with brown adventurer gloves and boots. His knightly gear: a small silver knight
helmet with a rose-pink plume perched on top of the 6, a flowing deep-blue cape on his
back, and a silver sword in one hand. Friendly, brave, confident hero posture. The digit-6
silhouette must stay clearly readable, and this exact character design must be identical
in every image."""

STYLE_SHEET = """Style: elegant medieval anime storybook illustration — painterly
cel-shaded fantasy anime in the spirit of classic theatrical fantasy anime films,
warm magical lighting, rich colors, dramatic but friendly composition, appealing to
children and adults alike. Absolutely no gore, no frightening realism, no text or
letters in the image (the number 6 on the shield is the only glyph allowed)."""

def generate_image(problem):
    prompt = (f"{CHARACTER_SHEET}\nScene: {problem['imagePrompt']}\n"
              f"The monster looks impressive but storybook-friendly, not scary. "
              f"Mr 6 faces it bravely.\n{STYLE_SHEET}")

    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=json.dumps({
            "model": "gpt-image-1",
            "prompt": prompt,
            "size": "1536x1024",
            "quality": "medium",
            "n": 1,
        }).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as res:
            data = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"OpenAI image API {e.code}: {body}") from None

    b64 = (data.get("data") or [{}])[0].get("b64_json")
    if not b64:
        raise RuntimeError("OpenAI image API returned no image data.")
    return compress_to_webp(base64.b64decode(b64))


def compress_to_webp(png_bytes, max_width=1280, quality=80):
    """Shrink API PNGs (~2.4 MB) to phone-friendly WebP (~150-250 KB)."""
    from PIL import Image
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    if im.width > max_width:
        im.thumbnail((max_width, max_width * 4))
    out = io.BytesIO()
    im.save(out, format="WEBP", quality=quality, method=6)
    return out.getvalue()

# ---------------- main ----------------

def main():
    images_on = WANT_IMAGES and bool(openai_key)
    print(f"[forge] {COUNT} problem(s) per tier for: {', '.join(TIERS)}")
    print(f"[forge] model: {args.model} - images: {'gpt-image-1' if images_on else 'OFF (placeholder art)'}\n")

    manifest, existing = load_existing()
    used_ids = {p["id"] for p in existing}
    (CONTENT / "images").mkdir(parents=True, exist_ok=True)

    added = rejected = image_fails = 0

    for tier in TIERS:
        print(f"-- Forging {tier} adventures...")
        try:
            batch = generate_problems(tier, COUNT, existing)
        except Exception as err:
            print(f"  [fail] Generation failed for {tier}: {err}")
            continue

        for p in batch:
            # ---- validation gate: no broken problems reach kids ----
            faults = []
            if not p.get("id") or p["id"] in used_ids:
                faults.append("duplicate or missing id")
            if not isinstance(p.get("answer"), (int, float)) or not math.isfinite(p["answer"]):
                faults.append("non-numeric answer")
            elif not verify_check(p.get("check"), p["answer"]):
                faults.append(f"check \"{p.get('check')}\" != answer {p['answer']}")
            d = p.get("distractors")
            if (not isinstance(d, list) or len(d) != 3
                    or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in d)
                    or len({round(x, 6) for x in d}) != 3
                    or any(abs(x - p.get("answer", 0)) < 1e-9 for x in d)):
                faults.append("bad distractors (need 3 distinct numbers != answer)")
            for f in ["title", "monster", "story", "question", "hint", "victory"]:
                if not isinstance(p.get(f), str) or not p[f]:
                    faults.append(f"missing {f}")
            if faults:
                rejected += 1
                print(f"  [reject] \"{p.get('title') or p.get('id')}\": {'; '.join(faults)}")
                continue

            # ---- image ----
            image_path = "images/placeholder.svg"
            if images_on:
                try:
                    webp = generate_image(p)
                    image_path = f"images/{p['id']}.webp"
                    (CONTENT / image_path).write_bytes(webp)
                    print(f"  [image] {image_path}")
                except Exception as err:
                    image_fails += 1
                    print(f"  [warn] Image failed for \"{p['title']}\" (using placeholder): {err}")

            # ---- persist ----
            record = {
                "id": p["id"], "tier": p["tier"], "title": p["title"], "monster": p["monster"],
                "story": p["story"], "question": p["question"], "answer": p["answer"],
                "unit": p.get("unit", ""), "distractors": p["distractors"],
                "hint": p["hint"], "victory": p["victory"],
                "image": image_path, "imagePrompt": p.get("imagePrompt", ""),
            }
            rel = f"problems/{p['id']}.json"
            (CONTENT / rel).write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
            manifest["problems"].append(rel)
            used_ids.add(p["id"])
            existing.append(record)
            added += 1
            print(f"  [ok] {p['title']} ({p['tier']}, answer: {p['answer']})")

    (CONTENT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"\n[done] {added} adventure(s) added, {rejected} rejected by verification, "
          f"{image_fails} image failure(s).")
    print(f"[done] Total pool: {len(manifest['problems'])} problems.")

if __name__ == "__main__":
    try:
        main()
    except anthropic.AuthenticationError:
        sys.exit("[fail] Anthropic auth failed — set ANTHROPIC_API_KEY, create anthropic_apikey.txt, or run `ant auth login`.")
    except anthropic.RateLimitError:
        sys.exit("[fail] Rate limited by the Claude API — wait a minute and try again.")
    except anthropic.APIStatusError as err:
        sys.exit(f"[fail] Claude API error {err.status_code}: {err.message}")
    except anthropic.APIConnectionError:
        sys.exit("[fail] Could not reach the Claude API — check your connection.")
