# Meshy — observed 2026-10-05

## Resolve

Public community: GET `https://www.meshy.ai/meshyd-api/web/public/v2/tasks/{uuid}`.
Private/account-visible: GET `/meshyd-api/web/v2/tasks/{uuid}` with runtime `Authorization: Bearer ...` and `x-device-id`.
Private/example IDs may return public `NotFound`; this is a normal reason to try authenticated detail.

Envelope: `{code:'OK', result: TASK}`; actual assets usually at `TASK.result.<section>.modelUrl`, not `TASK.<section>`. Prefer texture → generate → remesh → draft → stylize. Status must be SUCCEEDED if present.

Capture live request headers from requests to exact host `www.meshy.ai`, path `/meshyd-api/`, before opening workspace. Tokens may expire within minutes. Do not persist or print them. An unauthenticated public model may still work without a session.

The `/downloadable-status` UI quota is distinct from whether viewer assets are returned. Some tested private and CMS tasks exposed a viewer model despite unavailable UI export; do not promise every account-visible task behaves that way. Respect a server permission refusal.

## Download + conversion

`api.meshy.ai/misc/cdn-models/...` may redirect to `assets.meshy.ai`; follow redirects with Chrome-like User-Agent and no auth headers. Signed paths expire. Refresh task detail once if download returns 401/403.

- `glTF` magic: direct GLB.
- `MESHY.AI` magic: convert using official viewer loader at `https://www.meshy.ai/resource/decrypt/mesh_loader.js` and matching `.wasm`.
- Loader cache paths passed to Node must be absolute; bare `cache/file.js` is interpreted as npm package import.
- Conversion adapter is derived from `https://github.com/Shuvam-Banerji-Seal/meshy-glb-downloader`, MIT. See notices.
- Loader not bundled/licensed as our own code. If upstream changes, inspect adapter/loader compatibility before replacing cache files. Do not delete unrelated cache data.
- `quadJsonUrl` can be a stub: `{verts_count:N,verts:[],faces_count:N,faces:[]}`; never mistake this for real mesh geometry.

Observed outputs: owned draft → 30,284,712-byte GLB with 1 mesh, 0 images; CMS example → 84,102,284-byte GLB with 1 mesh, 3 WebP images, 3,134,796 triangles. These are evidence, not hardcoded IDs or size requirements.
