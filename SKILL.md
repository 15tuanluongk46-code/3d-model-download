---
name: 3d-model-download
description: Tải model 3D từ link về máy — gộp nhiều nguồn (Meshy không cần Pro, Hyper3D Rodin, Poly Pizza, Sketchfab public viewer không cần login/Pro, URL file .glb/.gltf/.obj/.stl/.fbx trực tiếp). Dùng NGAY khi user đưa link model 3D (meshy.ai/3d-models, hyper3d.ai/workspace/rodin, poly.pizza/m/..., sketchfab.com/3d-models/..., link file 3D) và nói "tải mẫu này", "tải model 3D", "tải Model 3D bất kì", "xuất file 3D", "tải GLB", hoặc gọi /3d-download. Tự tải kèm metadata (tác giả, like, license, sha256). KHÔNG dùng để tạo model mới, tạo ảnh, hay phân tích ảnh.
compatibility: OpenCode; Linux; uv; Node.js; Chrome logged-in CDP (default 127.0.0.1:9222) cho Meshy; Sketchfab dùng Chrome/Chromium headless với profile tạm (không cần đăng nhập/CDP). Python dependencies isolated by uv.
---

# 3D Model Download (đa nguồn)

Tải model 3D từ link về thư mục cục bộ, không cần đăng nhập Pro:
Meshy/Hyper3D Rodin (qua skill `meshy-rodin-download`), Poly Pizza (GLB tĩnh,
không cần login), Sketchfab public viewer (GLB + attribution, không cần
login/Pro — chỉ dùng cá nhân, tôn trọng license), và URL file 3D trực tiếp.

## Thực hiện ngay

1. Với nhân vật cần mở xem trong Blender, thực hiện mục **Chọn và xác minh pose**
   bên dưới trước để chọn tùy chọn tải. Sau đó chạy router với các link user đưa
   (mỗi link ra 1 dòng JSON; tách lượt chạy nếu các model cần tùy chọn khác nhau):

   ```bash
   uv run ~/.agents/skills/3d-model-download/scripts/download.py 'LINK1' ['LINK2' ...] --output ~/Downloads/3d-assets
   ```

   - Mặc định output: `~/Downloads/3d-assets/<provider>/<id>/`.
   - `--cdp http://127.0.0.1:9222` nếu Chrome debug chạy port khác.
   - `--sources` để xem danh sách nguồn hỗ trợ khi link không rõ.
   - `--timeout 240`: ngân sách giây cho extractor/helper hoặc mỗi transfer; tăng cho model lớn.
   - Sketchfab: `--texture-size 2048` (mặc định), `4096` hoặc `0` (ưu tiên bản lớn nhất).
     Đây là ưu tiên chọn variant, không bảo đảm resize mọi ảnh về đúng kích thước.
   - Sketchfab: `--no-textures`, `--no-animations` để bỏ phần không cần tải.
     Bỏ animation giữ rig/default pose; **không đồng nghĩa** pose “Static Pose” trên viewer.

2. Đọc từng dòng JSON trong stdout, báo user: `ok`, `status`, **`file_path`**,
   `bytes`, `creator`, `license`, `likes` (nếu có). Dùng đường dẫn tuyệt đối trả về,
   không tự ghép đường dẫn vì thư mục có thể được thêm hậu tố.
   `ok:true,status:partial` có file dùng được nhưng cần đọc `warnings` và `diagnostics`.
   Dòng `ok:false` kèm `error` mã lỗi ở mục dưới. Tiến độ đi vào stderr.
   KHÔNG bịa kết quả — chỉ báo cáo file thực đã ghi ra đĩa.

## Chọn và xác minh pose của nhân vật

Đây là quy trình của agent, không phải tính năng tự kiểm tra pose trong CLI.
Mặc định CLI vẫn tải animation nếu có; chỉ thêm `--no-animations` theo mục tiêu:

| Yêu cầu | Cách chọn bản |
|---|---|
| Chỉ tải file, chưa yêu cầu mở xem hay bỏ animation | Giữ mặc định CLI, không tự bỏ animation |
| Tải nhân vật và mở Blender để xem, không yêu cầu chuyển động | Kiểm tra viewer; ưu tiên bản tĩnh bằng `--no-animations` cho Sketchfab rồi đối chiếu |
| Yêu cầu Static Pose | Chọn Static Pose thật trên viewer làm reference; bản bỏ animation chỉ là ứng viên cần kiểm tra |
| Yêu cầu animation hoặc giữ nguyên mọi clip | Không thêm `--no-animations`; kiểm tra clip được yêu cầu riêng |

1. Trên viewer, đọc danh sách pose/animation và tên clip thực tế trước khi chọn.
   Chỉ nói có `Idle` nếu danh sách thực sự có clip đó; không đổi tên `Take001`
   thành Idle. Xác nhận lựa chọn Static Pose hoặc clip bằng readback của giao diện.
2. Nếu mở được viewer, lưu ảnh tham chiếu ở pose/clip đã chọn. Với animation, ghi
   thời điểm trong clip để so sánh cùng thời điểm sau import. Nếu không đọc được
   danh sách hoặc không chụp được reference, ghi rõ phần chưa xác minh; vẫn có thể
   tải tài nguyên công khai truy cập được, nhưng không tuyên bố pose đã khớp.
3. `--no-animations` giữ rig/default pose; không chứng minh đó là Static Pose,
   rest pose hay một frame cụ thể trên viewer. Tùy chọn này chỉ có hiệu lực cho
   Sketchfab; với nguồn khác, giữ file gốc và kiểm tra trên bản import riêng.
4. Khi mở Blender, áp dụng checklist cuối skill và quy trình chi tiết trong
   `references/sketchfab-extraction.md`. Nếu chưa có bằng chứng hình ảnh, báo
   **đã tải/import, chưa xác minh pose** thay vì **Static Pose đúng**.
5. Bản tĩnh đúng nhưng animation lỗi là hai kết quả khác nhau. Giữ file riêng,
   báo rõ lỗi animation còn tồn tại; không âm thầm thay yêu cầu animation bằng bản tĩnh.

## Nguồn hỗ trợ

**5 nhóm nguồn: 4 nền tảng + URL file trực tiếp.** `static.poly.pizza` là CDN
của Poly Pizza, không phải nền tảng riêng; các domain Rodin cũng cùng một nguồn.

| Nguồn | Link dạng | Ghi chú |
|---|---|---|
| Meshy | `meshy.ai/3d-models/...` (có UUID) | Không cần Pro — viewer-asset route, GLB + metadata |
| Hyper3D Rodin | `hyper3d.ai/workspace/rodin/...` | Model của mình → GLB; DRC → OBJ geometry-only |
| Poly Pizza | `poly.pizza/m/<slug>` | GLB từ `static.poly.pizza`, kèm like/download/license |
| File trực tiếp | `https://.../x.glb` (.gltf/.obj/.stl/.fbx/.ply/.usdz) | HTTPS, tối đa 1 GiB |
| Sketchfab | `sketchfab.com/3d-models/<slug>-<uid>` | GLB qua public viewer extractor — không cần login/Pro; kèm `model.glb.attribution.json`; chỉ dùng cá nhân, tôn trọng license |

Chi tiết + nguồn CHƯA hỗ trợ (Thingiverse, CGTrader, Fab...):
`references/sources.md`. Chi tiết extractor: `references/sketchfab-extraction.md`.

## Đầu ra

```
<output>/<provider>/<id>/
  model.glb        # hoặc model.obj / tên file gốc
  model.glb.attribution.json  # (sketchfab) tác giả + license + link gốc — luôn giữ kèm
  metadata.json    # provider, id, file, bytes, sha256, format, license, creator, ...
```

- Trùng id → thư mục mới có hậu tố `-1`, `-2`; không ghi đè file cũ.
- Kết quả thành công có `output_dir`, `file_path`, `metadata_path` tuyệt đối,
  `sha256`, `status`, `warnings`; metadata được ghi atomic.
- Thiếu metadata: kiểm tra lỗi của lần chạy trước và file còn lại, không tự xóa.
- License không có bằng chứng → `unknown`; không tự suy ra CC/CC0 hay quyền sử dụng.
- `.gltf` có external buffer/image và `.obj` có `mtllib` được báo `partial` với
  `external_dependencies`; các companion file chưa được tải tự động.
- GLB kiểm version/length/chunk/JSON/mesh/buffer bounds. Đây không phải kiểm định
  glTF đầy đủ; `complete` cũng không bảo đảm hình ảnh giống viewer 1:1.
- Thống kê Sketchfab: `quality`, `diagnostics`, `timings`, `network_bytes`.
  `peak_rss_kib` chỉ đo Python extractor, **không gồm Chrome**.

## Lỗi và phục hồi có giới hạn

- `UNSUPPORTED_LINK` — host/chưa hỗ trợ; chạy `--sources`, nói rõ với user.
- `POLY_SLUG_REQUIRED` / `POLY_RESOURCE_NOT_FOUND` — link Poly Pizza sai dạng
  hoặc trang đổi cấu trúc; thử lại link chính từ poly.pizza.
- `INVALID_GLB` — container/mesh/buffer không hợp lệ; file mới lỗi bị loại bỏ.
- `MESHY_SKILL_MISSING` / `UV_REQUIRED` — thiếu skill meshy-rodin-download
  hoặc `uv`; cài rồi chạy lại.
- `MESHY_HELPER_FAILED` — xem stderr in kèm; lỗi con thường gặp:
  `CDP_UNAVAILABLE` (mở Chrome debug), `LOGIN_REQUIRED` (cần đăng nhập Meshy
  trên Chrome), `PERMISSION_DENIED` (model riêng tư/không thuộc account),
  `TASK_ID_REQUIRED` (link không có UUID), `MESHY_DECODE_FAILED`.
- `SKETCHFAB_UID_REQUIRED` — link Sketchfab thiếu UID 32 ký tự; dùng đúng dạng
  `sketchfab.com/3d-models/<slug>-<uid>`.
- `SKETCHFAB_EXTRACTOR_MISSING` / `SKETCHFAB_TIMEOUT` / `SKETCHFAB_NO_BROWSER` —
   thiếu extractor / quá `--timeout` / không tìm thấy Chrome.
- `SKETCHFAB_EXTRACT_FAILED` — xem stderr in kèm (model private, trang đổi cấu trúc...).
- `HTTP_401/403` khi tải Meshy — signed URL hết hạn; script gốc tự retry 1 lần.
- `SIZE_LIMIT` / `EMPTY_DOWNLOAD` / `TRUNCATED_DOWNLOAD` / `NETWORK_ERROR` —
  đọc lỗi cụ thể, không retry mù. Lỗi Sketchfab có tiền tố `SKETCHFAB_`.
- `PARTIAL_GEOMETRY`, `NO_TEXTURES_EMBEDDED`, `TEXTURES_DECODE_UNVERIFIED`,
  `PIPELINE_RESOURCE_FAILURE`: file có cảnh báo chất lượng; báo rõ phần thiếu.
  Mesh chủ động ẩn bằng opacity 0 chỉ nằm trong diagnostics, không tính là mất mesh.

## Ranh giới hoạt động

- Không hardcode/copy token, cookie, HAR, signed URL vào file nào.
- Không mua gói, không tiêu credits, không đổi tài khoản của user.
- Chỉ tải HTTPS:443; kiểm host mỗi redirect. Direct chỉ redirect cùng host ban đầu;
  link đổi sang CDN khác cần URL CDN trực tiếp. Sketchfab dùng allowlist riêng.
- Không tự ý xóa model user đã tải; không sửa gallery/collection của user.

## Kiểm tra skill

```bash
python3 -B -m unittest discover -s ~/.agents/skills/3d-model-download/tests -v
npm --prefix ~/.agents/skills/3d-model-download/scripts/sketchfab/vendor/sketchfab_downloader_extension test
```

Bằng chứng kiểm thử và giới hạn: `references/verification-2026-10-06.md`.

## Khi user muốn mở trong Blender

- Import GLB bằng **File → Import → glTF 2.0** hoặc `bpy.ops.import_scene.gltf(filepath=...)`.
  Không truyền GLB như file `.blend` vào CLI mở tài liệu.
- Nếu cần mở GUI từ CLI, import rồi lưu `.blend` trong một process riêng trước.
  Không xóa scene đang mở của user để import model mới.
- Giữ pose gốc khi chưa rõ mục tiêu; không zero toàn bộ bone để giả lập “Static Pose”.
  Muốn pose theo viewer phải đối chiếu reference và chọn/bake pose phù hợp.
- Import vào scene/collection riêng, giữ hierarchy và rig. Với bản tĩnh, kiểm tra
  số animation trong GLB và Action/NLA đang tác động lên các object đã import;
  dừng playback thôi chưa đủ chứng minh không còn animation. Giữ rig nếu nguồn có.
- Bật Material Preview, đặt góc nhìn tương ứng reference và lấy toàn thân trong
  khung. Kiểm tra đầu/mũ, giáp thân, tay/chân, tỷ lệ, texture và mesh nổ/tách rời.
  Không scale riêng từng mảnh để che lỗi; nếu cần đổi kích thước, dùng root chung.
- Với animation, kiểm tra ít nhất đầu/giữa/cuối clip đúng tên và đúng thời điểm
  so với viewer; không suy ra clip đúng chỉ từ frame đầu hoặc từ bản tĩnh đúng.
- Sau thay đổi, đọc scene state và chụp viewport. Chỉ kết luận những chi tiết thấy
  được; ảnh thiếu góc/che khuất hoặc không đọc được thì báo giới hạn đó. Lưu `.blend`
  vào đường dẫn mới và báo đường dẫn cùng trạng thái xác minh pose/animation.
- Import thành công xác nhận khả năng đọc file; kết luận ngoại hình cần xem viewport/render.
  Trên Wayland, không thấy cửa sổ qua `xdotool` chưa có nghĩa Blender không mở;
  process còn sống cũng chưa chứng minh cửa sổ đã hiển thị đúng model.
