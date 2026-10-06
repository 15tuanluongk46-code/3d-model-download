#!/usr/bin/env python3
"""Authenticated loopback transport with bounded raw GLB writes and owned Chrome."""
from __future__ import annotations

import io
import json
import os
import resource
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from extract_public_model import model_uid, write_attribution
from asset_io import AssetError, clean_data, copy_bounded, inspect_glb, redact, stop_process

ROOT = Path(__file__).resolve().parent / 'vendor' / 'sketchfab_downloader_extension'
ALLOWED_HOSTS = {'sketchfab.com', 'www.sketchfab.com', 'media.sketchfab.com', 'static.sketchfab.com'}
MAX_BYTES = 1 << 30


def validate_target(url):
    try:
        p = urllib.parse.urlsplit(url)
        valid = p.scheme == 'https' and p.hostname in ALLOWED_HOSTS and not p.username and not p.password and p.port in (None, 443)
    except ValueError:
        valid = False
    if not valid:
        raise AssetError('UNTRUSTED_REDIRECT: unsupported proxy target')


class ProxyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_target(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class ExtractionServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, model, output, *, port=0, timeout=240):
        self.model = model
        self.output = Path(output).resolve()
        self.token = secrets.token_urlsafe(32)
        self.deadline = time.monotonic() + timeout
        self.done = threading.Event()
        self.lock = threading.Lock()
        self.payload = {}
        self.result = {}
        self.network_bytes = 0
        self.network_lock = threading.Lock()
        self.proxy_slots = threading.BoundedSemaphore(6)
        super().__init__(('127.0.0.1', port), Handler)

    @property
    def origin(self):
        return f'http://127.0.0.1:{self.server_port}'


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, *_):
        pass  # Do not log signed URLs or the callback token.

    def setup(self):
        super().setup()
        self.connection.settimeout(max(.1, min(15, self.server.deadline - time.monotonic())))

    def authorized(self):
        host = f'127.0.0.1:{self.server.server_port}'
        token = self.headers.get('X-Extractor-Token', '')
        valid = (self.headers.get('Host') == host and
                 self.headers.get('Origin') in (None, self.server.origin) and
                 secrets.compare_digest(token, self.server.token))
        if not valid:
            self.send_error(403)
        return valid

    def respond(self, code):
        self.send_response(code)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def length(self, limit):
        try:
            length = int(self.headers.get('Content-Length', '-1'))
        except ValueError:
            length = -1
        if length < 0 or self.headers.get('Transfer-Encoding'):
            self.send_error(411)
            return None
        if length > limit:
            self.send_error(413)
            return None
        return length

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path != '/proxy':
            if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
                return self.send_error(403)
            if parsed.path.endswith('/'):
                return self.send_error(404)
            return super().do_GET()
        if not self.authorized():
            return
        if not self.server.proxy_slots.acquire(blocking=False):
            return self.send_error(429)
        try:
            target = urllib.parse.parse_qs(parsed.query).get('url', [''])[0]
            validate_target(target)
            remaining = self.server.deadline - time.monotonic()
            if remaining <= 0:
                raise AssetError('TIMEOUT: proxy deadline')
            request = urllib.request.Request(target, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://sketchfab.com/'})
            opener = urllib.request.build_opener(ProxyRedirect())
            # Spool to disk rather than retaining another copy of large media in Python RAM.
            with opener.open(request, timeout=min(15, remaining)) as response, tempfile.TemporaryFile() as spool:
                length = response.headers.get('Content-Length')
                count, _ = copy_bounded(response, spool, limit=MAX_BYTES,
                    expected=int(length) if length else None, deadline=self.server.deadline)
                with self.server.network_lock:
                    self.server.network_bytes += count
                    if self.server.network_bytes > 4 * MAX_BYTES:
                        raise AssetError('SIZE_LIMIT: aggregate network limit exceeded')
                spool.seek(0)
                self.send_response(200)
                self.send_header('Content-Type', response.headers.get_content_type())
                self.send_header('Content-Length', str(count))
                self.end_headers()
                shutil.copyfileobj(spool, self.wfile, 1 << 20)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as error:
            print('proxy: ' + redact(error), file=sys.stderr, flush=True)
            self.send_error(502, 'proxy transfer failed')
        finally:
            self.server.proxy_slots.release()

    def do_POST(self):
        if not self.authorized():
            return
        path = urllib.parse.urlsplit(self.path).path
        if path not in {'/progress', '/error', '/metadata', '/save'}:
            return self.send_error(404)
        length = self.length(MAX_BYTES if path == '/save' else 1 << 20)
        if length is None:
            return
        part = None
        try:
            with self.server.lock:
                if self.server.done.is_set():
                    return self.respond(409)
                if time.monotonic() >= self.server.deadline:
                    raise AssetError('TIMEOUT: callback deadline')
                if path != '/save':
                    body = io.BytesIO()
                    copy_bounded(self.rfile, body, limit=1 << 20, expected=length, deadline=self.server.deadline)
                    text = body.getvalue().decode('utf-8')
                    if path == '/metadata':
                        payload = json.loads(text)
                        if not isinstance(payload, dict) or not isinstance(payload.get('metadata', {}), dict) or not isinstance(payload.get('warnings', []), list):
                            raise AssetError('INVALID_METADATA: malformed payload')
                        self.server.payload = clean_data(payload)
                    elif path == '/error':
                        self.server.result = {'ok': False, 'error': 'EXTRACT_FAILED: ' + redact(text)[:4000]}
                        self.server.done.set()
                    else:
                        print(redact(text), file=sys.stderr, flush=True)
                    return self.respond(204)
                output = self.server.output
                if output.exists():
                    return self.respond(409)
                fd, temp = tempfile.mkstemp(prefix='.' + output.name, suffix='.part', dir=output.parent)
                part = Path(temp)
                with os.fdopen(fd, 'wb') as f:
                    count, digest = copy_bounded(self.rfile, f, limit=MAX_BYTES, expected=length, deadline=self.server.deadline)
                    f.flush()
                    os.fsync(f.fileno())
                quality = inspect_glb(part)
                if time.monotonic() >= self.server.deadline:
                    raise AssetError('TIMEOUT: validation deadline')
                os.replace(part, output)
                payload = self.server.payload
                write_attribution(self.server.model, output, payload.get('metadata', {}))
                self.server.result = {'ok': True, 'file_path': str(output), 'bytes': count, 'sha256': digest,
                    'quality': quality, 'diagnostics': payload.get('diagnostics', {}),
                    'warnings': payload.get('warnings', []), 'timings': payload.get('timings', {})}
                self.respond(204)
                self.server.done.set()
        except Exception as error:
            self.server.result = {'ok': False, 'error': redact(error) if isinstance(error, AssetError) else type(error).__name__}
            # No successful final artifact on a failed save.
            if path == '/save' and part is not None:
                self.server.output.unlink(missing_ok=True)
            self.send_error(422, 'invalid extraction payload')
        finally:
            if part is not None:
                part.unlink(missing_ok=True)


def extract(model_url, output_path, port=0, launch=True, timeout=240, texture_size=2048, textures=True, animations=True):
    uid = model_uid(model_url)
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise AssetError('OUTPUT_EXISTS: choose a new output path')
    start = time.monotonic()
    server = ExtractionServer(uid, output, port=port, timeout=timeout)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    browser = profile = None
    previous = {}
    try:
        if threading.current_thread() is threading.main_thread():
            def interrupted(signum, frame):
                raise AssetError('INTERRUPTED: extraction cancelled')
            for sig in (signal.SIGTERM, signal.SIGINT):
                previous[sig] = signal.signal(sig, interrupted)
        thread.start()
        params = urllib.parse.urlencode({'model': uid, 'textureSize': texture_size, 'textures': int(textures), 'animations': int(animations)})
        url = f'{server.origin}/headless.html?{params}#{server.token}'
        if launch:
            executable = next((shutil.which(n) for n in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser') if shutil.which(n)), None)
            if not executable:
                raise AssetError('NO_BROWSER: Chrome or Chromium is required')
            profile = tempfile.TemporaryDirectory(prefix='sketchfab-extractor-chrome-')
            browser = subprocess.Popen([executable, '--headless=new', '--disable-background-networking',
                '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-extensions',
                '--no-first-run', '--no-default-browser-check', f'--user-data-dir={profile.name}', f'--app={url}'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            print(f'Started isolated extractor on port {server.server_port}', file=sys.stderr, flush=True)
        else:
            print(f'Open this local one-time URL: {url}', file=sys.stderr, flush=True)
        while not server.done.wait(.1):
            if time.monotonic() >= server.deadline:
                raise AssetError('TIMEOUT: extractor deadline exceeded')
            if browser is not None and browser.poll() is not None:
                raise AssetError(f'BROWSER_EXIT: Chrome exited {browser.returncode}')
        result = server.result
        result.setdefault('timings', {})['total_seconds'] = round(time.monotonic() - start, 3)
        result['network_bytes'] = server.network_bytes
        result['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return result
    finally:
        server.deadline = 0
        if browser is not None:
            stop_process(browser)
        if thread.is_alive():
            server.shutdown()
            thread.join(timeout=2)
        server.server_close()
        if profile is not None:
            profile.cleanup()
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == '__main__':
    from extract_public_model import main
    raise SystemExit(main())
