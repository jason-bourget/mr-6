"""Publish today's daily quest: the 10 oldest not-yet-published problems.

Usage:
    python generator/publish_day.py               # publish for today (UTC)
    python generator/publish_day.py --date 2026-08-23

Idempotent: if the day file already exists, does nothing. Fails loudly if
fewer than 10 unpublished problems remain (the forge should run first).
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
DAYS = CONTENT / "days"

parser = argparse.ArgumentParser()
parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
parser.add_argument("--count", type=int, default=3)
args = parser.parse_args()

DAYS.mkdir(exist_ok=True)
day_path = DAYS / f"{args.date}.json"
if day_path.exists():
    print(f"[day] {args.date} already published — nothing to do.")
    sys.exit(0)

manifest = json.loads((CONTENT / "manifest.json").read_text(encoding="utf-8"))

# Problems already used by any published day
assigned = set()
for f in DAYS.glob("*.json"):
    if f.name == "index.json":
        continue
    assigned.update(json.loads(f.read_text(encoding="utf-8"))["problems"])

# Playable pool in manifest (chronological) order
pool = []
for rel in manifest["problems"]:
    if rel in assigned:
        continue
    try:
        p = json.loads((CONTENT / rel).read_text(encoding="utf-8"))
    except Exception:
        continue
    if p.get("tier") == "champion" and isinstance(p.get("answer"), (int, float)):
        pool.append(rel)

if len(pool) < args.count:
    sys.exit(f"[fail] Only {len(pool)} unpublished problems available — need {args.count}. "
             f"Run the forge first.")

picked = pool[:args.count]
day_path.write_text(json.dumps({"date": args.date, "problems": picked}, indent=2) + "\n",
                    encoding="utf-8")

index_path = DAYS / "index.json"
index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"days": []}
if args.date not in index["days"]:
    index["days"].append(args.date)
    index["days"].sort()
index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

print(f"[day] Published {args.date}: {len(picked)} adventures "
      f"({len(pool) - len(picked)} left in queue).")
for rel in picked:
    print(f"  - {Path(rel).stem}")
