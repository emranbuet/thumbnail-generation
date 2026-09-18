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
2. Drop a headshot photo (`.jpg`/`.jpeg`/`.png`/`.webp`/… common image types)
   into [face/](face/).
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

### How files are picked and versioned

- **Script:** newest `.txt`/`.md` in `script/` by modification time. `.gitkeep`,
  other dotfiles, and non-script junk are ignored.
- **Face:** newest image in `face/` among common image extensions (case-
  insensitive). `.gitkeep` and junk are ignored.
- **Output version:** next `N` is **max numeric suffix** among
  `output/thumbnail_vN.png` files, plus one — not “count of files + 1”. So if
  `v1` and `v3` exist, the next file is `thumbnail_v4.png`.

Helpers (stdlib-only, no API call):

```bash
python3 .claude/skills/thumbnail-generator/scripts/generate_image.py --pick-script
python3 .claude/skills/thumbnail-generator/scripts/generate_image.py --pick-face
python3 .claude/skills/thumbnail-generator/scripts/generate_image.py --next-version
```

### Dry-run and offline self-check

Print the request shape (model, size, field names) without calling the API:

```bash
python3 .claude/skills/thumbnail-generator/scripts/generate_image.py \
  --dry-run \
  --face face/your-headshot.jpg \
  --prompt "example prompt" \
  --out output/thumbnail_v1.png
```

Run minimal offline self-checks:

```bash
python3 .claude/skills/thumbnail-generator/scripts/generate_image.py --self-test
```

## Project structure

```
thumbnail_brief_prompt.md   The prompt template used to analyze your script
script/                     Drop your video script here (.txt / .md)
face/                       Drop your headshot here (common image types)
output/                     Generated thumbnails land here (gitignored)
.env.example                Template for your OpenAI API key
.claude/skills/thumbnail-generator/
  SKILL.md                  Instructions Claude follows to run the pipeline
  scripts/generate_image.py Calls the OpenAI image-edit API (stdlib only);
                            also --dry-run / --self-test / pick & version helpers
```

## Troubleshooting

- **Auth error from the OpenAI API** — double-check `OPENAI_API_KEY` in `.env`.
- **Permission/organization error** — your OpenAI org likely hasn't completed
  identity verification, which GPT Image models require.
- **Response lacks `b64_json`** — `generate_image.py` now exits with the fields
  present in `data[0]` and a short body preview; check model access / response
  format rather than assuming a file was written.
- **Wrong file picked** — confirm the intended script/face has a supported
  extension and is newer than other candidates; `.gitkeep` is never selected.
- **Layout doesn't match what you wanted** — since generation is native 16:9
  (no crop step), a bad layout means the prompt itself needs adjusting; describe
  the fix in absolute terms (e.g. "text no taller than 15% of frame height")
  rather than relative ones ("smaller than before"), since each revision is a
  fresh generation, not a targeted edit.
