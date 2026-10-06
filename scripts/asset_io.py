"""Bounded transfers, container inspection and subprocess ownership."""
from __future__ import annotations

import hashlib
import json
import os
import re
import selectors
import signal
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse


class AssetError(Exception):
    pass


def redact(value):
    def url(match):
        try:
            p = urllib.parse.urlsplit(match.group())
            return urllib.parse.urlunsplit((p.scheme, p.hostname or '', p.path, '', ''))
        except ValueError:
            return '[invalid URL]'
    return re.sub(r'https?://[^\s"<>]+', url, str(value))


def clean_data(value):
    if isinstance(value, dict):
        return {k: clean_data(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_data(v) for v in value]
    return redact(value) if isinstance(value, str) else value


def atomic_json(path, data):
    fd, temp = tempfile.mkstemp(prefix='.' + path.name, suffix='.part', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(clean_data(data), f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def copy_bounded(source, target, *, limit, expected=None, deadline=None):
    if expected is not None and (expected < 0 or expected > limit):
        raise AssetError('SIZE_LIMIT: declared size exceeds limit')
    total = 0
    digest = hashlib.sha256()
    while expected is None or total < expected:
        if deadline is not None and time.monotonic() >= deadline:
            raise AssetError('TIMEOUT: transfer deadline exceeded')
        count = min(1 << 20, limit + 1 - total)
        if expected is not None:
            count = min(count, expected - total)
        chunk = source.read(count)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise AssetError('SIZE_LIMIT: transfer exceeds limit')
        target.write(chunk)
        digest.update(chunk)
    if expected is not None and total != expected:
        raise AssetError('INCOMPLETE_DOWNLOAD: Content-Length mismatch')
    if not total:
        raise AssetError('EMPTY_DOWNLOAD: empty body')
    return total, digest.hexdigest()


def inspect_glb(path):
    """Validate GLB framing and glTF JSON without loading the binary payload."""
    def bad(message):
        raise AssetError('INVALID_GLB: ' + message)
    size = path.stat().st_size
    doc = None
    bin_size = 0
    chunks = []
    with path.open('rb') as f:
        header = f.read(12)
        if len(header) != 12:
            bad('truncated header')
        magic, version, declared = struct.unpack('<III', header)
        if magic != 0x46546C67 or version != 2 or declared != size:
            bad('magic, version or declared length mismatch')
        while f.tell() < size:
            raw = f.read(8)
            if len(raw) != 8:
                bad('truncated chunk header')
            length, kind = struct.unpack('<II', raw)
            if length % 4 or f.tell() + length > size:
                bad('invalid chunk bounds/alignment')
            if not chunks and kind != 0x4E4F534A:
                bad('first chunk is not JSON')
            chunks.append(kind)
            if kind == 0x4E4F534A:
                if doc is not None or length > 32 << 20:
                    bad('duplicate or oversized JSON')
                try:
                    doc = json.loads(f.read(length))
                except (ValueError, UnicodeError):
                    bad('invalid JSON')
            else:
                if kind == 0x004E4942:
                    if chunks.count(kind) != 1:
                        bad('duplicate BIN')
                    bin_size = length
                f.seek(length, 1)
    if not isinstance(doc, dict) or (doc.get('asset') or {}).get('version') != '2.0':
        bad('missing glTF 2.0 asset')
    meshes = doc.get('meshes') or []
    if not meshes or not any(m.get('primitives') for m in meshes):
        bad('no mesh primitives')
    buffers = doc.get('buffers') or []
    for b in buffers:
        if not b.get('uri') and (b.get('byteLength', 0) > bin_size or b.get('byteLength', 0) < 0):
            bad('BIN is shorter than buffer')
    for view in doc.get('bufferViews') or []:
        i = view.get('buffer', 0)
        if not isinstance(i, int) or i < 0 or i >= len(buffers):
            bad('bufferView references missing buffer')
        if view.get('byteOffset', 0) < 0 or view.get('byteLength', 0) < 0 or view.get('byteOffset', 0) + view.get('byteLength', 0) > buffers[i].get('byteLength', 0):
            bad('bufferView out of bounds')
    dependencies = [b['uri'] for b in buffers + (doc.get('images') or []) if b.get('uri') and not b['uri'].startswith('data:')]
    return {'meshes': len(meshes), 'primitives': sum(len(m.get('primitives', [])) for m in meshes),
            'images': len(doc.get('images') or []), 'animations': len(doc.get('animations') or []),
            'skins': len(doc.get('skins') or []), 'external_dependencies': dependencies,
            'validation': 'container-and-buffer-bounds'}


def stop_process(proc, *, group=True):
    """Only terminate the process/group created by this invocation."""
    def send(sig):
        try:
            if group and os.name == 'posix':
                os.killpg(proc.pid, sig)
            elif sig == signal.SIGTERM:
                proc.terminate()
            else:
                proc.kill()
        except ProcessLookupError:
            pass
    send(signal.SIGTERM)
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    send(signal.SIGKILL)
    proc.wait(timeout=3)


def run_process(cmd, timeout, *, progress=True):
    """Stream redacted stderr; bound captured output; kill owned group on timeout."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True)
    output = bytearray()
    errors = bytearray()
    end = time.monotonic() + timeout
    pending = bytearray()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ, 'out')
            selector.register(proc.stderr, selectors.EVENT_READ, 'err')
            while selector.get_map():
                if time.monotonic() >= end:
                    raise AssetError('TIMEOUT: subprocess deadline exceeded')
                for key, _ in selector.select(min(.2, max(0, end - time.monotonic()))):
                    chunk = os.read(key.fileobj.fileno(), 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    if key.data == 'out':
                        output.extend(chunk)
                        if len(output) > 4 << 20:
                            raise AssetError('OUTPUT_LIMIT: helper output exceeds 4 MiB')
                    else:
                        errors.extend(chunk)
                        del errors[:-65536]
                        pending.extend(chunk)
                        while b'\n' in pending:
                            line, _, rest = pending.partition(b'\n')
                            pending[:] = rest
                            if progress:
                                print(redact(line.decode('utf-8', 'replace')), file=sys.stderr, flush=True)
                        if len(pending) > 65536:
                            pending.clear()
            proc.wait(timeout=max(.01, end - time.monotonic()))
    finally:
        stop_process(proc)
        proc.stdout.close()
        proc.stderr.close()
    return subprocess.CompletedProcess(cmd, proc.returncode, output.decode('utf-8', 'replace'), redact(errors.decode('utf-8', 'replace')))
