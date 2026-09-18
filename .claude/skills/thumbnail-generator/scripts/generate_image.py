#!/usr/bin/env python3
"""Call OpenAI gpt-image-2.5 edits API to generate/revise a YouTube thumbnail.

Stdlib only. Hardening: extension-aware picks, max-suffix versioning, --dry-run,
clearer missing-b64_json errors, --self-test.
"""
import argparse, base64, json, mimetypes, os, re, sys, urllib.error, urllib.request, uuid

API_URL = "https://api.openai.com/v1/images/edits"
DEFAULT_MODEL = "gpt-image-2.5-sunburst"
SCRIPT_EXTS = (".txt", ".md")
FACE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff")
JUNK = {".gitkeep", ".ds_store", "thumbs.db", "desktop.ini"}
SIZE_RE = re.compile(r"^(\d+)x(\d+)$")
VER_RE = re.compile(r"^thumbnail_v(\d+)\.png$", re.I)


def validate_size(size):
    if size == "auto":
        return size
    m = SIZE_RE.match(size)
    if not m:
        sys.exit(f"ERROR: --size must be 'WIDTHxHEIGHT' or 'auto', got: {size}")
    w, h = int(m.group(1)), int(m.group(2))
    if w % 16 or h % 16:
        sys.exit(f"ERROR: --size width/height must be multiples of 16, got: {size}")
    if max(w, h) > 3840:
        sys.exit(f"ERROR: --size edges must not exceed 3840px, got: {size}")
    if not (1 / 3 <= w / h <= 3):
        sys.exit(f"ERROR: --size aspect ratio must be between 1:3 and 3:1, got: {size}")
    total = w * h
    if not (655360 <= total <= 8294400):
        sys.exit(f"ERROR: --size total pixels must be 655360-8294400, got: {size} ({total})")
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
        parts += [f"--{boundary}".encode(), f'Content-Disposition: form-data; name="{name}"'.encode(), b"", str(value).encode()]
    for name, filepath in files:
        filename = os.path.basename(filepath)
        mime = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
        with open(filepath, "rb") as f:
            data = f.read()
        parts += [
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'.encode(),
            f"Content-Type: {mime}".encode(),
            b"",
            data,
        ]
    parts += [f"--{boundary}--".encode(), b""]
    return b"\r\n".join(parts), boundary


def pick_newest(directory, extensions):
    """Newest file by mtime with given extensions; skips .gitkeep/junk."""
    if not os.path.isdir(directory):
        return None
    exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
    cands = []
    for name in os.listdir(directory):
        if name.startswith(".") or name.lower() in JUNK:
            continue
        path = os.path.join(directory, name)
        if os.path.isfile(path) and os.path.splitext(name)[1].lower() in exts:
            cands.append(path)
    return max(cands, key=os.path.getmtime) if cands else None


def next_thumbnail_version(output_dir="output"):
    """Max numeric suffix among thumbnail_vN.png + 1 (not file count)."""
    if not os.path.isdir(output_dir):
        return 1
    nums = [int(m.group(1)) for name in os.listdir(output_dir) if (m := VER_RE.match(name))]
    return (max(nums) + 1) if nums else 1


def extract_b64_json(payload):
    if not isinstance(payload, dict):
        sys.exit(f"ERROR: API response is not a JSON object ({type(payload).__name__}): {str(payload)[:500]}")
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        sys.exit(
            "ERROR: API response missing non-empty 'data' list with b64_json. "
            f"Top-level keys: {sorted(payload.keys())}. Body preview: {json.dumps(payload)[:500]}"
        )
    first = data[0]
    if not isinstance(first, dict):
        sys.exit(f"ERROR: API response data[0] is not an object: {json.dumps(payload)[:500]}")
    if "b64_json" not in first:
        hint = " Response has 'url' instead of 'b64_json'." if "url" in first else ""
        sys.exit(
            "ERROR: API response data[0] lacks 'b64_json'. "
            f"Present fields: {sorted(first.keys())}.{hint} Body preview: {json.dumps(payload)[:500]}"
        )
    return first["b64_json"]


def print_dry_run(args, fields, files):
    print("DRY-RUN — request shape (no API call):")
    print(f"  url: {API_URL}")
    print("  method: POST")
    print(f"  model: {args.model}")
    print(f"  size: {args.size}")
    print(f"  field names: {[n for n, _ in fields]}")
    print(f"  file field names: {[n for n, _ in files]}")
    for n, p in files:
        print(f"    - {n}: {p}")
    print(f"  out: {args.out}")
    if args.previous:
        print(f"  previous: {args.previous}")
    print(f"  prompt length: {len(args.prompt)} chars")
    print("  Authorization: Bearer <OPENAI_API_KEY> (not sent in dry-run)")


def run_self_test():
    import shutil, tempfile
    failures = []
    try:
        assert validate_size("2560x1440") == "2560x1440"
        assert validate_size("auto") == "auto"
    except SystemExit as e:
        failures.append(f"validate_size good: {e}")
    for bad in ("100x100", "17x17", "notasize"):
        try:
            validate_size(bad); failures.append(f"should reject {bad}")
        except SystemExit:
            pass
    try:
        assert extract_b64_json({"data": [{"b64_json": "QQ=="}]}) == "QQ=="
    except SystemExit as e:
        failures.append(f"extract happy: {e}")
    for payload in ({}, {"data": []}, {"data": [{"url": "https://x"}]}, {"data": ["x"]}):
        try:
            extract_b64_json(payload); failures.append(f"should reject {payload!r}")
        except SystemExit as e:
            if "b64_json" not in str(e) and "data" not in str(e):
                failures.append(f"unclear: {e}")
    tmp = os.path.join(os.getcwd(), "_t.bin")
    try:
        open(tmp, "wb").write(b"x")
        body, b = encode_multipart([("model", DEFAULT_MODEL), ("prompt", "h"), ("size", "2560x1440"), ("n", "1")], [("image[]", tmp)])
        if f"--{b}".encode() not in body or b'name="model"' not in body or b'name="image[]"' not in body:
            failures.append("multipart fields")
    finally:
        if os.path.isfile(tmp):
            os.remove(tmp)
    td = tempfile.mkdtemp(prefix="tv_")
    try:
        open(os.path.join(td, "thumbnail_v1.png"), "wb").close()
        open(os.path.join(td, "thumbnail_v3.png"), "wb").close()
        open(os.path.join(td, ".gitkeep"), "wb").close()
        if next_thumbnail_version(td) != 4:
            failures.append("versioning")
    finally:
        shutil.rmtree(td, ignore_errors=True)
    td = tempfile.mkdtemp(prefix="tp_")
    try:
        sd, fd = os.path.join(td, "script"), os.path.join(td, "face")
        os.makedirs(sd); os.makedirs(fd)
        open(os.path.join(sd, ".gitkeep"), "w").close()
        open(os.path.join(sd, "notes.log"), "w").close()
        older, newer = os.path.join(sd, "old.txt"), os.path.join(sd, "new.md")
        open(older, "w").write("o"); open(newer, "w").write("n")
        os.utime(older, (1, 1)); os.utime(newer, (2, 2))
        if pick_newest(sd, SCRIPT_EXTS) != newer:
            failures.append("pick script")
        open(os.path.join(fd, ".gitkeep"), "w").close()
        face = os.path.join(fd, "me.PNG"); open(face, "wb").write(b"x")
        if pick_newest(fd, FACE_EXTS) != face:
            failures.append("pick face")
        if pick_newest(fd, SCRIPT_EXTS) is not None:
            failures.append("pick none")
    finally:
        shutil.rmtree(td, ignore_errors=True)
    if failures:
        print("SELF-TEST FAILED:"); [print(" -", f) for f in failures]; sys.exit(1)
    print("SELF-TEST OK")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--face", help="Path to the reference headshot image")
    p.add_argument("--previous", help="Path to the previous thumbnail (for revision passes)")
    p.add_argument("--prompt", help="Image generation / edit instructions")
    p.add_argument("--out", help="Where to write the resulting PNG")
    p.add_argument("--size", default="2560x1440", help="WIDTHxHEIGHT (multiples of 16) or 'auto'")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Image model to use")
    p.add_argument("--env-file", default=".env", help="Path to a .env file holding OPENAI_API_KEY")
    p.add_argument("--dry-run", action="store_true", help="Print request shape without calling the API")
    p.add_argument("--self-test", action="store_true", help="Run offline self-checks and exit")
    p.add_argument("--pick-script", metavar="DIR", nargs="?", const="script", help="Print newest .txt/.md in DIR")
    p.add_argument("--pick-face", metavar="DIR", nargs="?", const="face", help="Print newest image in DIR")
    p.add_argument("--next-version", metavar="DIR", nargs="?", const="output", help="Print next thumbnail_vN from max suffix")
    args = p.parse_args()

    if args.self_test:
        run_self_test(); return
    if args.pick_script is not None:
        path = pick_newest(args.pick_script, SCRIPT_EXTS)
        if not path:
            sys.exit(f"ERROR: no .txt/.md script found in {args.pick_script}/ (skipped .gitkeep/junk).")
        print(path); return
    if args.pick_face is not None:
        path = pick_newest(args.pick_face, FACE_EXTS)
        if not path:
            sys.exit(f"ERROR: no face image found in {args.pick_face}/ (accepted: {', '.join(FACE_EXTS)}; skipped .gitkeep/junk).")
        print(path); return
    if args.next_version is not None:
        print(next_thumbnail_version(args.next_version)); return

    missing = [n for n in ("face", "prompt", "out") if not getattr(args, n)]
    if missing:
        sys.exit("ERROR: required unless using --self-test/--pick-script/--pick-face/--next-version: " + ", ".join(f"--{n}" for n in missing))

    args.size = validate_size(args.size)
    files = [("image[]", args.face)]
    if args.previous:
        files.append(("image[]", args.previous))
    fields = [("model", args.model), ("prompt", args.prompt), ("size", args.size), ("n", "1")]

    if args.dry_run:
        for path in [args.face, args.previous]:
            if path and not os.path.isfile(path):
                print(f"WARNING: input image not found (dry-run continues): {path}", file=sys.stderr)
        print_dry_run(args, fields, files); return

    api_key = load_api_key(args.env_file)
    if not api_key:
        sys.exit(f"ERROR: OPENAI_API_KEY not found (checked env var and {args.env_file}).")
    for path in [args.face, args.previous]:
        if path and not os.path.isfile(path):
            sys.exit(f"ERROR: input image not found: {path}")

    body, boundary = encode_multipart(fields, files)
    req = urllib.request.Request(API_URL, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urllib.request.urlopen(req) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"ERROR: OpenAI API request failed ({e.code}): {e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        sys.exit(f"ERROR: could not reach OpenAI API: {e.reason}")
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: API response was not valid JSON: {e}")

    b64 = extract_b64_json(payload)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as f:
        f.write(base64.b64decode(b64))
    print(f"Saved thumbnail to {args.out}")


if __name__ == "__main__":
    main()
