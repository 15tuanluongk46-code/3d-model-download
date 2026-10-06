import { extractionOptions, uploadResult } from './lib/export-contract.js';
const token = location.hash.slice(1);
globalThis.extractorToken = token;
const headers = { 'X-Extractor-Token': token };
const log = document.querySelector('#log');
let progressQueue = Promise.resolve();
const write = (line) => {
  log.textContent += `${line}\n`;
  document.body.dataset.lastProgress = line;
  progressQueue = progressQueue.then(() => fetch('/progress', { method: 'POST', headers, body: line })).catch(() => {});
};

const params = new URLSearchParams(location.search);
const model = params.get('model');
try {
  globalThis.chrome = {
    runtime: { getURL: (path) => new URL(path, location.href).href },
    storage: { local: { get: async () => ({}), set: async () => {} } },
  };
  const { downloadModel } = await import('./lib/pipeline.js');
  const result = await downloadModel(model, write, extractionOptions(params));
  await progressQueue;
  await uploadResult(result, token);
  document.body.dataset.state = 'ready';
  document.body.dataset.result = JSON.stringify({
    glbBytes: result.glb.length,
    diagnostics: result.diagnostics,
  });
} catch (error) {
  write(error?.stack || String(error));
  document.body.dataset.state = 'error';
  document.body.dataset.error = error?.message || String(error);
  await progressQueue;
  await fetch('/error', { method: 'POST', headers, body: error?.stack || String(error) }).catch(() => {});
}
