# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.48,<2", "DracoPy==2.1.0", "numpy>=1.26,<3"]
# ///
"""Link-driven asset retrieval. Session credentials stay inside the process/browser."""
import argparse
import asyncio
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

UUID = r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
ROOT = Path(__file__).resolve().parent
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
ALLOWED = {"assets.meshy.ai", "api.meshy.ai", "www.meshy.ai", "file.hyper3d.com"}


class AssetError(Exception):
    pass


def parse_link(url):
    p = urlsplit(url.strip())
    if p.scheme != "https" or p.username or p.password or p.port not in (None, 443):
        raise AssetError("INVALID_URL: dùng link HTTPS của Meshy hoặc Hyper3D.")
    if p.hostname in {"meshy.ai", "www.meshy.ai"}:
        provider = "meshy"
    elif p.hostname in {"hyper3d.ai", "www.hyper3d.ai", "hyperhuman.deemos.com"}:
        provider = "rodin"
    else:
        raise AssetError("UNSUPPORTED_HOST: link không thuộc Meshy/Rodin.")
    ids = re.findall(UUID, p.path)
    for key, values in parse_qs(p.query).items():
        if key in {"taskId", "task_id", "task_uuid", "uuid", "id"}:
            ids.extend(v for v in values if re.fullmatch(UUID, v))
    ids = list(dict.fromkeys(v.lower() for v in ids))
    if len(ids) != 1:
        raise AssetError("TASK_ID_REQUIRED: gửi link chi tiết một mẫu 3D có task UUID.")
    return provider, ids[0]


def check_asset_url(url):
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname not in ALLOWED or p.username or p.password or p.port not in (None, 443):
        raise AssetError("UNTRUSTED_ASSET_HOST: host tải chưa được hỗ trợ.")


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_asset_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_file(url, dest):
    check_asset_url(url)
    partial = dest.with_name(dest.name + ".part")
    size = 0
    try:
        req = Request(url, headers={"User-Agent": UA, "Referer": "https://www.meshy.ai/" if "meshy.ai" in urlsplit(url).hostname else "https://hyper3d.ai/"})
        with build_opener(SafeRedirect()).open(req, timeout=90) as response, partial.open("xb") as f:
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > 1024 ** 3:
                    raise AssetError("SIZE_LIMIT: asset vượt 1 GiB.")
                f.write(chunk)
        if not size:
            raise AssetError("EMPTY_DOWNLOAD")
        partial.replace(dest)
    except HTTPError as e:
        raise AssetError(f"DOWNLOAD_HTTP_{e.code}") from None
    except (URLError, TimeoutError):
        raise AssetError("DOWNLOAD_NETWORK_ERROR") from None
    finally:
        partial.unlink(missing_ok=True)


def meshy_asset(envelope):
    if envelope.get("code") != "OK" or not isinstance(envelope.get("result"), dict):
        raise AssetError("MESHY_TASK_UNAVAILABLE")
    task = envelope["result"]
    if task.get("status") not in (None, "SUCCEEDED"):
        raise AssetError("TASK_NOT_READY: mẫu chưa tạo xong.")
    result = task.get("result", task)
    for section in ("texture", "generate", "remesh", "draft", "stylize"):
        output = result.get(section)
        if isinstance(output, dict) and output.get("modelUrl"):
            check_asset_url(output["modelUrl"])
            return output["modelUrl"], {"name": task.get("name"), "license": task.get("license"), "section": section, "owner_id": task.get("userId")}
    raise AssetError("NO_MODEL_URL")


def validate_glb(path):
    size = path.stat().st_size
    try:
        with path.open("rb") as f:
            magic, version, declared = struct.unpack("<4sII", f.read(12))
            if magic != b"glTF" or version != 2 or declared != size:
                raise ValueError()
            doc = None
            while f.tell() < size:
                length, kind = struct.unpack("<I4s", f.read(8))
                if length % 4 or f.tell() + length > size:
                    raise ValueError()
                if doc is None:
                    if kind != b"JSON" or length > 64 * 1024 ** 2:
                        raise ValueError()
                    doc = json.loads(f.read(length))
                else:
                    f.seek(length, 1)
            meshes = doc.get("meshes", [])
            if not meshes or not any(m.get("primitives") for m in meshes):
                raise ValueError()
            # Deliverable must not rely on missing external sidecar files.
            for obj in doc.get("buffers", []) + doc.get("images", []):
                if obj.get("uri") and not obj["uri"].startswith("data:"):
                    raise AssetError("EXTERNAL_SIDECARS: GLB cần tài nguyên ngoài chưa tải.")
            return {"format": "glb", "bytes": size, "meshes": len(meshes), "materials": len(doc.get("materials", [])), "images": len(doc.get("images", [])), "extensions": doc.get("extensionsUsed", []), "validation": "container-and-json"}
    except (ValueError, TypeError, AttributeError, struct.error):
        raise AssetError("INVALID_GLB: header/chunks/mesh không hợp lệ.") from None


def new_output_dir(root, provider, task_id):
    parent = root.expanduser().resolve() / provider
    parent.mkdir(parents=True, exist_ok=True)
    for n in range(10000):
        target = parent / (task_id if not n else f"{task_id}-{n}")
        try:
            target.mkdir()
            return target
        except FileExistsError:
            pass
    raise AssetError("OUTPUT_COLLISION_LIMIT")


def ensure_loader(cache):
    cache.mkdir(parents=True, exist_ok=True)
    for name in ("mesh_loader.js", "mesh_loader.wasm"):
        p = cache / name
        if not p.exists():
            download_file(f"https://www.meshy.ai/resource/decrypt/{name}", p)
        with p.open("rb") as f:
            prefix = f.read(256)
        if (name.endswith("wasm") and prefix[:4] != b"\0asm") or (name.endswith("js") and (p.stat().st_size < 1000 or b"<html" in prefix.lower())):
            raise AssetError("INVALID_LOADER: kiểm tra cache Meshy loader.")


def convert_meshy(source, output, cache):
    with source.open("rb") as f:
        magic = f.read(8)
    if magic[:4] == b"glTF":
        shutil.copyfile(source, output)
    elif magic == b"MESHY.AI":
        if not shutil.which("node"):
            raise AssetError("NODE_REQUIRED")
        ensure_loader(cache)
        try:
            result = subprocess.run(["node", str(ROOT / "decrypt.mjs"), str(source.resolve()), str(output.resolve()), str((cache / "mesh_loader.js").resolve()), str((cache / "mesh_loader.wasm").resolve())], capture_output=True, timeout=600, check=False)
        except subprocess.TimeoutExpired:
            raise AssetError("DECODE_TIMEOUT") from None
        if result.returncode:
            raise AssetError("MESHY_DECODE_FAILED: loader có thể đã đổi; kiểm tra phiên bản.")
    else:
        raise AssetError("INVALID_MESHY_MAGIC")
    return validate_glb(output)


def convert_draco(source, output):
    import DracoPy
    import numpy as np
    try:
        mesh = DracoPy.decode(source.read_bytes())
        points, faces = mesh.points, mesh.faces
        if points.ndim != 2 or points.shape[1] != 3 or faces.ndim != 2 or faces.shape[1] != 3 or not len(points) or not len(faces) or not np.isfinite(points).all() or faces.min() < 0 or faces.max() >= len(points):
            raise ValueError()
    except Exception:  # noqa: BLE001 - normalize native decoder failures at the file boundary
        raise AssetError("INVALID_DRACO_MESH") from None
    with output.open("x") as f:
        f.write("# Rodin preview geometry; no materials or textures\n")
        np.savetxt(f, points, fmt="v %.9g %.9g %.9g")
        np.savetxt(f, faces.astype(np.int64) + 1, fmt="f %d %d %d")
    # Read the persisted output rather than reporting solely on the input arrays.
    v = faces_written = 0
    with output.open() as f:
        for line in f:
            v += line.startswith("v ")
            faces_written += line.startswith("f ")
    if v != len(points) or faces_written != len(faces):
        raise AssetError("OBJ_WRITE_MISMATCH")
    return {"format": "obj", "bytes": output.stat().st_size, "vertices": v, "triangles": faces_written, "images": 0, "geometry_only": True, "validation": "finite-vertices-index-bounds-and-output-counts"}


class Session:
    def __init__(self, browser, provider):
        self.browser, self.provider = browser, provider
        self.page = None
        self.auth = {}

    async def open(self):
        if not self.browser.contexts:
            raise AssetError("NO_BROWSER_CONTEXT")
        context = self.browser.contexts[0]
        # A temporary tab uses the selected profile without navigating existing work.
        self.page = await context.new_page()
        def capture(request):
            p = urlsplit(request.url)
            if p.hostname == "www.meshy.ai" and p.path.startswith("/meshyd-api/"):
                headers = request.headers
                if headers.get("authorization", "").startswith("Bearer "):
                    self.auth["authorization"] = headers["authorization"]
                if headers.get("x-device-id"):
                    self.auth["x-device-id"] = headers["x-device-id"]
        self.page.on("request", capture)
        await self.page.goto("https://www.meshy.ai/workspace?sidebar=assets" if self.provider == "meshy" else "https://hyper3d.ai/workspace/rodin", wait_until="domcontentloaded", timeout=60000)
        for _ in range(40):
            if self.provider == "meshy" and self.auth.get("authorization"):
                break
            if self.provider == "rodin":
                token = await self.page.evaluate("localStorage.getItem('token')")
                if token:
                    self.auth["authorization"] = "Bearer " + token
                    break
            await asyncio.sleep(0.5)

    async def api(self, path, body=None, public=False):
        base = "https://www.meshy.ai" if self.provider == "meshy" else "https://api.hyper3d.com/api"
        for attempt in range(2):
            payload = await self.page.evaluate("""async ({url, headers, body}) => {
                const r = await fetch(url, {method: body === null ? 'GET' : 'POST',
                  headers: {...headers, 'content-type':'application/json'},
                  ...(body === null ? {} : {body:JSON.stringify(body)}), signal:AbortSignal.timeout(60000)});
                let data; try {data = await r.json()} catch {data = {error:'NON_JSON_RESPONSE'}};
                return {status:r.status,data};
            }""", {"url": base + path, "headers": {} if public else self.auth, "body": body})
            if payload["status"] == 401 or payload["data"].get("code") == "InvalidToken":
                if attempt or public:
                    raise AssetError("LOGIN_REQUIRED: đăng nhập đúng tài khoản trong Chrome rồi chạy lại.")
                self.auth.clear()
                await self.page.reload(wait_until="domcontentloaded")
                await asyncio.sleep(4)
                if self.provider == "rodin":
                    token = await self.page.evaluate("localStorage.getItem('token')")
                    if token:
                        self.auth["authorization"] = "Bearer " + token
                continue
            if payload["status"] == 403 or payload["data"].get("error") == "PERMISSION_DENIED":
                raise AssetError("PERMISSION_DENIED: tài khoản hiện tại không có quyền với mẫu này.")
            if public and payload["status"] == 404 and payload["data"].get("code") == "NotFound":
                return payload["data"]
            if payload["status"] >= 400:
                raise AssetError(f"API_HTTP_{payload['status']}")
            return payload["data"]

    async def resolve(self, task_id):
        if self.provider == "meshy":
            data = await self.api(f"/meshyd-api/web/public/v2/tasks/{task_id}", public=True)
            if data.get("code") != "OK":
                if not self.auth:
                    raise AssetError("LOGIN_REQUIRED: mẫu không public; cần phiên Meshy.")
                data = await self.api(f"/meshyd-api/web/v2/tasks/{task_id}")
            url, meta = meshy_asset(data)
            return url, "meshy", meta
        if not self.auth:
            raise AssetError("LOGIN_REQUIRED: cần phiên Rodin.")
        data = await self.api("/task/get_download", {"task_uuid": task_id})
        for entry in data.get("list", []):
            if entry.get("url") and not entry.get("error") and (entry.get("name", "").lower().endswith(".glb") or urlsplit(entry["url"]).path.lower().endswith(".glb")):
                check_asset_url(entry["url"])
                return entry["url"], "glb", {"source": "official-download"}
        history = await self.api("/task/rodin_history", {"uuid": task_id, "step": "ModelGenerate"})
        versions = [v for v in history if re.fullmatch(r"v\d+", v)]
        for version in sorted(versions, key=lambda v: int(v[1:]), reverse=True):
            row = history[version]
            if isinstance(row, dict) and row.get("preview_drc"):
                check_asset_url(row["preview_drc"])
                return row["preview_drc"], "drc", {"source": "owned-preview-geometry", "version": version, "geometry_only": True}
        raise AssetError("RODIN_NO_SUPPORTED_OUTPUT: không có GLB hoặc history DRC được cấp quyền; RodinAgentic chưa được hỗ trợ.")


def record(out, provider, task_id, meta, result, output):
    with output.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    info = {"provider": provider, "task_id": task_id, "file": str(output), "sha256": digest, **meta, **result}
    (out / "metadata.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
    return info


async def run(args):
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import async_playwright
    failed = False
    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.connect_over_cdp(args.cdp, timeout=20000)
        except PlaywrightError:
            raise AssetError("CDP_UNAVAILABLE: mở Chrome debug đúng profile/endpoint.") from None
        for link in args.urls:
            session = None
            try:
                provider, task_id = parse_link(link)
                session = Session(browser, provider)
                await session.open()
                out = None
                for attempt in range(2):
                    url, kind, meta = await session.resolve(task_id)
                    if out is None:
                        out = new_output_dir(args.output, provider, task_id)
                    source = out / ("source." + kind)
                    try:
                        await asyncio.to_thread(download_file, url, source)
                        break
                    except AssetError as e:
                        if attempt or str(e) not in {"DOWNLOAD_HTTP_401", "DOWNLOAD_HTTP_403"}:
                            raise
                output = out / ("model.obj" if kind == "drc" else "model.glb")
                if kind == "drc":
                    result = await asyncio.to_thread(convert_draco, source, output)
                else:
                    result = await asyncio.to_thread(convert_meshy, source, output, args.cache.expanduser().resolve())
                print(json.dumps({"ok": True, **record(out, provider, task_id, meta, result, output)}, ensure_ascii=False), flush=True)
            except AssetError as e:
                failed = True
                print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), flush=True)
            except Exception as e:  # noqa: BLE001 - batch boundary; redact URLs and continue other links
                # Browser/network exceptions can contain signed URLs or request headers.
                failed = True
                print(json.dumps({"ok": False, "error": "UNEXPECTED_" + type(e).__name__}), flush=True)
            finally:
                if session and session.page:
                    await session.page.close()
        # Do not browser.close(): this is the user's existing browser.
    return int(failed)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("urls", nargs="*")
    p.add_argument("--cdp", default="http://127.0.0.1:9222")
    p.add_argument("--output", type=Path, default=Path.home() / "Downloads/3d-assets")
    p.add_argument("--cache", type=Path, default=Path.home() / ".cache/meshy-rodin-download")
    p.add_argument("--inspect", type=Path, help="Validate local GLB without browser")
    p.add_argument("--convert", type=Path, help="Convert existing .meshy/.drc to --destination")
    p.add_argument("--destination", type=Path)
    args = p.parse_args()
    try:
        if args.inspect:
            print(json.dumps(validate_glb(args.inspect)))
            return 0
        if args.convert:
            if not args.destination or args.destination.exists() or args.destination.resolve() == args.convert.resolve():
                raise AssetError("DESTINATION_REQUIRED: chọn file đích mới.")
            args.destination.parent.mkdir(parents=True, exist_ok=True)
            result = convert_draco(args.convert, args.destination) if args.convert.suffix == ".drc" else convert_meshy(args.convert, args.destination, args.cache.expanduser().resolve())
            print(json.dumps(result))
            return 0
        if not args.urls:
            p.error("Cần ít nhất một link mẫu 3D.")
        for url in args.urls:
            parse_link(url)
        return asyncio.run(run(args))
    except AssetError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
