"""Shared art pipeline for Mr 6: reference-conditioned generation + vision QC.

Every image is generated with the canonical Mr 6 reference image
(generator/reference/mr6.png) via OpenAI's images/edits endpoint, then
checked by Claude's vision against an on-model checklist. Failed images
are retried; the QC verdict is returned to the caller.
"""

import base64
import io
import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

REFERENCE_DIR = Path(__file__).resolve().parent / "reference"

CHARACTER_RULES = """The character is Mr 6 from the reference image(s): a living, heroic
golden numeral 6 with thin arms and legs, brown adventurer gloves and boots, a small
silver knight helmet with a rose-pink plume, and a flowing deep-blue cape. Keep his
design EXACTLY as in the reference. Critical face rules: exactly TWO steely, narrowed,
determined eyes with strong expressive brows, drawn DIRECTLY on the smooth golden
surface of the numeral, placed SIDE BY SIDE high on the numeral's upper stem, well
above the loop — never inside or below the loop, never more than two eyes. NO separate
face patch, NO pale face area, NO nose, NO beak, NO mustache. He carries at most ONE
sword. His body must read unmistakably as the digit 6 — never a blob, a b, or a 9."""

STYLE_RULES = """Style: elegant medieval anime storybook illustration — painterly
cel-shaded fantasy anime, warm magical lighting, rich colors, dramatic but friendly
composition, appealing to children and adults alike. No gore, no frightening realism,
no text or letters in the image (a small 6 on his shield is the only glyph allowed)."""


def compress_to_webp(png_bytes, max_width=1280, quality=80):
    """Shrink API PNGs (~2.4 MB) to phone-friendly WebP (~150-250 KB)."""
    from PIL import Image
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    if im.width > max_width:
        im.thumbnail((max_width, max_width * 4))
    out = io.BytesIO()
    im.save(out, format="WEBP", quality=quality, method=6)
    return out.getvalue()


def _multipart(fields, files):
    boundary = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += (f"--{boundary}\r\n"
                 f'Content-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n').encode()
    for k, fname, data, ctype in files:
        body += (f"--{boundary}\r\n"
                 f'Content-Disposition: form-data; name="{k}"; filename="{fname}"\r\n'
                 f"Content-Type: {ctype}\r\n\r\n").encode() + data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def _openai_edit(openai_key, prompt, quality="medium", timeout=600):
    """Generate a scene via images/edits, conditioned on the Mr 6 reference(s)."""
    refs = sorted(REFERENCE_DIR.glob("*.png"))
    if not refs:
        raise RuntimeError(f"No reference images in {REFERENCE_DIR}")
    body, ctype = _multipart(
        {"model": "gpt-image-1", "prompt": prompt, "size": "1536x1024",
         "quality": quality, "n": "1"},
        [("image[]", r.name, r.read_bytes(), "image/png") for r in refs],
    )
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/edits",
        data=body,
        headers={"Content-Type": ctype, "Authorization": f"Bearer {openai_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            data = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"OpenAI images/edits {e.code}: {detail}") from None
    b64 = (data.get("data") or [{}])[0].get("b64_json")
    if not b64:
        raise RuntimeError("OpenAI images/edits returned no image data.")
    return base64.b64decode(b64)


QC_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean", "description": "true only if every check passes"},
        "problems": {"type": "array", "items": {"type": "string"},
                      "description": "Each failed check, briefly"},
    },
    "required": ["ok", "problems"],
    "additionalProperties": False,
}

QC_PROMPT = """You are the art quality gate for a children's math game. This is
an illustration of Mr 6, a living golden numeral 6 who is a knight. Check ALL of:
1. Exactly TWO eyes, placed side by side HIGH on the numeral's upper stem, above the
   loop. Fail if any eye is inside/below the loop, missing, or more than two.
2. The eyes and brows are drawn DIRECTLY on the golden numeral surface — fail if there
   is a separate pale/white face patch, a face bubble, or a distinct head shape.
3. The eyes read as steely/narrowed/determined with visible brows — not blank, vacant,
   googly, dot-like, or missing.
4. His body reads UNMISTAKABLY as the digit 6 — fail if it looks like a blob, a b, a 9,
   an 8, or an ambiguous shape.
5. Silver knight helmet and pink plume present; deep-blue cape present.
6. No nose, beak, or mustache on the numeral. At most ONE sword.
7. No stray gibberish text or watermark-like lettering. Story-appropriate glyphs are
   FINE and pass: the 6 on his shield, "Zzz" over a sleeper, digits on a magical
   number-lock, prices on a market sign — anything the scene is clearly about.
8. Nothing gory or nightmarish. Storybook-spooky is FINE and passes (cartoon ghosts,
   looming shadows, glowing eyes) — fail only imagery that would genuinely frighten
   a ten-year-old.
For rules 1-6 (the character), a borderline case is a FAIL. For rules 7-8 (the scene),
fail only clear violations. Report ok=true only if ALL pass; otherwise list each
problem briefly."""


def qc_image(anthropic_client, webp_bytes, model="claude-opus-5"):
    """Ask Claude vision to verify the image is on-model. Returns (ok, problems)."""
    response = anthropic_client.beta.messages.create(
        model=model,
        max_tokens=2000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image",
                 "source": {"type": "base64", "media_type": "image/webp",
                            "data": base64.b64encode(webp_bytes).decode("ascii")}},
                {"type": "text", "text": QC_PROMPT},
            ],
        }],
        output_config={"format": {"type": "json_schema", "schema": QC_SCHEMA}},
    )
    if response.stop_reason == "refusal":
        return True, ["qc-refused (accepted without check)"]
    verdict = json.loads("".join(b.text for b in response.content if b.type == "text"))
    return bool(verdict.get("ok")), verdict.get("problems", [])


def generate_scene(openai_key, scene, anthropic_client=None,
                   quality="medium", attempts=3, log=print):
    """Generate one on-model scene as WebP bytes, QC-gated when a client is given.

    Returns (webp_bytes, qc_note). qc_note is "" when clean, else a warning string.
    """
    prompt = (f"Paint a completely NEW scene featuring the exact character from the "
              f"reference image.\n{CHARACTER_RULES}\nScene: {scene}\n"
              f"Any monster looks impressive but storybook-friendly, not scary.\n"
              f"{STYLE_RULES}")

    last_webp, last_problems = None, []
    for attempt in range(1, attempts + 1):
        png = _openai_edit(openai_key, prompt, quality=quality)
        webp = compress_to_webp(png)
        if anthropic_client is None:
            return webp, ""
        try:
            ok, problems = qc_image(anthropic_client, webp)
        except Exception as err:  # QC outage never blocks art delivery
            return webp, f"qc-error: {err}"
        if ok:
            return webp, ""
        last_webp, last_problems = webp, problems
        log(f"    [qc] attempt {attempt} rejected: {'; '.join(problems)}")
        if attempt < attempts:
            time.sleep(2)
    return last_webp, f"qc-failed after {attempts} attempts: {'; '.join(last_problems)}"
