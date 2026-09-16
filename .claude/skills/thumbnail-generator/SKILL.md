---
name: thumbnail-generator
description: Generate a YouTube thumbnail from a video script and a headshot photo. Reads the newest file in script/, applies thumbnail_brief_prompt.md to extract a thumbnail brief, generates an image with OpenAI gpt-image-2.5 compositing the newest face in face/, saves versioned results to output/, and interactively revises based on user feedback. Use when the user wants a thumbnail made or revised for a video in this project.
---

# Thumbnail Generator

Orchestrates: script + brief prompt → thumbnail brief → OpenAI gpt-image-2.5 image
(with the user's face composited in) → interactive revision loop. All paths below
are relative to the project root (the `thumbnail-generation` directory that contains
this `.claude/` folder).

## Prerequisites check

Before doing anything, verify:

1. `script/` contains at least one file. Pick the **most recently modified** one:
   `ls -t script/ | head -1`. If empty, stop and tell the user to drop their video
   script (.txt/.md) into `script/`.
2. `face/` contains at least one image file. Pick the **most recently modified** one
   the same way: `ls -t face/ | head -1`. If empty, stop and tell the user to drop a
   headshot photo into `face/`.
3. An OpenAI API key is available: either the `OPENAI_API_KEY` env var is set, or a
   `.env` file at the project root has a line `OPENAI_API_KEY=sk-...`. If neither
   exists, stop and ask the user to create `.env` (from `.env.example`) with their key.

## Step 1 — Extract the thumbnail brief

1. Read `thumbnail_brief_prompt.md` in full — it defines your persona, task, and
   strict output rules (under 2000 characters, no fluff, specific sections: TOPIC,
   SHOCKING ELEMENTS, AUDIENCE PSYCHOLOGY).
2. Read the script file picked above.
3. Following that prompt's instructions exactly, produce the thumbnail brief
   yourself (you are the model doing the analysis — no API call here). Treat the
   script's content as what goes below the `PASTE VIDEO SCRIPT BELOW THIS LINE`
   marker.
4. Save the brief to `output/latest_brief.md` (overwrite each run — it's a working
   artifact, not a versioned deliverable) so the user can see the reasoning behind
   the thumbnail.

## Step 2 — Turn the brief into an image prompt

We use `gpt-image-2.5-sunburst`, which generates custom sizes natively — no crop
step needed. Default size is **2560x1440**, exact 16:9 and the same resolution as
any reference thumbnail the user gives you. Custom sizes must have width/height
as multiples of 16, aspect ratio between 1:3 and 3:1, no edge over 3840px, and
655,360-8,294,400 total pixels (`generate_image.py` validates this).

From the brief, write a concrete visual prompt for `gpt-image-2.5-sunburst`. It
must specify:

- The single top-ranked shocking element / tension to depict (pick the #1 ranked
  item from SHOCKING ELEMENTS).
- That the photo attached as a reference shows the real person to depict — instruct
  the model to keep that person's face/identity. Default to a calm-to-mildly-
  surprised, legible expression rather than an extreme scared/screaming look
  unless the user asks for maximum shock value.
- Medium shot: head and shoulders both fully visible, with clear headroom above
  the hair — not a tight close-up cropped into the face.
- A short bold text overlay, max 3-5 words, sized moderately (roughly 12-18% of
  frame height per line, not larger), with a dark outline/border for legibility,
  placed in open background space that doesn't overlap the face.
- Composition: subject positioned in one half of the frame with the other half
  left open for text/graphics; clean, uncluttered background (subtle vignette or
  grid, not busy); bold but not oversaturated colors — reference the general
  high-CTR YouTube finance-thumbnail style, not a garish poster. If the user has
  provided a reference/sample thumbnail, match its layout pattern (subject side,
  text placement, chart/graphic style) rather than inventing a new one.
- Explicitly state: photorealistic, not illustrated/cartoon, unless the user's
  channel style says otherwise.

Keep this prompt tight (a few sentences) — the model responds better to concrete,
concise direction than long prose. Note: image edits are full regenerations
conditioned on the input image(s) and prompt, not a targeted local edit — relative
instructions like "make it smaller than before" are unreliable. Always state
**absolute** sizes/positions (e.g. "text no taller than 15% of frame height") rather
than relative deltas.

**Show the user the exact prompt and parameters (face file, size, output path)
you're about to send, and wait for an explicit "yes" before proceeding to Step 3.
Never call `generate_image.py` without that explicit go-ahead — this applies to
every single generation, including every revision round, not just the first one.**

## Step 3 — Generate the image

Only do this after the user has explicitly said yes to the prompt from Step 2.

Determine the next version number by counting existing `output/thumbnail_v*.png`
files (`ls output/thumbnail_v*.png 2>/dev/null | wc -l`); next version = count + 1.

Run:

```bash
python3 .claude/skills/thumbnail-generator/scripts/generate_image.py \
  --face "face/<picked face file>" \
  --prompt "<prompt from Step 2>" \
  --out "output/thumbnail_v<N>.png"
```

This generates natively at 2560x1440 (16:9) — no cropping needed. If the result
doesn't match what was asked (wrong layout, cut-off text, etc.), that means the
prompt needs tightening, not that a crop step is missing.

Tell the user the thumbnail is ready at `output/thumbnail_v<N>.png`.

## Step 4 — Interactive revision loop

Ask the user if they'd like changes. If they give feedback:

1. Build a revision prompt from their feedback (e.g. "make the text bigger and
   change background to red", "make the expression more shocked"), using
   **absolute** sizes/positions per Step 2's note.
2. Show the user the exact revision prompt and parameters, and **wait for an
   explicit "yes"** — same rule as Step 2, every round.
3. Once confirmed, run the same script, passing **both** the face image and the
   previous version as inputs, and bump the version number:

```bash
python3 .claude/skills/thumbnail-generator/scripts/generate_image.py \
  --face "face/<picked face file>" \
  --previous "output/thumbnail_v<N>.png" \
  --prompt "<revision instructions>" \
  --out "output/thumbnail_v<N+1>.png"
```

4. Show the new version, ask again. Repeat until the user is satisfied. Never
   overwrite or delete earlier versions — each round gets its own `thumbnail_vN.png`
   so the user can compare or roll back.

## Notes

- `generate_image.py` uses only the Python standard library — no `pip install`
  needed.
- If the API call fails with an auth error, double-check `.env` or the
  `OPENAI_API_KEY` env var. If it fails because the account isn't verified for
  GPT Image models, tell the user they need to complete OpenAI's organization
  verification for image generation access.
