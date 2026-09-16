#!/usr/bin/env python3
"""Call OpenAI's gpt-image-2.5 edit endpoint to generate or revise a YouTube
thumbnail, compositing a reference face photo into the scene.

Uses only the Python standard library (no pip install required).
"""
import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.request
import uuid

API_URL = "https://api.openai.com/v1/images/edits"
DEFAULT_MODEL = "gpt-image-2.5-sunburst"

# gpt-image-2.5 custom-size constraints (per OpenAI's image generation guide):
# width/height must be multiples of 16, aspect ratio between 1:3 and 3:1,
# neither edge over 3840px, and total pixels between 655,360 and 8,294,400.
SIZE_RE = re.compile(r"^(\d+)x(\d+)$")


def validate_size(size):
    if size == "auto":
        return size
    m = SIZE_RE.match(size)
    if not m:
        sys.exit(f"ERROR: --size must be 'WIDTHxHEIGHT' or 'auto', got: {size}")
    w, h = int(m.group(1)), int(m.group(2))
    if w % 16 or h % 16:
        sys.exit(f"ERROR: --size width and height must be multiples of 16, got: {size}")
    if max(w, h) > 3840:
        sys.exit(f"ERROR: --size edges must not exceed 3840px, got: {size}")
    if not (1 / 3 <= w / h <= 3):
        sys.exit(f"ERROR: --size aspect ratio must be between 1:3 and 3:1, got: {size}")
    total = w * h
    if not (655360 <= total <= 8294400):
        sys.exit(f"ERROR: --size total pixels must be 655,360-8,294,400, got: {size} ({total})")
    return size


def load_api_key(env_file):
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    if env_file and os.path.isfile(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                if k.strip() == "OPENAI_API_KEY":
                    return v.strip().strip('"').strip("'")
    return None


def encode_multipart(fields, files):
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields:
        parts.append(f"--{boundary}".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"'.encode())
        parts.append(b"")
        parts.append(str(value).encode())
    for name, filepath in files:
        filename = os.path.basename(filepath)
        mime = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
        with open(filepath, "rb") as f:
            data = f.read()
        parts.append(f"--{boundary}".encode())
        parts.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'.encode()
        )
        parts.append(f"Content-Type: {mime}".encode())
        parts.append(b"")
        parts.append(data)
    parts.append(f"--{boundary}--".encode())
    parts.append(b"")
    body = b"\r\n".join(parts)
    return body, boundary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--face", required=True, help="Path to the reference headshot image")
    p.add_argument("--previous", help="Path to the previous thumbnail (for revision passes)")
    p.add_argument("--prompt", required=True, help="Image generation / edit instructions")
    p.add_argument("--out", required=True, help="Where to write the resulting PNG")
    p.add_argument("--size", default="2560x1440", help="WIDTHxHEIGHT (multiples of 16) or 'auto'")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Image model to use")
    p.add_argument("--env-file", default=".env", help="Path to a .env file holding OPENAI_API_KEY")
    args = p.parse_args()
    args.size = validate_size(args.size)

    api_key = load_api_key(args.env_file)
    if not api_key:
        sys.exit(
            f"ERROR: OPENAI_API_KEY not found (checked the OPENAI_API_KEY env var "
            f"and {args.env_file}). Add it to one of those and retry."
        )

    for path in [args.face, args.previous]:
        if path and not os.path.isfile(path):
            sys.exit(f"ERROR: input image not found: {path}")

    images = [("image[]", args.face)]
    if args.previous:
        images.append(("image[]", args.previous))

    fields = [
        ("model", args.model),
        ("prompt", args.prompt),
        ("size", args.size),
        ("n", "1"),
    ]
    body, boundary = encode_multipart(fields, images)

    req = urllib.request.Request(API_URL, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

    try:
        with urllib.request.urlopen(req) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        sys.exit(f"ERROR: OpenAI API request failed ({e.code}): {detail}")
    except urllib.error.URLError as e:
        sys.exit(f"ERROR: could not reach OpenAI API: {e.reason}")

    try:
        b64 = payload["data"][0]["b64_json"]
    except (KeyError, IndexError):
        sys.exit(f"ERROR: unexpected API response: {json.dumps(payload)[:500]}")

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "wb") as f:
        f.write(base64.b64decode(b64))
    print(f"Saved thumbnail to {args.out}")


if __name__ == "__main__":
    main()
