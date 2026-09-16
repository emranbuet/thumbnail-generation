---
name: thumbnail-generator
description: Generate a YouTube thumbnail from a video script and a headshot photo. Reads the newest file in script/, applies thumbnail_brief_prompt.md to extract a thumbnail brief, generates an image with OpenAI gpt-image-1 compositing the newest face in face/, saves versioned results to output/, and interactively revises based on user feedback. Use when the user wants a thumbnail made or revised for a video in this project.
---

# Thumbnail Generator

Orchestrates: script + brief prompt → thumbnail brief → OpenAI gpt-image-1 image
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

From the brief, write a concrete visual prompt for gpt-image-1. It must specify:

- The single top-ranked shocking element / tension to depict (pick the #1 ranked
  item from SHOCKING ELEMENTS).
- That the photo attached as a reference shows the real person to depict — instruct
  the model to keep that person's face/identity, rendering them with a strong,
  legible emotional expression that matches the hook (shocked, smug, alarmed, etc).
- A short bold text overlay, max 3-5 words, high-contrast, placed to not cover the
  face (YouTube thumbnail text conventions).
- Composition: face large, positioned on one third of the frame; background/props
  that visually represent the hook; bold saturated colors; strong rim lighting or
  contrast typical of high-CTR YouTube thumbnails.
- Explicitly state: photorealistic, not illustrated/cartoon, unless the user's
  channel style says otherwise.

Keep this prompt tight (a few sentences) — gpt-image-1 responds better to concrete,
concise direction than long prose.

## Step 3 — Generate the image

Determine the next version number by counting existing `output/thumbnail_v*.png`
files (`ls output/thumbnail_v*.png 2>/dev/null | wc -l`); next version = count + 1.

Run:

```bash
python3 .claude/skills/thumbnail-generator/scripts/generate_image.py \
  --face "face/<picked face file>" \
  --prompt "<prompt from Step 2>" \
  --out "output/thumbnail_v<N>.png"
```

gpt-image-1 only offers 1024x1024 / 1024x1536 / 1536x1024 / auto sizes — none is
exact 16:9. After generation, crop the 1536x1024 result down to YouTube's
recommended 1280x720 using macOS's built-in `sips` (no extra dependencies):

```bash
sips -c 720 1280 "output/thumbnail_v<N>.png"
```

This crops from the center; if the crop cuts off something important (e.g. the
face), redo Step 2's prompt to keep key elements more centered and regenerate.

Tell the user the thumbnail is ready at `output/thumbnail_v<N>.png`.

## Step 4 — Interactive revision loop

Ask the user if they'd like changes. If they give feedback:

1. Build a revision prompt from their feedback (e.g. "make the text bigger and
   change background to red", "make the expression more shocked").
2. Run the same script, but pass **both** the face image and the previous version
   as inputs, and bump the version number:

```bash
python3 .claude/skills/thumbnail-generator/scripts/generate_image.py \
  --face "face/<picked face file>" \
  --previous "output/thumbnail_v<N>.png" \
  --prompt "<revision instructions>" \
  --out "output/thumbnail_v<N+1>.png"
sips -c 720 1280 "output/thumbnail_v<N+1>.png"
```

3. Show the new version, ask again. Repeat until the user is satisfied. Never
   overwrite or delete earlier versions — each round gets its own `thumbnail_vN.png`
   so the user can compare or roll back.

## Notes

- `generate_image.py` uses only the Python standard library — no `pip install`
  needed.
- If the API call fails with an auth error, double-check `.env` or the
  `OPENAI_API_KEY` env var. If it fails because the account isn't verified for
  gpt-image-1, tell the user they need to complete OpenAI's organization
  verification for image generation access.
