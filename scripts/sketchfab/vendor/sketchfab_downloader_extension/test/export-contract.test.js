import test from 'node:test';
import assert from 'node:assert/strict';
import { rawResult, uploadResult, extractionOptions, geometryWarnings } from '../lib/export-contract.js';
import { fetchTextures } from '../lib/sf-api.js';

test('intentional invisible geometry is diagnosed without a loss warning', () => {
  const hidden = { name: 'shell', reason: 'the viewer does not draw it (opacity 0)' };
  assert.deepEqual(geometryWarnings([hidden]), []);
  assert.deepEqual(geometryWarnings([hidden, { reason: 'no geometry data' }]), ['PARTIAL_GEOMETRY']);
});

test('texture listing authenticates every local proxy request', async () => {
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  globalThis.location = { hostname: '127.0.0.1' };
  globalThis.extractorToken = 'test-local-token';
  const headers = [];
  globalThis.fetch = async (_url, init) => {
    headers.push(init.headers);
    return { ok: true, json: async () => ({ results: [] }) };
  };
  try {
    await fetchTextures('a'.repeat(32));
    assert.equal(headers.length, 2);
    assert.ok(headers.every(h => h['X-Extractor-Token'] === 'test-local-token'));
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
    delete globalThis.extractorToken;
  }
});

test('raw export keeps GLB buffer identity, diagnostics and only public metadata', () => {
  const glb = new Uint8Array([103, 108, 84, 70]);
  const result = rawResult({ glb, info: { name: 'demo', user: { username: 'artist' }, secret: 'do-not-export' },
    diagnostics: { geometry_count: 2, skipped_geometries: [{ name: 'hat', reason: 'unsupported' }] }, warnings: ['PARTIAL_GEOMETRY'], timings: { convert_seconds: .2 } });
  assert.equal(result.glb, glb);
  assert.equal(result.metadata.secret, undefined);
  assert.equal(result.diagnostics.skipped_geometries[0].name, 'hat');
  assert.deepEqual(result.warnings, ['PARTIAL_GEOMETRY']);
  assert.equal(result.timings.convert_seconds, .2);
});

test('raw export rejects failed or empty geometry', () => {
  assert.throws(() => rawResult({ glb: null, diagnostics: { geometry_count: 2 } }), /INVALID_GLB/);
  assert.throws(() => rawResult({ glb: new Uint8Array(4), diagnostics: { geometry_count: 0 } }), /EMPTY_GEOMETRY/);
});

test('uploads metadata before the exact raw bytes with per-run authentication', async () => {
  const calls = [];
  const glb = new Uint8Array([1, 2, 3]);
  await uploadResult({ glb, metadata: { name: 'demo' }, warnings: [] }, 'test-token', async (url, init) => {
    calls.push({ url, ...init });
    return { ok: true };
  });
  assert.deepEqual(calls.map(c => c.url), ['/metadata', '/save']);
  assert.equal(calls[1].body, glb);
  assert.equal(calls[1].headers['X-Extractor-Token'], 'test-token');
  assert.equal(JSON.parse(calls[0].body).glb, undefined);
});

test('failed metadata prevents writing a model', async () => {
  const calls = [];
  await assert.rejects(uploadResult({ glb: new Uint8Array(4) }, 'token', async url => {
    calls.push(url); return { ok: false, status: 413 };
  }), /413/);
  assert.deepEqual(calls, ['/metadata']);
});

test('CLI options preserve explicit original texture size and animation opt-out', () => {
  const options = extractionOptions(new URLSearchParams('textureSize=0&textures=0&animations=0'));
  assert.equal(options.maxTextureEdge, 0);
  assert.equal(options.downloadTextures, false);
  assert.equal(options.downloadAnimations, false);
  assert.equal(options.transport, 'raw');
  assert.equal(extractionOptions(new URLSearchParams()).maxTextureEdge, 2048);
});
