#!/usr/bin/env python3
"""Generate images with Google's Gemini image model ("Nano Banana").

The API key is NOT stored here. In Claude Code cloud sessions it is added by the
network proxy (environment Network secret for generativelanguage.googleapis.com,
header x-goog-api-key). On your own computer, set GEMINI_API_KEY instead.

Examples:
  python3 tools/nano_banana.py "Photorealistic living room, warm oak floors..." \
      --ref sketchup_view.png --ref moodboard.jpg --aspect 16:9 --out renders/living.png
  python3 tools/nano_banana.py --list-models
"""
import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request

API = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = os.environ.get("NANO_BANANA_MODEL", "gemini-2.5-flash-image")


def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method)
    # Real key comes from the proxy (cloud) or GEMINI_API_KEY (local).
    req.add_header("x-goog-api-key", os.environ.get("GEMINI_API_KEY", "injected-by-proxy"))
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=300) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"API error {e.code}: {e.read().decode(errors='replace')[:2000]}")


def list_models():
    res = call("GET", "/models?pageSize=200")
    for m in res.get("models", []):
        name = m["name"].removeprefix("models/")
        if "image" in name:
            print(name)


def generate(prompt, refs, model, aspect, out):
    parts = [{"text": prompt}]
    for path in refs:
        mime = mimetypes.guess_type(path)[0] or "image/png"
        with open(path, "rb") as f:
            parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(f.read()).decode()}})
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    if aspect:
        body["generationConfig"]["imageConfig"] = {"aspectRatio": aspect}
    res = call("POST", f"/models/{model}:generateContent", body)

    saved = 0
    base, ext = os.path.splitext(out)
    for cand in res.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            blob = part.get("inlineData") or part.get("inline_data")
            if blob:
                path = out if saved == 0 else f"{base}_{saved + 1}{ext}"
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                with open(path, "wb") as f:
                    f.write(base64.b64decode(blob["data"]))
                print(f"saved {path}")
                saved += 1
            elif part.get("text"):
                print(part["text"])
    if not saved:
        sys.exit("No image returned. Response: " + json.dumps(res)[:2000])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("prompt", nargs="?")
    p.add_argument("--ref", action="append", default=[], help="reference image (SketchUp view, plan, mood board); repeatable")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--aspect", default="16:9", help="e.g. 16:9, 4:3, 1:1, 3:4, 9:16; empty for model default")
    p.add_argument("--out", default="renders/render.png")
    p.add_argument("--list-models", action="store_true", help="list image models available to your key")
    a = p.parse_args()
    if a.list_models:
        return list_models()
    if not a.prompt:
        p.error("prompt is required")
    generate(a.prompt, a.ref, a.model, a.aspect, a.out)


if __name__ == "__main__":
    main()
