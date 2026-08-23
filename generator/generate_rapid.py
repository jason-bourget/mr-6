"""Generate the daily Rapid Fire round: a story-themed speed drill.

Each day has ONE monster, ONE simple transformation rule (double it, halve it,
subtract from 100, ...), and 10 terse questions drilling that rule fast. One
dedicated illustration is generated for the day's story (reference-conditioned,
QC-gated via artkit).

Usage:
    python generator/generate_rapid.py                # for today (UTC)
    python generator/generate_rapid.py --date 2026-08-24
    python generator/generate_rapid.py --no-image

Idempotent: if the day's rapid file exists, does nothing.
"""

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import artkit

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
RAPID = CONTENT / "rapid"

try:
    import anthropic
except ImportError:
    sys.exit("pip install anthropic")


def key_from_file(name):
    p = ROOT / name
    if p.exists():
        lines = p.read_text(encoding="utf-8").strip().splitlines()
        if lines:
            return lines[0].strip() or None
    return None


parser = argparse.ArgumentParser()
parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
parser.add_argument("--no-image", action="store_true")
args = parser.parse_args()

RAPID.mkdir(exist_ok=True)
day_path = RAPID / f"{args.date}.json"
if day_path.exists():
    print(f"[rapid] {args.date} already generated — nothing to do.")
    sys.exit(0)

_akey = os.environ.get("ANTHROPIC_API_KEY") or key_from_file("anthropic_apikey.txt")
client = anthropic.Anthropic(api_key=_akey) if _akey else anthropic.Anthropic()
openai_key = os.environ.get("OPENAI_API_KEY") or key_from_file("openai_apikey.txt")

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Short battle title, e.g. 'The Doubling Duel'"},
        "monster": {"type": "string", "description": "Monster's full name, e.g. 'Pyroclast the Fire Demon'"},
        "story": {"type": "string", "description": "2-3 sentences: the monster, the stakes, and WHY the rule wins the fight. Ends by daring the player to be fast."},
        "rule": {"type": "string", "description": "Short imperative shown during play, e.g. 'Strike back with DOUBLE the force!' Max ~40 characters."},
        "imagePrompt": {"type": "string", "description": "One-sentence scene: Mr 6 mid-battle with this monster, setting, mood."},
        "problems": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "Terse prompt. For transformation rules, usually just the input number, e.g. '36'. Max ~12 characters."},
                    "answer": {"type": "number"},
                    "check": {"type": "string", "description": "Arithmetic expression evaluating to the answer, digits and + - * / ( ) . only"},
                    "distractors": {"type": "array", "items": {"type": "number"}, "description": "Exactly 3 wrong answers modeling real mental-math slips. Distinct, none equal to the answer."},
                },
                "required": ["q", "answer", "check", "distractors"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "monster", "story", "rule", "imagePrompt", "problems"],
    "additionalProperties": False,
}

ALLOWED_CHECK = re.compile(r"^[\d\s+\-*/().,]*$")


def verify_check(expr, answer):
    if not isinstance(expr, str) or not ALLOWED_CHECK.match(expr):
        return False
    try:
        value = eval(expr, {"__builtins__": {}}, {})
        return isinstance(value, (int, float)) and math.isfinite(value) and abs(value - answer) < 1e-9
    except Exception:
        return False


def recent_mechanics(limit=6):
    """Rules from recent days, so mechanics rotate."""
    rules = []
    for f in sorted(RAPID.glob("*.json"), reverse=True):
        if f.name == "index.json":
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("rule"):
                rules.append(d["rule"])
        except Exception:
            pass
        if len(rules) >= limit:
            break
    return rules


PROMPT_TEMPLATE = """Design today's RAPID FIRE round for "Mr 6 — Knight of Numbers"
(kids ages 10-13). Mr 6 is a living, heroic numeral 6 — a knight who out-thinks
monsters. Rapid Fire is a SPEED drill: one monster, ONE simple mental-math
transformation rule, and 10 terse questions drilling that rule as fast as possible.

Pick ONE mechanic for the whole round and weave it into the story. Examples
(invent variations freely, one per day):
- DOUBLE it (the demon strikes, Mr 6 strikes back with twice the force: see 36, tap 72)
- HALVE it (the splitting slime must be cut exactly in half)
- Subtract from 100 (the shield golem absorbs hits; how much force is left?)
- Add a fixed number (every echo adds 25)
- Multiply by one digit (each mirror triples the beam: see 14, tap 42)
- 10% of it (the tithe-collecting imp takes a tenth)

Avoid these recently used rules: {recent}

Requirements:
- "story": 2-3 sentences that make the rule make sense in the fight, ending with a
  dare to be quick. Storybook-brave, funny, never gory. No real-world money/places.
- "rule": short imperative shown on screen during play (e.g. "Strike back with
  DOUBLE the force!").
- 10 "problems": inputs chosen so a practiced kid can answer in seconds, ramping
  from warm-up to satisfying. For a transformation rule, "q" is just the input
  number. Whole-number answers only. Every "check" must equal the answer exactly.
- "distractors": 3 per question, modeling real slips (off-by-ten, dropped carry,
  neighboring fact, the input itself when tempting).
- "imagePrompt": one sentence, Mr 6 mid-battle with the monster."""


def main():
    prompt = PROMPT_TEMPLATE.format(recent=", ".join(recent_mechanics()) or "none yet")
    response = client.beta.messages.create(
        model="claude-opus-5",
        max_tokens=10000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )
    if response.stop_reason == "refusal":
        sys.exit("[fail] model declined")
    text = "".join(b.text for b in response.content if b.type == "text")
    data = json.loads(text)

    good = []
    for p in data["problems"]:
        d = p.get("distractors")
        ok = (isinstance(p.get("q"), str) and p["q"].strip()
              and isinstance(p.get("answer"), (int, float))
              and verify_check(p.get("check", ""), p["answer"])
              and isinstance(d, list) and len(d) == 3
              and all(isinstance(x, (int, float)) and math.isfinite(x) for x in d)
              and len({round(x, 6) for x in d}) == 3
              and all(abs(x - p["answer"]) > 1e-9 for x in d))
        if ok:
            good.append({"q": p["q"].strip(), "answer": p["answer"], "distractors": d})
        else:
            print(f"  [reject] {p.get('q')!r}")

    if len(good) < 10:
        sys.exit(f"[fail] only {len(good)} of 10 verified — rerun")

    for field in ("title", "monster", "story", "rule"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            sys.exit(f"[fail] missing {field}")

    image_rel = "images/placeholder.svg"
    if not args.no_image and openai_key:
        try:
            webp, note = artkit.generate_scene(
                openai_key, data["imagePrompt"], anthropic_client=client,
                quality="medium", log=lambda m: print(f"  {m}", flush=True))
            image_rel = f"images/rapid-{args.date}.webp"
            (CONTENT / image_rel).write_bytes(webp)
            if note:
                print(f"  [warn] image: {note}")
        except Exception as err:
            print(f"  [warn] image failed, using placeholder: {err}")

    day = {
        "date": args.date, "title": data["title"], "monster": data["monster"],
        "story": data["story"], "rule": data["rule"], "image": image_rel,
        "problems": good[:10],
    }
    day_path.write_text(json.dumps(day, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    index_path = RAPID / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"days": []}
    if args.date not in index["days"]:
        index["days"].append(args.date)
        index["days"].sort()
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    print(f"[rapid] Published {args.date}: {data['title']} — {data['rule']}")
    for p in good[:10]:
        print(f"  {p['q']} -> {p['answer']}")


if __name__ == "__main__":
    main()
