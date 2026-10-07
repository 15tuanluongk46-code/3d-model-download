// Adapted from meshy-glb-downloader; MIT (c) 2026 Shuvam Banerji Seal.
// Full notice: ../THIRD_PARTY_NOTICES.md. Loader JS/WASM fetched separately.
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import path from 'node:path';

function signature(hostname, timestamp) {
  let r = 14695981039346656037n;
  const mask = 0xFFFFFFFFFFFFFFFFn;
  for (const text of ['Meshy_Crypto_Key', `${hostname}:${timestamp}`]) {
    for (let i = 0; i < text.length; i++) {
      r ^= BigInt(text.charCodeAt(i));
      r = (r * 1099511628211n) & mask;
    }
  }
  r ^= r >> 33n; r = (r * 0xff51afd7ed558ccdn) & mask;
  r ^= r >> 33n; r = (r * 0xc4ceb9fe1a85ec53n) & mask;
  r ^= r >> 33n;
  return r.toString(16).padStart(16, '0');
}

try {
  const [input, output, jsPath, wasmPath] = process.argv.slice(2);
  if (!input || !output || !jsPath || !wasmPath) throw new Error('arguments');
  const buf = fs.readFileSync(input);
  if (buf.subarray(0, 8).toString() !== 'MESHY.AI') throw new Error('magic');
  const {default: init} = await import(pathToFileURL(path.resolve(jsPath)).href);
  const mod = await init({locateFile: p => p.endsWith('.wasm') ? path.resolve(wasmPath) : p});
  const host = 'www.meshy.ai', ts = Date.now();
  if (!mod.authorize(host, ts, signature(host, ts))) throw new Error('authorize');
  const res = mod.processMeshyFile(new Uint8Array(buf));
  if (!res?.success || !res.data) throw new Error('decode');
  fs.writeFileSync(output, Buffer.from(res.data.buffer, res.data.byteOffset, res.data.byteLength), {flag: 'wx'});
} catch {
  console.error('Meshy conversion failed. Check input and loader version.');
  process.exitCode = 1;
}
