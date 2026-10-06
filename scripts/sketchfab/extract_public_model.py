#!/usr/bin/env python3
"""Extract a public Sketchfab viewer model to a corrected self-contained GLB.

This intentionally uses viewer resources rather than Sketchfab's official
Download API.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from asset_io import AssetError, atomic_json, clean_data, redact


def model_uid(value: str) -> str:
    path = urllib.parse.urlsplit(value).path if '://' in value else value
    match = re.fullmatch(r'(?:/3d-models/(?:[^/]+-)?|/models/)?([a-f0-9]{32})(?:/embed)?/?', path, re.I)
    if not match:
        raise AssetError('UID_REQUIRED: expected a Sketchfab model URL or UID')
    return match.group(1).lower()


def attribution_for(model_url: str, output: Path, metadata=None) -> dict:
    uid = model_uid(model_url)
    metadata = metadata if isinstance(metadata, dict) else {}
    user = metadata.get("user") or {}
    license_data = metadata.get("license")
    if isinstance(license_data, dict):
        license_name = license_data.get("label") or license_data.get("slug") or "unknown"
        license_url = license_data.get("url")
    else:
        license_name = license_data or "unknown"
        license_url = None

    images = (metadata.get("thumbnails") or {}).get("images") or []
    usable_images = [image for image in images if image.get("url")]
    thumbnail = max(
        (image for image in usable_images if int(image.get("width") or 0) <= 1024),
        key=lambda image: int(image.get("width") or 0),
        default=None,
    ) or min(
        usable_images,
        key=lambda image: int(image.get("width") or 0),
        default={},
    )
    canonical_url = metadata.get("viewerUrl") or (
        model_url if model_url.startswith("http") else f"https://sketchfab.com/3d-models/{uid}"
    )
    return {
        "uid": uid,
        "name": metadata.get("name") or output.stem,
        "author": user.get("displayName") or user.get("username") or "Unknown author",
        "authorUrl": user.get("profileUrl") or user.get("url"),
        "license": license_name,
        "licenseUrl": license_url,
        "modelUrl": canonical_url,
        "thumbnailUrl": thumbnail.get("url"),
        "source": "public Sketchfab viewer resources",
        "glbBytes": output.stat().st_size,
    }


def write_attribution(model_url: str, output: Path, metadata=None) -> Path:
    sidecar = output.with_suffix(f"{output.suffix}.attribution.json")
    atomic_json(sidecar, attribution_for(model_url, output, metadata))
    return sidecar


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_url", help="Sketchfab model URL or 32-character UID")
    parser.add_argument("-o", "--output", type=Path, required=True, help="output GLB path")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument('--timeout', type=float, default=240)
    parser.add_argument('--texture-size', type=int, choices=[0, 2048, 4096], default=2048)
    parser.add_argument('--no-textures', action='store_true')
    parser.add_argument('--no-animations', action='store_true')
    parser.add_argument("--no-launch", action="store_true")
    args = parser.parse_args()
    from serve_public_extractor import extract

    try:
        if args.timeout <= 0:
            raise AssetError('INVALID_TIMEOUT: must be positive')
        result = extract(args.model_url, args.output, port=args.port, launch=not args.no_launch,
                         timeout=args.timeout, texture_size=args.texture_size,
                         textures=not args.no_textures, animations=not args.no_animations)
    except Exception as error:
        result = {'ok': False, 'error': redact(error) if isinstance(error, AssetError) else type(error).__name__}
    print(json.dumps(clean_data(result)), flush=True)
    return 0 if result.get('ok') else 1


if __name__ == "__main__":
    raise SystemExit(main())
