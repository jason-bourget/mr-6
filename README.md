# ⚔️ Mr 6 — Knight of Numbers

A math word-problem game for kids, starring **Mr 6** — a handsome, adventurous knight
who fights monsters and saves the helpless by *out-thinking* them. Medieval anime
storybook vibes, three difficulty tiers, and an AI "Story Forge" that generates
endless new adventures (with art) so kids rarely see the same problem twice.

## Play

```bash
python -m http.server 8123 --bind 127.0.0.1
```

Then open **http://localhost:8123**. (Run the command from this folder.)

- **Squire's Path** (ages 5–8) — adding, subtracting, counting
- **Knight's Quest** (ages 8–10) — multiplication, division, doubling chains
- **Champion's Trial** (ages 10–12) — fractions, percentages, rates, multi-step

Each quest is 5 battles, answered by multiple choice (four options — one right answer
plus three distractors modeled on real mistakes). A wrong pick costs a heart (of 3) and
crosses that option out; a hint appears after the first miss. Solved problems are
remembered (per browser) so new quests prefer adventures the player hasn't seen.

## Generate new adventures (the Story Forge)

The forge runs **offline from gameplay** — run it whenever you want to top up the pool.
It asks Claude for new problems (each arithmetically verified before it's accepted —
broken problems are rejected, never shown to kids) and gpt-image-1 for matching art.

One-time setup:

```bash
pip install anthropic
```

Keys — both are picked up automatically from files in the project root (git-ignored):

- **OpenAI** (images): `openai_apikey.txt` ✅ already in place, or `OPENAI_API_KEY`
- **Anthropic** (problems): `anthropic_apikey.txt`, `ANTHROPIC_API_KEY`, or an
  `ant auth login` profile

Then:

```bash
python generator/generate.py
```

Options:

| Flag | Effect |
|---|---|
| `--count 5` | problems per tier (default 3) |
| `--tier knight` | only one tier (`squire` / `knight` / `champion` / `all`) |
| `--no-images` | skip image generation (placeholder art) |
| `--model claude-opus-5` | which Claude model writes the problems |

Rough cost per adventure: a fraction of a cent for the problem text, and roughly
$0.04–0.06 for a gpt-image-1 medium-quality image.

## How content works

```
content/
  manifest.json        <- list of all problem files (the forge appends here)
  problems/*.json      <- one file per problem (story, question, answer, hint, ...)
  images/*             <- one illustration per problem (SVG starters, PNG generated)
```

The starter pack is 18 hand-written problems (6 per tier) with hand-drawn SVG
silhouette art, so the game is fully playable before you ever run the forge.

To retire a problem, delete its line from `manifest.json` (and optionally its files).
