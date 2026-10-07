# Rodin / Hyper3D — observed 2026-10-05

Detail link: `https://hyper3d.ai/workspace/rodin/{task_uuid}`.
Web API: `https://api.hyper3d.com/api`, Bearer from `localStorage.token` on the authenticated Hyper3D origin. Never print this value.

## Supported retrieval

1. POST `/task/get_download` JSON `{task_uuid}` → expected `{list:[{name,url,...}]}`. Helper selects a GLB if supplied.
2. If there is no usable official GLB, POST `/task/rodin_history` JSON `{uuid:task_uuid,step:'ModelGenerate'}`.
3. Response `{v1:{preview_drc,preview_cover,settings,...}, ...}`: prefer highest numeric version with `preview_drc`.
4. Download signed `file.hyper3d.com/.../model.drc`. Signature authorizes only that exact path; no auth header required on CDN.
5. Decode Draco using DracoPy → checked positions/faces → OBJ geometry only. File retained as source.drc. No texture/UV/material recovery is claimed by this fallback.

## Boundaries and known failures

- `PERMISSION_DENIED` on non-owned Featured task was verified. Stop; a public card is not evidence of geometry-download permission.
- `get_download` returned HTTP 201 with `error:INVALID_REQUEST` even on owned Done tasks. This is not success. Extra format/type/step payload fields did not fix it; do not repeat those guesses.
- Gen-2.5 subscription and NSFW dialogs were seen. UI text alone did not establish every reason for rejection.
- `rodin_agentic_download` is a DIFFERENT task type. Allowed formats observed: usdz/blend/source/pack; pack needs version. Ordinary rodin_mesh tasks return `Not a RodinAgentic task`. Current helper does not automate this path.
- Developer API `/api/v2/download` needs an active API key. Web JWT does not authenticate it. Do not substitute web tokens or request a purchase automatically.
- No generation, material confirmation or pack creation during download. Those can consume credits.

Observed owned DRC: 3,701,725 bytes, 1,000,002 points and 2,000,000 faces. OBJ was about 72 MB in the earlier prototype; precision differences can change size. Not a general fixed-size requirement.
