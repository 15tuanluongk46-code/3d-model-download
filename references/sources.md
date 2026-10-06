# Ma trận nguồn tải model 3D

Cập nhật: 2026-10-06. Đây là ma trận tính năng, không phải tuyên bố mọi nguồn đều
được chạy E2E lại sau mỗi thay đổi. Bằng chứng đợt overhaul nằm trong
`verification-2026-10-06.md`.

## Đã hỗ trợ

### Meshy — không cần gói Pro
- Link: `https://www.meshy.ai/3d-models/<slug>-<task-uuid>`.
- Cách tải (đã kiểm chứng 5 model, GLB + texture, license CC0):
  parse UUID từ link → public API `www.meshy.ai/meshyd-api/web/public/v2/tasks/<uuid>`
  → `result.texture.modelUrl` → convert bằng loader chính thức của viewer
  (`mesh_loader.js` + `.wasm`). Đây là đường viewer-asset của helper đã có.
- Task private cần đăng nhập Meshy trên Chrome CDP; token capture runtime, không lưu.
- Thực thi: skill `meshy-rodin-download` (router gọi qua `uv run`).

### Hyper3D Rodin (hyper3d.ai)
- Model do account mình tạo: official output tải được (ưu tiên GLB, fallback DRC → OBJ).
- DRC convert ra OBJ **chỉ có geometry** (không màu/texture).
- Model Featured của người khác: `PERMISSION_DENIED` — không có quyền tải.
- Thực thi: skill `meshy-rodin-download`.

### Poly Pizza — không cần login
- Link model: `https://poly.pizza/m/<slug>`.
- Trang server-rendered chứa JSON: `ResourceID`, `Name`, `Likes`, `Downloads`,
  `Views`, `Username`, license (`CC0` / `Public Domain` / `CC-BY`).
- File tĩnh: `https://static.poly.pizza/<ResourceID>.glb` (HTTP 200, gltf-binary).
- Thực thi: handler `handle_poly` trong `scripts/download.py`, ghi GLB và
  metadata (like/download/view/creator/license); không lưu nguyên HTML.

### URL file trực tiếp
- `.glb .gltf .obj .stl .fbx .ply .usdz` qua HTTPS, cap 1 GiB.
- GLB được kiểm container v2/length/chunks/mesh/buffer bounds; không hợp lệ → lỗi.
- `.gltf`/`.obj` có dependency ngoài trả `partial` và danh sách companion chưa tải.
- Redirect direct chỉ cùng host ban đầu; cần link CDN trực tiếp nếu đổi host.

### Sketchfab — public viewer, không cần login/Pro
- Link: `https://sketchfab.com/3d-models/<slug>-<uid>` (model công khai, kể cả
  không "downloadable").
- Cách tải (kiểm chứng 2026-10, Blu uid `c75ab6b43e1e49da952361ee6b36f0a4`, ≈5.4 MB):
  `scripts/sketchfab/extract_public_model.py` mở Chrome/Chromium headless với
   **profile tạm** (không đụng Chrome của user, không cần CDP/login), chạy web app
   JavaScript vendored (`scripts/sketchfab/vendor/`), lấy viewer resources, giải mã
  mesh/animation + descramble texture → GLB tự chứa + sidecar
  `model.glb.attribution.json`.
- Giới hạn: chỉ model xem công khai; **chỉ dùng cá nhân** — giữ attribution, tôn
   trọng license của tác giả (metadata tái sử dụng từ viewer, thiếu → `unknown`).
- Raw GLB transport không qua ZIP, callback có token mỗi run, port tự cấp.
  Xem `sketchfab-extraction.md` cho options, deadline, diagnostics và giới hạn.

## Chưa hỗ trợ (lý do)

| Nguồn | Lý do | Hướng nếu user cần |
|---|---|---|
| Thingiverse | API trả 429, UI cần login | Chrome CDP + lấy link file trực tiếp rồi dùng chế độ `direct` |
| CGTrader / Fab / Free3D / TurboSquid | Account + phần lớn trả phí | Chỉ hỗ trợ link file trực tiếp nếu user cung cấp |

## Thêm nguồn mới (quy trình)

1. Tìm asset tĩnh thật (thường là CDN GLB) — bắt request trong Chrome DevTools.
2. Thêm host vào `classify()` (kind mới) + handler trong `scripts/download.py`
   (chỉ stdlib; dùng `validate_https`/`download_file`/`new_output_dir` có sẵn).
3. Thêm fixture + test offline trong `tests/` (không gọi mạng khi test).
4. Chạy E2E 1 mẫu thật, lưu bằng chứng (JSON stdout + file bytes) rồi mới ghi vào bảng trên.
5. Cập nhật bảng "Đã hỗ trợ" kèm ngày + số mẫu đã tải thành công.
