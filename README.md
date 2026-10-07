# 3D Model Download

Máy mới: [SETUP.md](SETUP.md). Hướng dẫn AI: [AGENTS.md](AGENTS.md).
Kiểm tra bàn giao: [VERIFICATION.md](VERIFICATION.md).

Skill cho AI agent tải model 3D từ **5 nhóm nguồn**: Meshy, Hyper3D Rodin,
Poly Pizza, Sketchfab và URL file trực tiếp. Hướng dẫn vận hành đầy đủ ở
[SKILL.md](SKILL.md).

## Yêu cầu

- Python 3.11 trở lên.
- Chrome/Chromium cho extractor Sketchfab.
- Node.js có hỗ trợ `node --test` để chạy bộ kiểm thử JavaScript.
- `uv` và skill **`meshy-rodin-download`** cho Meshy/Rodin. Helper này là
  dependency riêng, **không nằm trong repo này**; router tìm tại
  `~/.agents/skills/meshy-rodin-download/scripts/download.py`.
- Meshy/Rodin sử dụng phiên Chrome CDP được chọn; endpoint mặc định là
  `http://127.0.0.1:9222`. Sketchfab dùng Chrome headless với profile tạm riêng.

## Cài đặt

Clone repo vào một thư mục mới, không ghi đè skill đã có:

```bash
git clone https://github.com/15tuanluongk46-code/3d-model-download.git \
  ~/.agents/skills/3d-model-download
```

Repo private yêu cầu tài khoản có quyền truy cập. Khởi động lại OpenCode sau khi
cài để nạp hướng dẫn skill.

## Sử dụng

```bash
python3 ~/.agents/skills/3d-model-download/scripts/download.py \
  'https://example.com/model.glb' --output ~/Downloads/3d-assets
```

Mỗi link trả một dòng JSON trên stdout, tiến độ trên stderr. Kết quả có đường dẫn
tuyệt đối `file_path`, metadata, SHA-256, `status` và `warnings`. Thư mục trùng tên
được thêm hậu tố để giữ các lần tải trước.

Sketchfab hỗ trợ `--timeout`, `--texture-size 2048|4096|0`, `--no-textures` và
`--no-animations`. Bỏ animation chỉ giữ default pose/rig, không chứng minh pose
giống “Static Pose” trên viewer; xem checklist trong SKILL.md.

Chỉ dùng tài nguyên công khai hoặc được cấp quyền cho phiên hiện tại và giữ
license/attribution của model. Kiểm tra GLB container không thay thế kiểm định
glTF đầy đủ hoặc đối chiếu hình ảnh sau import.

## Kiểm thử

Chạy từ thư mục repo:

```bash
python3 -B -m unittest discover -s tests -v
npm --prefix scripts/sketchfab/vendor/sketchfab_downloader_extension test
```

- [Nguồn và giới hạn](references/sources.md)
- [Extractor Sketchfab và kiểm tra pose](references/sketchfab-extraction.md)
- [Bằng chứng kiểm thử](references/verification-2026-10-06.md)
- [Kịch bản đánh giá agent](evals/evals.json) — không phải tất cả đã chạy E2E.

## Thành phần bên thứ ba

Giữ nguyên mã nguồn, tài liệu và license đi kèm của Sketchfab Public Downloader.
Xem [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Repo không kèm model đã tải,
phiên trình duyệt hoặc credentials.
