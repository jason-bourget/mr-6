"""Backfill worked-solution steps + praise lines onto existing problems.

Usage:  python generator/backfill_solutions.py
Processes every manifest problem missing a "solution" field, in batches of 10.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"

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


_akey = os.environ.get("ANTHROPIC_API_KEY") or key_from_file("anthropic_apikey.txt")
client = anthropic.Anthropic(api_key=_akey) if _akey else anthropic.Anthropic()

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "solution": {"type": "array", "items": {"type": "string"},
                                  "description": "2-3 short worked-solution steps, arithmetic shown, final step states the answer with unit"},
                    "praise": {"type": "string",
                                "description": "One warm growth-mindset line for a wrong answer: name the good strategy and the missing step"},
                },
                "required": ["id", "solution", "praise"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def generate_batch(batch):
    listing = "\n\n".join(
        f"id: {p['id']}\nquestion: {p['question']}\nanswer: {p['answer']} {p.get('unit', '')}\nhint: {p.get('hint', '')}"
        for p in batch
    )
    prompt = f"""These are math word problems from a kids' game (ages 10-13). For EACH problem,
write:
- "solution": 2-3 short worked steps a kid can follow, each a self-contained sentence
  with the arithmetic shown (e.g. "Each minute the web really shrinks by 6 - 4.5 = 1.5
  feet."). The final step must state the answer with its unit.
- "praise": one warm growth-mindset line for a kid who picked a wrong answer: name the
  good strategy they likely tried and the step that was missing (e.g. "Dividing was the
  right instinct - one step was missing."). Praise the thinking, never judge the child.

Problems:

{listing}"""

    response = client.beta.messages.create(
        model="claude-opus-5",
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("model declined")
    text = "".join(b.text for b in response.content if b.type == "text")
    return json.loads(text)["items"]


def main():
    manifest = json.loads((CONTENT / "manifest.json").read_text(encoding="utf-8"))
    todo = []
    for rel in manifest["problems"]:
        path = CONTENT / rel
        p = json.loads(path.read_text(encoding="utf-8"))
        if not p.get("solution"):
            todo.append((path, p))

    print(f"[backfill] {len(todo)} problem(s) need solutions")
    done = failed = 0
    for i in range(0, len(todo), 10):
        batch = todo[i:i + 10]
        by_id = {p["id"]: (path, p) for path, p in batch}
        try:
            items = generate_batch([p for _, p in batch])
        except Exception as err:
            failed += len(batch)
            print(f"  [fail] batch at {i}: {err}", flush=True)
            continue
        for item in items:
            entry = by_id.get(item["id"])
            if not entry:
                continue
            path, p = entry
            sol, praise = item.get("solution"), item.get("praise")
            if (not isinstance(sol, list) or not (2 <= len(sol) <= 3)
                    or not all(isinstance(s, str) and s.strip() for s in sol)
                    or not isinstance(praise, str) or not praise.strip()):
                failed += 1
                print(f"  [reject] {item['id']}: malformed solution/praise", flush=True)
                continue
            p["solution"] = sol
            p["praise"] = praise
            path.write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            done += 1
        print(f"  ...{done} done", flush=True)

    print(f"[done] {done} backfilled, {failed} failed/rejected")


if __name__ == "__main__":
    main()
