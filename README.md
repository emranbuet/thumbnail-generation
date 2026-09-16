# Thumbnail Generator

A Claude Code skill that turns a YouTube video script and a headshot photo into
a ready-to-use YouTube thumbnail, using OpenAI's `gpt-image-2.5-sunburst` to
composite your face into a scene, then iterates on it based on your feedback.

## What it does

1. Reads your video script and runs it through `thumbnail_brief_prompt.md` to
   extract a "thumbnail brief" — the shocking hooks, audience psychology, and
   the single tension most likely to earn a click.
2. Turns that brief into an image-generation prompt, and shows it to you for
   approval before spending any API credits.
3. Calls OpenAI's `gpt-image-2.5-sunburst` with your headshot as a reference
   image, generating natively at 2560x1440 (exact 16:9) — no cropping needed.
4. Asks if you'd like changes, and revises the image based on your feedback —
   showing you each revision prompt for approval first, and keeping every
   version so you can compare or roll back.

## Requirements

- [Claude Code](https://claude.com/claude-code)
- Python 3 (standard library only — no `pip install` needed)
- An OpenAI API key with access to GPT Image models. Note: these models require
  your OpenAI organization to complete identity verification before they'll
  generate images — do this at platform.openai.com if you haven't already.

## Setup

1. Clone this repo and open it in Claude Code.
2. Add your OpenAI API key:
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` and replace the placeholder with your real key:
   ```
   OPENAI_API_KEY=sk-...
   ```
   `.env` is gitignored, so your key never gets committed.

## Usage

1. Drop your full video script (`.txt` or `.md`) into [script/](script/).
2. Drop a headshot photo (`.jpg`/`.png`) into [face/](face/).
3. In Claude Code, run the skill:
   ```
   /thumbnail-generator
   ```
4. Claude will read both files, generate a thumbnail, and save it to
   [output/](output/) as `thumbnail_v1.png`.
5. Tell Claude what to change ("make the text bigger", "more shocked
   expression", "change the background to red") and it will generate
   `thumbnail_v2.png`, `v3.png`, etc. — nothing gets overwritten, so you can
   always go back to an earlier version.

If you have multiple files in `script/` or `face/`, the skill always picks the
most recently modified one.

## Project structure

```
thumbnail_brief_prompt.md   The prompt template used to analyze your script
script/                     Drop your video script here
face/                       Drop your headshot here
output/                     Generated thumbnails land here (gitignored)
.env.example                Template for your OpenAI API key
.claude/skills/thumbnail-generator/
  SKILL.md                  Instructions Claude follows to run the pipeline
  scripts/generate_image.py Calls the OpenAI image-edit API (stdlib only)
```

## Troubleshooting

- **Auth error from the OpenAI API** — double-check `OPENAI_API_KEY` in `.env`.
- **Permission/organization error** — your OpenAI org likely hasn't completed
  identity verification, which GPT Image models require.
- **Layout doesn't match what you wanted** — since generation is native 16:9
  (no crop step), a bad layout means the prompt itself needs adjusting; describe
  the fix in absolute terms (e.g. "text no taller than 15% of frame height")
  rather than relative ones ("smaller than before"), since each revision is a
  fresh generation, not a targeted edit.
