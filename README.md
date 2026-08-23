# ⚔️ Mr 6 — Knight of Numbers

A daily math quest for kids (ages 10–13), starring **Mr 6** — a living, steely-eyed
number six who fights monsters and saves the helpless by *out-thinking* them. Medieval
anime storybook art, one shared quest of 10 problems per day (Wordle-style), and an AI
"Story Forge" that writes and illustrates 10 new adventures every morning.

**Play: https://mr6.vercel.app** — on iPhone/iPad: open in Safari → Share →
Add to Home Screen.

## How a day works

Every morning (~6 AM Mountain) the Story Forge GitHub Action:
1. forges 3 new "thinker" problems (Claude), each **arithmetically verified**, with a
   2-3 step worked solution and a growth-mindset praise line;
2. illustrates them with the canonical Mr 6 **reference image** (gpt-image-1
   images/edits) gated by a **vision QC** (Claude) that rejects off-model art;
3. publishes the day's quest: the 3 oldest problems in the queue;
4. forges the day's **Rapid Fire** round: 10 terse mental-math questions (tables,
   two-digit add/subtract, division facts, doubling/halving, easy percents), verified,
   sharing one library illustration;
5. commits — Vercel redeploys automatically.

Two modes, same for everyone each day:
- **Today's Quest** — 3 story thinkers: one pick each, optional owl hint, worked
  solution after every answer. Replayable; the day's score is your best.
- **Rapid Fire** — 10 quick strikes against a stopwatch; best score + time of the
  day is kept, unlimited races.

The queue holds ~1 month of buffer, so a failed generation never breaks a morning.

## Worldbuilding rules

Self-contained fantasy realm: invented currencies (crowns, moonstone shards — never
dollars), no real-world places or brands. Mr 6's character canon and the art rules
live in `generator/artkit.py`; his reference images in `generator/reference/`.

## Local development

```bash
python -m http.server 8123 --bind 127.0.0.1     # play at localhost:8123
```

Generator scripts (need `pip install anthropic pillow`; keys in gitignored
`openai_apikey.txt` / `anthropic_apikey.txt` or env vars):

| Command | Purpose |
|---|---|
| `python generator/generate.py --count 10` | forge new problems (+art) into the queue |
| `python generator/publish_day.py` | publish today's quest from the queue |
| `python generator/illustrate.py --only <id> --force` | redo one illustration |
| `python generator/qc_sweep.py` | vision-QC every image, list failures |

## Content layout

```
content/
  manifest.json        <- every problem ever forged (the queue, in order)
  days/index.json      <- list of published days
  days/YYYY-MM-DD.json <- the 10 problem files for that day's quest
  problems/*.json      <- one file per problem
  images/*.webp        <- one phone-sized illustration per problem
```
