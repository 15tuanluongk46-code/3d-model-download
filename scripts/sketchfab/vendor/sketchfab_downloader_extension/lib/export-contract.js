/** Raw headless transport; extension ZIP downloads retain their existing contract. */
export function extractionOptions(params) {
  const size = Number(params.get('textureSize') ?? 2048);
  return {
    transport: 'raw', packMode: 'glb', devMode: false,
    downloadTextures: params.get('textures') !== '0',
    downloadAnimations: params.get('animations') !== '0',
    maxTextureEdge: [0, 2048, 4096].includes(size) ? size : 2048,
  };
}

export function geometryWarnings(skipped = []) {
  return skipped.some(item => item.reason !== 'the viewer does not draw it (opacity 0)')
    ? ['PARTIAL_GEOMETRY'] : [];
}

export function rawResult({ glb, info = {}, diagnostics, warnings = [], timings = {} }) {
  if (!glb?.length) throw new Error('INVALID_GLB: conversion failed');
  if (!diagnostics?.geometry_count) throw new Error('EMPTY_GEOMETRY: no meshes exported');
  // Never send prefetched URLs, viewer keys, or unrelated account data back as metadata.
  const metadata = Object.fromEntries(['name', 'user', 'license', 'thumbnails', 'uri']
    .filter(key => info[key] !== undefined).map(key => [key, info[key]]));
  return { glb, metadata, diagnostics, warnings, timings };
}

export async function uploadResult(result, token, send = fetch) {
  const { glb, ...metadata } = result;
  const headers = { 'X-Extractor-Token': token };
  for (const [url, body, type] of [
    ['/metadata', JSON.stringify(metadata), 'application/json'],
    ['/save', glb, 'model/gltf-binary'],
  ]) {
    const response = await send(url, { method: 'POST', headers: { ...headers, 'Content-Type': type }, body });
    if (!response.ok) throw new Error(`${url} failed: HTTP ${response.status}`);
  }
}
