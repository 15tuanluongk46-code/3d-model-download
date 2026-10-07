# Kiểm chứng triển khai — 2026-10-05

## Kiểm tra tự động

Chạy từ `~/.agents/skills/meshy-rodin-download/`:

- PASS: `python3 -m unittest discover -s tests -v` — 6 tests; nhận link, envelope Meshy, host tải, GLB giả/truncated, tránh ghi đè, và private Meshy fallback khi public API trả HTTP 404.
- PASS: `uvx ruff check scripts tests`.
- PASS: `node --check scripts/decrypt.mjs`.
- PASS: `python3 ~/.agents/skills/skill-creator/scripts/quick_validate.py ~/.agents/skills/meshy-rodin-download` — Skill is valid.

## Tải thực bằng helper mới

Lệnh Meshy:

```bash
uv run ~/.agents/skills/meshy-rodin-download/scripts/download.py \
  'https://www.meshy.ai/workspace?taskId=01a0c245-8a0c-7620-be5a-14e6dad5719d'
```

PASS: `~/Downloads/3d-assets/meshy/01a0c245-8a0c-7620-be5a-14e6dad5719d/model.glb`.
30,284,712 bytes; 1 mesh, 1 material, 0 images; KHR_mesh_quantization.
SHA-256: `2ad83de65fe117d6292b6b98ede423d7591577bb92e185a20e638100b88ee128`.
Private task dùng authenticated API sau khi public endpoint trả NotFound.

Lệnh Rodin (đã chạy trong batch với Meshy):

```bash
uv run ~/.agents/skills/meshy-rodin-download/scripts/download.py \
  'https://hyper3d.ai/workspace/rodin/b8893ec3-93b8-4f6c-9c3b-810337d2587a'
```

PASS: `~/Downloads/3d-assets/rodin/b8893ec3-93b8-4f6c-9c3b-810337d2587a/model.obj`.
84,923,888 bytes; 1,000,002 vertices; 2,000,000 triangles; geometry-only.
SHA-256: `7eb382e3c27baa6ab0600f57e6829f09d8bbd1a9f261aac15f256f949c07c601`.
Nguồn owned ModelGenerate preview DRC, không phải full textured export.

Negative integration check:

```bash
uv run ~/.agents/skills/meshy-rodin-download/scripts/download.py \
  'https://hyper3d.ai/workspace/rodin/e89eaefb-cc42-4928-be44-47e544dd283f'
```

PASS theo kỳ vọng: trả `ok: false`, `PERMISSION_DENIED`, exit 1; dừng mẫu không được tài khoản cấp quyền.

## Giới hạn bằng chứng

Đây là kiểm thử helper trực tiếp, không phải benchmark so sánh agent có/không skill. Các prompt trong `evals/evals.json` là bộ case để đánh giá agent về sau; chưa chạy benchmark nhận diện trigger. Command đã tạo đúng thư mục nhưng cần khởi động lại OpenCode để thử trong phiên mới.

GLB được kiểm tra container/chunks/JSON, chưa render đối chiếu hoặc chạy Khronos validator. Chưa xác minh live đường Rodin official GLB, RodinAgentic, mọi public/community Meshy hoặc mọi định dạng URL. Không suy rộng hai mẫu thành bảo đảm tải mọi link.
