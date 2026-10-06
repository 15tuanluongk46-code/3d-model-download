# Báo cáo kiểm tra — 2026-10-06

## Phạm vi

Đã triển khai cả bốn nhóm: sửa hợp đồng kết quả và validation; gia cố extractor;
tối ưu raw GLB/metadata/options; bổ sung tests, E2E, docs và eval scenarios.
Thay đổi áp dụng tại `~/.agents/skills/3d-model-download`.

## Automated checks

Chạy từ thư mục skill:

```bash
python3 -B -m unittest discover -s tests -v
npm --prefix scripts/sketchfab/vendor/sketchfab_downloader_extension test
```

- Python: **34/34 PASS**, 2.230 giây.
- JavaScript: **205/205 PASS**, 226.65 ms.
- Regression mới kiểm direct JSON/metadata/absolute paths, GLB lỗi, URL redaction,
  external dependencies, output directory concurrency, Meshy delegate contract,
  Poly metadata timeout, bounded transfer, subprocess deadline, callback auth,
  ephemeral ports, raw upload, unknown license, texture proxy authentication,
  options và phân biệt geometry chủ động ẩn với geometry bị mất.
- Các regression đã được chạy ở trạng thái lỗi trước khi sửa implementation.
- Không tìm thấy cấu hình lint/typecheck/build riêng cho wrapper này.

## E2E mạng thật

Output root: `/tmp/opencode/3d-download-overhaul-e2e`.
Lệnh dùng `python3 -B scripts/download.py '<URL>' --output <root>`; Blu cuối dùng
`--timeout 120`, direct dùng `--timeout 60`; các lượt bỏ animation thêm
`--no-animations`.

| Mẫu | Dung lượng | Thời gian extractor | Kết quả |
|---|---:|---:|---|
| Blu, mặc định, lượt cuối | 5,399,316 B | 13.745 s | complete; 13 meshes, 5 images, 13 skins, 1 animation |
| Blu, `--no-animations` | 4,909,564 B | 9.937 s | 13 meshes, 5 images, 13 skins, 0 animations |
| Allom, `--no-animations` | 94,189,936 B | 46.208 s | complete; 29 meshes, 26 images, 0 skins, 0 animations |
| Khronos Box, direct HTTPS | 1,664 B | không đo | complete; JSON và metadata đúng |

Allom vốn không có animation; kiểm tra bỏ animation có ý nghĩa được thực hiện
riêng trên Blu. Lượt Blu no-animation chạy trước khi bỏ cảnh báo giả đối với hai
geometry opacity 0, nên metadata lịch sử của lượt đó vẫn ghi `partial`.
Code cuối giữ lý do loại hai geometry này trong diagnostics nhưng không coi là mất dữ liệu.

URL nguồn:

- Blu: https://sketchfab.com/3d-models/blu-anime-girl-character-c75ab6b43e1e49da952361ee6b36f0a4
- Allom: https://sketchfab.com/3d-models/allom-game-character-7dd62bde838845e89f15741e79f88e9a
- Box: https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/Box/glTF-Binary/Box.glb

Các file dưới output root:

```text
sketchfab/blu-anime-girl-character-c75ab6b43e1e49da952361ee6b36f0a4-3/model.glb
sketchfab/blu-anime-girl-character-c75ab6b43e1e49da952361ee6b36f0a4-2/model.glb
sketchfab/allom-game-character-7dd62bde838845e89f15741e79f88e9a/model.glb
direct/Box.glb/Box.glb
```

SHA-256 tương ứng:

```text
Blu:       aa4dd147ccf142e923a22c4b18d28248e689b4a57eed20ac07f3ecace641460c
Blu noanim:1f7c495991b1fca8837b92615e1427ff32c781f84e37550fd4a8d7e465656d7a
Allom:     fbcf09240bc47b3ca647f83c235211c5848718a47f063462561e120440306a18
Box:       ed52f7192b8311d700ac0ce80644e3852cd01537e4d62241b9acba023da3d54e
```

Blu mặc định và Allom khớp SHA-256 với file tải bằng pipeline cũ.
Allom nay ghi license `unknown`, sửa fallback `CC` không có bằng chứng trước đây.

## Timeout, concurrency và Blender

- Blu và Allom chạy đồng thời thành công, dùng port riêng 44403 và 41033.
- Router với Blu embed và `--timeout 0.5` trả `ok:false`,
  `SKETCHFAB_TIMEOUT: extractor deadline exceeded` sau 1.078 giây kể cả cleanup.
  So sánh process snapshot trước/sau: **0 Chrome/Chromium extractor mới còn lại**.
  Kiểm tra live này không đo riêng sự tồn tại của thư mục profile sau cleanup.
- Blender 5.2.1, `--background --factory-startup --python-expr`, import bằng
  `bpy.ops.import_scene.gltf`, reset factory scene giữa các mẫu và assert mesh có vertices:
  - Blu animated (lượt `-1`, hash giống lượt cuối): 14 mesh objects, 1 armature,
    5 images, 1 action.
  - Blu no-animation (`-2`): 14 mesh objects, 1 armature, 5 images, 0 actions.
  - Allom: 29 mesh objects, 0 armatures, 26 images, 0 actions.
  Cả ba import thành công, process exit 0. Số Blender objects có thể khác số glTF meshes.

## Hiệu năng và giới hạn bằng chứng

- Headless truyền raw GLB, bỏ ZIP compress/decompress và wireframe overlay không dùng.
  Metadata viewer được tái sử dụng; hash tính khi stream, proxy spool ra disk.
- Blu lượt cuối: textures 6.603 s, convert 0.380 s; network 7,255,539 B;
  Python extractor peak RSS 37,012 KiB.
- Allom: textures 39.593 s, convert 0.237 s; Python extractor peak RSS 47,592 KiB.
- RSS **không gồm Chrome**. Không có benchmark cũ/mới cùng điều kiện, vì vậy
  không kết luận nhanh hơn bao nhiêu phần trăm hoặc giảm bao nhiêu tổng RAM.
- GLB validation hiện tại kiểm container và buffer bounds, không thay thế full
  Khronos Validator. Blender import không chứng minh ngoại hình/pose giống viewer 1:1.
- Meshy/Rodin/Poly Pizza chưa chạy lại E2E mạng trong đợt này; Meshy delegate contract
  được kiểm bằng fixture/mocked process, Poly parser và timeout bằng unit tests.
- `evals/evals.json` chứa 10 kịch bản đánh giá; không tuyên bố đã chạy toàn bộ
  agent-level eval hoặc benchmark with-skill/without-skill.

Kết luận: automated suite và các E2E đại diện ở trên đều pass; phạm vi tất cả
provider và độ tương đồng hình ảnh chỉ được xác minh một phần.
