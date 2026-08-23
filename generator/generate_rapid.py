"""Generate the daily Rapid Fire set: 10 quick mental-math questions.

Usage:
    python generator/generate_rapid.py                # for today (UTC)
    python generator/generate_rapid.py --date 2026-08-24

Idempotent: if the day's rapid file exists, does nothing. Questions are
forged by Claude (terse, mixed mental-math toolkit) and every answer is
verified arithmetically before acceptance. All 10 share one image, picked
from the existing library by date.
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

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
args = parser.parse_args()

RAPID.mkdir(exist_ok=True)
day_path = RAPID / f"{args.date}.json"
if day_path.exists():
    print(f"[rapid] {args.date} already generated — nothing to do.")
    sys.exit(0)

_akey = os.environ.get("ANTHROPIC_API_KEY") or key_from_file("anthropic_apikey.txt")
client = anthropic.Anthropic(api_key=_akey) if _akey else anthropic.Anthropic()

SCHEMA = {
    "type": "object",
    "properties": {
        "problems": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "Terse question, e.g. '7 × 8', '96 − 38', '10% of 340', 'Half of 76'. No story, max ~20 characters."},
                    "answer": {"type": "number"},
                    "check": {"type": "string", "description": "Arithmetic expression evaluating to the answer, digits and + - * / ( ) . only"},
                    "distractors": {"type": "array", "items": {"type": "number"}, "description": "Exactly 3 wrong answers modeling real mental-math slips (neighboring table fact, dropped carry, off by ten, digit swap). Distinct, none equal to the answer."},
                },
                "required": ["q", "answer", "check", "distractors"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["problems"],
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


def pick_image(date):
    """Date-rotating pick from the existing library art."""
    images = sorted(p.name for p in (CONTENT / "images").glob("*.webp"))
    if not images:
        return "images/placeholder.svg"
    idx = int(hashlib.sha256(date.encode()).hexdigest(), 16) % len(images)
    return f"images/{images[idx]}"


PROMPT = """Write exactly 10 rapid-fire MENTAL MATH questions for kids ages 10-13.
This is a speed round: each question is terse (no story), answered in seconds by a
practiced mind. Mix the toolkit across the set — include a spread of:
- multiplication facts up to 12 × 12
- division facts (inverses of the tables)
- two-digit addition and subtraction (with carrying/borrowing)
- doubling or halving a two-digit number
- an easy percent of a round number (10%, 25%, or 50%)
Format questions tersely: "7 × 8", "96 − 38", "72 ÷ 9", "Double 47", "25% of 80".
Use × − ÷ symbols, not words, except for Double/Half/% forms. Vary difficulty from
warm-up to satisfying. Every "check" expression must equal the answer exactly.
Distractors must be the answers to REAL mental-math slips: the neighboring times-table
fact, a dropped carry, off-by-ten, a digit swap. All whole numbers unless the question
naturally yields a decimal (avoid decimals in this speed round)."""


def main():
    response = client.beta.messages.create(
        model="claude-opus-5",
        max_tokens=8000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": PROMPT}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )
    if response.stop_reason == "refusal":
        sys.exit("[fail] model declined")
    text = "".join(b.text for b in response.content if b.type == "text")
    raw = json.loads(text)["problems"]

    good = []
    for p in raw:
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

    day = {"date": args.date, "image": pick_image(args.date), "problems": good[:10]}
    day_path.write_text(json.dumps(day, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    index_path = RAPID / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"days": []}
    if args.date not in index["days"]:
        index["days"].append(args.date)
        index["days"].sort()
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    print(f"[rapid] Published {args.date}: 10 questions · image {day['image']}")
    for p in good[:10]:
        print(f"  {p['q']} = {p['answer']}")


if __name__ == "__main__":
    main()
