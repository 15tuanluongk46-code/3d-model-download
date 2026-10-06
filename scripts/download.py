#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""3d-model-download — tải model 3D từ nhiều nguồn về thư mục cục bộ.

Nguồn hỗ trợ:
  - meshy.ai / hyper3d.ai       -> delegate sang skill meshy-rodin-download
  - poly.pizza/m/<slug>         -> static GLB từ static.poly.pizza (không cần login)
  - sketchfab.com/3d-models/...  -> GLB qua public viewer extractor (không cần login/Pro)
  - URL file trực tiếp          -> .glb/.gltf/.obj/.stl/.fbx/.ply/.usdz
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import io
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from asset_io import AssetError, atomic_json, clean_data, copy_bounded, inspect_glb, redact, run_process

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
SIZE_LIMIT = 1 << 30  # 1 GiB
MESHY_SCRIPT = Path.home() / ".agents/skills/meshy-rodin-download/scripts/download.py"
MESHY_HOSTS = {
    "meshy.ai",
    "www.meshy.ai",
    "hyper3d.ai",
    "www.hyper3d.ai",
    "hyperhuman.deemos.com",
}
POLY_HOSTS = {"poly.pizza", "www.poly.pizza"}
SKETCHFAB_HOSTS = {"sketchfab.com", "www.sketchfab.com"}
SKETCHFAB_EXTRACTOR = Path(__file__).resolve().parent / "sketchfab" / "extract_public_model.py"
SKETCHFAB_UID_RE = re.compile(r"[a-f0-9]{32}")
SKETCHFAB_SLUG_RE = re.compile(r"/3d-models/([^/?#]+)")
DIRECT_EXTS = {".glb", ".gltf", ".obj", ".stl", ".fbx", ".ply", ".usdz"}

SOURCES = """Nguồn hỗ trợ:
  - meshy.ai (link /3d-models/...)              -> delegate skill meshy-rodin-download (không cần Pro)
  - hyper3d.ai / hyperhuman.deemos.com (Rodin)  -> delegate skill meshy-rodin-download
  - poly.pizza/m/<slug>                         -> GLB (CC0/CC-BY) từ static.poly.pizza
  - static.poly.pizza/<uuid>.glb                -> tải thẳng
  - sketchfab.com/3d-models/<slug>-<uid>        -> GLB qua Sketchfab public viewer (không cần login/Pro, kèm attribution)
  - URL file trực tiếp: .glb .gltf .obj .stl .fbx .ply .usdz
Chưa hỗ trợ (xem references/sources.md): Thingiverse, CGTrader, Fab, Free3D, TurboSquid."""

POLY_PATTERNS = {
    "name": r'"Name":"([^"]+)"',
    "likes": r'"Likes":(\d+)',
    "downloads": r'"Downloads":"([^"]+)"',
    "views": r'"Views":"([^"]+)"',
    "creator": r'"Username":"([^"]+)"',
    "resource_id": r'"ResourceID":"([0-9a-fA-F-]{36})"',
}
POLY_LICENSE = r'(Public Domain|CC0|CC[- ]BY[^"<]{0,4})'
POLY_TITLE = r"<title[^>]*>([^<]+)</title>"
POLY_SLUG = re.compile(r"^/m/([A-Za-z0-9_-]+)/?$")


class TransferSize(int):
    def __new__(cls, size, digest):
        obj = super().__new__(cls, size)
        obj.sha256 = digest
        return obj


def validate_https(url, allow_hosts=None):
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https":
        raise AssetError("INSECURE_LINK: chỉ chấp nhận https — " + redact(url))
    if p.username or p.password:
        raise AssetError("INSECURE_LINK: link chứa credential")
    if p.port not in (None, 443):
        raise AssetError(f"UNTRUSTED_REDIRECT: port {p.port} không được phép")
    host = (p.hostname or "").lower()
    if not host:
        raise AssetError('INSECURE_LINK: missing hostname')
    if allow_hosts is not None and host not in allow_hosts:
        raise AssetError(f"UNTRUSTED_REDIRECT: host {host} nằm ngoài whitelist")
    return p


def classify(url):
    p = validate_https(url)
    host = (p.hostname or "").lower()
    if host in MESHY_HOSTS:
        return "meshy", None
    if host in SKETCHFAB_HOSTS:
        return "sketchfab", None
    if host in POLY_HOSTS:
        return "poly", None
    if host == "static.poly.pizza" and p.path.lower().endswith(".glb"):
        return "poly-static", None
    if Path(urllib.parse.unquote(p.path)).suffix.lower() in DIRECT_EXTS:
        return "direct", None
    raise AssetError("UNSUPPORTED_LINK: " + url + " — xem `--sources`")


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, allow_hosts=None):
        super().__init__()
        self.allow_hosts = allow_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_https(newurl, self.allow_hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener(allow_hosts=None):
    return urllib.request.build_opener(SafeRedirect(allow_hosts))


def http_get(url, referer=None, allow_hosts=None, timeout=90):
    validate_https(url, allow_hosts)
    deadline = time.monotonic() + timeout
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    try:
        with _opener(allow_hosts).open(req, timeout=min(30, timeout)) as r:
            output = io.BytesIO()
            copy_bounded(r, output, limit=16 << 20,
                         expected=int(r.headers['Content-Length']) if r.headers.get('Content-Length') else None,
                         deadline=deadline)
            return output.getvalue()
    except urllib.error.HTTPError as e:
        raise AssetError(f"HTTP_{e.code}: {url}") from e
    except AssetError:
        raise
    except Exception as e:
        raise AssetError(f"NETWORK_ERROR: {e}") from e


def download_file(url, dest, referer=None, allow_hosts=None, timeout=240):
    validate_https(url, allow_hosts)
    dest = Path(dest)
    part = dest.with_name(dest.name + ".part")
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    allow_hosts = allow_hosts or {urllib.parse.urlsplit(url).hostname}
    deadline = time.monotonic() + timeout
    try:
        with _opener(allow_hosts).open(req, timeout=min(30, timeout)) as r, open(part, "xb") as f:
            total, digest = copy_bounded(r, f, limit=SIZE_LIMIT,
                expected=int(r.headers['Content-Length']) if r.headers.get('Content-Length') else None,
                deadline=deadline)
    except urllib.error.HTTPError as e:
        part.unlink(missing_ok=True)
        raise AssetError(f"HTTP_{e.code}: {url}") from e
    except AssetError:
        part.unlink(missing_ok=True)
        raise
    except Exception as e:
        part.unlink(missing_ok=True)
        raise AssetError(f"NETWORK_ERROR: {e}") from e
    if total == 0:
        part.unlink(missing_ok=True)
        raise AssetError("EMPTY_DOWNLOAD: " + url)
    part.replace(dest)
    return TransferSize(total, digest)


def new_output_dir(base, provider, ident):
    root = Path(base).expanduser().resolve() / provider
    root.mkdir(parents=True, exist_ok=True)
    ident = re.sub(r'[^A-Za-z0-9._-]+', '_', ident).strip('.')[:120] or 'asset'
    n = 0
    while True:
        candidate = root / (ident if n == 0 else f'{ident}-{n}')
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            n += 1


def sha256_of(path):
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write_metadata(out_dir, data):
    atomic_json(out_dir / 'metadata.json', data)


def finish(out, data):
    data.update(output_dir=str(out.resolve()), file_path=str((out / data['file']).resolve()),
                metadata_path=str((out / 'metadata.json').resolve()))
    data.setdefault('license', 'unknown')
    data['license'] = data.get('license') or 'unknown'
    data.setdefault('warnings', [])
    data.setdefault('status', 'partial' if data['warnings'] else 'complete')
    data = clean_data(data)
    write_metadata(out, data)
    print(json.dumps(data, ensure_ascii=False), flush=True)
    return True


def checked_glb(path):
    try:
        return inspect_glb(path)
    except Exception:
        path.unlink(missing_ok=True)
        raise


def parse_poly_page(html):
    out = {}
    for key, pattern in POLY_PATTERNS.items():
        m = re.search(pattern, html)
        if not m:
            continue
        out[key] = int(m.group(1)) if key == "likes" else m.group(1)
    if not out.get("name"):
        t = re.search(POLY_TITLE, html)
        if t:
            out["name"] = t.group(1).split(" - Free 3D Model")[0].strip()
    lic = re.search(POLY_LICENSE, html)
    if lic:
        out["license"] = lic.group(1)
    return out


def handle_poly(link, args):
    p = validate_https(link)
    m = POLY_SLUG.match(urllib.parse.unquote(p.path))
    if not m:
        raise AssetError("POLY_SLUG_REQUIRED: cần link dạng https://poly.pizza/m/<slug>")
    slug = m.group(1)
    html = http_get(
        link, referer="https://poly.pizza/", allow_hosts=POLY_HOSTS, timeout=args.timeout
    ).decode("utf-8", "replace")
    info = parse_poly_page(html)
    rid = info.get("resource_id")
    if not rid:
        raise AssetError("POLY_RESOURCE_NOT_FOUND: không tìm thấy ResourceID trong trang " + link)
    out = new_output_dir(args.output, "poly-pizza", slug)
    url = f"https://static.poly.pizza/{rid}.glb"
    size = download_file(url, out / "model.glb", referer=link, allow_hosts={"static.poly.pizza"}, timeout=args.timeout)
    quality = checked_glb(out / 'model.glb')
    data = {
        "ok": True,
        "provider": "poly-pizza",
        "id": slug,
        "name": info.get("name"),
        "file": "model.glb",
        "bytes": size,
        "sha256": getattr(size, 'sha256', None) or sha256_of(out / 'model.glb'),
        "quality": quality,
        "format": "glb",
        "likes": info.get("likes"),
        "downloads": info.get("downloads"),
        "views": info.get("views"),
        "creator": info.get("creator"),
        "license": info.get("license"),
        "resource_id": rid,
        "source_url": link,
    }
    return finish(out, data)


def handle_direct(link, args, provider="direct"):
    p = validate_https(link)
    name = Path(urllib.parse.unquote(p.path)).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", name) or "asset"
    out = new_output_dir(args.output, provider, stem)
    name = stem
    dest = out / name
    size = download_file(link, dest, referer=link, timeout=args.timeout)
    data = {
        "ok": True,
        "provider": provider,
        "id": stem,
        "file": name,
        "bytes": size,
        "sha256": getattr(size, 'sha256', None) or sha256_of(dest),
        "format": Path(name).suffix.lstrip(".").lower(),
        "source_url": link,
    }
    if dest.suffix.lower() == ".glb":
        data['quality'] = checked_glb(dest)
        data['external_dependencies'] = data['quality']['external_dependencies']
    elif dest.suffix.lower() == '.gltf':
        if dest.stat().st_size > 32 << 20:
            raise AssetError('SIZE_LIMIT: glTF JSON exceeds 32 MiB')
        doc = json.loads(dest.read_text())
        data['external_dependencies'] = [x['uri'] for x in doc.get('buffers', []) + doc.get('images', []) if x.get('uri') and not x['uri'].startswith('data:')]
    elif dest.suffix.lower() == '.obj':
        deps = []
        with dest.open(errors='replace') as f:
            for line in f:
                if line.lstrip().startswith('mtllib '):
                    deps.append(line.strip()[7:].strip())
        data['external_dependencies'] = deps
    if data.get('external_dependencies'):
        data['warnings'] = ['EXTERNAL_DEPENDENCIES: companion files were not downloaded']
    return finish(out, data)


def handle_sketchfab(link, args):
    validate_https(link)
    m = re.search(r'(?:/3d-models/(?:[^/]+-)?|/models/)([a-f0-9]{32})(?:/embed)?/?$', urllib.parse.urlsplit(link).path, re.I)
    if not m:
        raise AssetError(
            "SKETCHFAB_UID_REQUIRED: cần link dạng https://sketchfab.com/3d-models/<slug>-<uid>"
        )
    uid = m.group(1).lower()
    slug_m = SKETCHFAB_SLUG_RE.search(urllib.parse.unquote(urllib.parse.urlsplit(link).path))
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", slug_m.group(1) if slug_m else uid)[:80] or uid
    if not SKETCHFAB_EXTRACTOR.exists():
        raise AssetError("SKETCHFAB_EXTRACTOR_MISSING: " + str(SKETCHFAB_EXTRACTOR))
    out = new_output_dir(args.output, "sketchfab", slug)
    glb = out / "model.glb"
    cmd = [sys.executable, str(SKETCHFAB_EXTRACTOR), link, '--output', str(glb),
           '--timeout', str(args.timeout), '--texture-size', str(args.texture_size)]
    if args.no_textures:
        cmd.append('--no-textures')
    if args.no_animations:
        cmd.append('--no-animations')
    try:
        proc = run_process(cmd, args.timeout + 10)
    except AssetError as e:
        raise AssetError('SKETCHFAB_' + str(e)) from e
    except FileNotFoundError as e:
        raise AssetError("SKETCHFAB_EXTRACTOR_MISSING: " + str(SKETCHFAB_EXTRACTOR)) from e
    try:
        report = json.loads(proc.stdout)
    except ValueError:
        report = {}
    if proc.returncode != 0 or not glb.exists() or not report.get('ok'):
        glb.unlink(missing_ok=True)
        raise AssetError('SKETCHFAB_' + report.get('error', f'EXTRACT_FAILED: exit {proc.returncode}'))
    quality = checked_glb(glb)
    attr_path = glb.with_name(glb.name + ".attribution.json")
    attr = {}
    if attr_path.exists():
        try:
            attr = json.loads(attr_path.read_text(encoding="utf-8"))
        except ValueError:
            attr = {}
    data = {
        "ok": True,
        "provider": "sketchfab",
        "id": slug,
        "uid": uid,
        "name": attr.get("name") or slug,
        "file": "model.glb",
        "bytes": glb.stat().st_size,
        "sha256": report.get('sha256') or sha256_of(glb),
        "quality": quality,
        "diagnostics": report.get('diagnostics', {}),
        "warnings": report.get('warnings', []) + ([] if attr else ['ATTRIBUTION_MISSING']),
        "timings": report.get('timings', {}),
        "peak_rss_kib": report.get('peak_rss_kib'),
        "peak_rss_scope": "extractor-python-process-only",
        "network_bytes": report.get('network_bytes'),
        "format": "glb",
        "creator": attr.get("author"),
        "license": attr.get("license"),
        "license_url": attr.get("licenseUrl"),
        "thumbnail_url": attr.get("thumbnailUrl"),
        "source_url": link,
        "attribution": attr_path.name if attr_path.exists() else None,
        "note": "Tải qua Sketchfab public viewer — chỉ dùng cá nhân, giữ attribution và tôn trọng license của tác giả.",
    }
    return finish(out, data)


def run_meshy(link, args):
    if not MESHY_SCRIPT.exists():
        raise AssetError("MESHY_SKILL_MISSING: " + str(MESHY_SCRIPT))
    cmd = ["uv", "run", str(MESHY_SCRIPT), link, "--output", str(args.output), "--cdp", args.cdp]
    try:
        proc = run_process(cmd, args.timeout)
    except FileNotFoundError as e:
        raise AssetError("UV_REQUIRED: cần cài uv (https://docs.astral.sh/uv/)") from e
    try:
        data = json.loads(proc.stdout)
    except ValueError as e:
        raise AssetError('MESHY_HELPER_FAILED: helper did not return one JSON result') from e
    if proc.returncode or not data.get('ok'):
        raise AssetError('MESHY_HELPER_FAILED: ' + str(data.get('error', proc.returncode)))
    if not isinstance(data.get('file'), str):
        raise AssetError('MESHY_HELPER_FAILED: missing output file')
    path = Path(data['file']).expanduser().resolve()
    if not path.is_file() or not path.stat().st_size:
        raise AssetError('MESHY_HELPER_FAILED: output missing or empty')
    if path.suffix.lower() == '.glb':
        data['quality'] = inspect_glb(path)
    data.update(file=path.name, bytes=path.stat().st_size,
                sha256=sha256_of(path), format=path.suffix.lstrip('.').lower())
    return finish(path.parent, data)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Tải model 3D từ Meshy / Hyper3D Rodin / Poly Pizza / Sketchfab / URL file trực tiếp."
    )
    ap.add_argument("urls", nargs="*", help="link model 3D (nhiều link cùng lúc được)")
    ap.add_argument(
        "--output",
        type=Path,
        default=Path.home() / "Downloads/3d-assets",
        help="thư mục gốc lưu model (mặc định ~/Downloads/3d-assets)",
    )
    ap.add_argument("--cdp", default="http://127.0.0.1:9222", help="Chrome debug endpoint")
    ap.add_argument("--sources", action="store_true", help="in danh sách nguồn hỗ trợ")
    ap.add_argument('--timeout', type=float, default=240, help='deadline seconds per extractor/transfer')
    ap.add_argument('--texture-size', type=int, choices=[0, 2048, 4096], default=2048, help='Sketchfab texture variant preference; 0 = original')
    ap.add_argument('--no-textures', action='store_true')
    ap.add_argument('--no-animations', action='store_true', help='skip animation curves; preserve default pose and rig')
    args = ap.parse_args(argv)
    if args.timeout <= 0:
        ap.error('--timeout must be positive')
    if args.sources:
        print(SOURCES)
        return 0
    if not args.urls:
        ap.error("cần ít nhất 1 link (hoặc dùng --sources để xem nguồn hỗ trợ)")
    failed = 0
    for link in args.urls:
        try:
            kind, _ = classify(link)
            if kind == "meshy":
                ok = run_meshy(link, args)
            elif kind == "poly":
                ok = handle_poly(link, args)
            elif kind in ("poly-static", "direct"):
                ok = handle_direct(link, args)
            elif kind == "sketchfab":
                ok = handle_sketchfab(link, args)
            else:
                raise AssetError("UNSUPPORTED_LINK: " + link)
        except AssetError as e:
            ok = False
            print(
                json.dumps({"ok": False, "link": redact(link), "error": redact(e)}, ensure_ascii=False),
                flush=True,
            )
        except Exception as e:
            ok = False
            print(
                json.dumps(
                    {"ok": False, "link": redact(link), "error": "UNEXPECTED_" + type(e).__name__},
                    ensure_ascii=False,
                ),
                flush=True,
            )
        failed += 0 if ok else 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
