# Cài đặt trên máy khác

Repo chứa hai skill: thư mục gốc là `3d-model-download`, thư mục
`bundled-skills/meshy-rodin-download` là helper Meshy/Rodin. Không cần repo thứ hai.

## Phần mềm cần có

- Linux, Python >= 3.11, Git, `uv`, Node.js (khuyến nghị bản LTS còn hỗ trợ).
- Chrome/Chromium: Sketchfab tự mở headless profile tạm; Meshy/Rodin kết nối
  phiên Chrome CDP của người dùng, mặc định `http://127.0.0.1:9222`.
- `uv run` tự tạo môi trường Python theo script: `playwright>=1.48,<2`,
  `DracoPy==2.1.0`, `numpy>=1.26,<3`. Cần mạng cho lần tải dependency đầu tiên.
- Không cần Blender để tải. Blender chỉ cần khi muốn import/xem file.
- Tài khoản GitHub có quyền đọc repo private. Đăng nhập Meshy/Rodin trên máy mới
  khi mẫu cần quyền truy cập; phiên trình duyệt không đi kèm repo.

Nếu dùng Chrome mới cho CDP, sử dụng profile riêng và chỉ bind loopback:

```bash
google-chrome --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.local/share/3d-model-download/chrome"
```

Nếu đã có phiên CDP được chọn thì dùng phiên đó; truyền `--cdp` khi endpoint khác.
Các hướng dẫn agent có tham chiếu `chrome-ops` để điều khiển trình duyệt trên máy
gốc; skill đó không được đóng gói ở đây. CLI chạy trực tiếp khi đã có CDP,
không cần `chrome-ops` hay MCP riêng.

## Clone và cài cả hai skill

Clone ngoài thư mục mà agent tự quét skill để tránh nạp helper hai lần:

```bash
git clone https://github.com/15tuanluongk46-code/3d-model-download.git \
  ~/3d-model-download-repo
```

Chạy đoạn dưới. Nếu một trong hai skill đích đã tồn tại, đoạn cài đặt dừng trước
khi ghi file; hãy kiểm tra/backup bản đang có trước khi cập nhật.

```bash
python3 - <<'PY'
from pathlib import Path
import shutil

repo = Path.home() / '3d-model-download-repo'
target = Path.home() / '.agents/skills'
destinations = [target / '3d-model-download', target / 'meshy-rodin-download']
for dest in destinations:
    if dest.exists() or dest.is_symlink():
        raise SystemExit(f'Dừng: đã tồn tại {dest}')
ignore = shutil.ignore_patterns('.git', '__pycache__', '*.pyc', '.ruff_cache',
                               '.pytest_cache', '.venv', 'node_modules')
target.mkdir(parents=True, exist_ok=True)
shutil.copytree(repo, destinations[0], ignore=shutil.ignore_patterns(
    '.git', 'bundled-skills', '__pycache__', '*.pyc', '.ruff_cache',
    '.pytest_cache', '.venv', 'node_modules'))
shutil.copytree(repo / 'bundled-skills/meshy-rodin-download', destinations[1],
                ignore=ignore)
print('Đã cài cả hai skill:', *destinations, sep='\n')
PY
```

Khởi động lại OpenCode để nạp skill. Giữ checkout để cập nhật/kiểm tra;
`git pull` trong checkout không tự ghi đè hai bản skill đã cài.

## Kiểm tra

Tại checkout repo, chạy các lệnh trong README. Kiểm tra bản cài trực tiếp:

```bash
python3 -B ~/.agents/skills/3d-model-download/scripts/download.py --sources
uv run ~/.agents/skills/meshy-rodin-download/scripts/download.py --help
```

Meshy loader tải từ website chính thức khi cần và lưu tại
`~/.cache/meshy-rodin-download/`; cache không có trong GitHub. Không đưa token,
cookie, signed URL, profile Chrome, cache hoặc model đã tải vào commit.

## Giới hạn

Rodin DRC → OBJ chỉ có geometry. Meshy có thể dùng WebP/mesh quantization;
khả năng import phụ thuộc ứng dụng đích. Các kiểm tra GLB không thay thế
Khronos validator hoặc kiểm tra ngoại hình. Bằng chứng live lịch sử nằm trong
`references/` của từng skill; không coi đó là bảo đảm mọi link hoạt động.
Không có package Python bên ngoài cần cài cho downloader chính. Native Windows
chưa được xác minh: helper Sketchfab dùng module Unix `resource`.

## Kiểm tra offline từ checkout

```bash
python3 scripts/download.py --help
python3 scripts/download.py --sources
python3 -B -m unittest discover -s tests -v
npm --prefix scripts/sketchfab/vendor/sketchfab_downloader_extension test
```

Node suite dùng `node --test`, không cần `npm install`. Giữ vendor và giấy phép trong `THIRD_PARTY_NOTICES.md`.

## Phụ thuộc theo nguồn

| Nguồn | Điều kiện |
|---|---|
| URL file trực tiếp / Poly Pizza | Internet và URL hỗ trợ; không cần CDP hoặc phiên Google |
| Sketchfab public | Chrome/Chromium trên PATH với tên `google-chrome`, `google-chrome-stable`, `chromium` hoặc `chromium-browser`; dùng profile headless tạm |
| Meshy / Rodin | `uv`, helper riêng `~/.agents/skills/meshy-rodin-download/scripts/download.py`, Chrome CDP đã đăng nhập theo tài khoản user chọn |

Helper Meshy/Rodin đã được đóng gói, nhưng vẫn cần cài vào thư mục ngang hàng
theo phần đầu. `MESHY_SKILL_MISSING` nghĩa là chưa cài đúng đường dẫn;
`UV_REQUIRED` nghĩa là thiếu `uv`.

## Tải khi có URL và quyền phù hợp

```bash
python3 scripts/download.py 'https://example.org/model.glb' --output ./downloads
```

URL trên chỉ minh họa cú pháp; thay bằng URL model thực tế do user cung cấp. Mặc định output là `~/Downloads/3d-assets`. Xem `--help` cho timeout, texture-size, bỏ texture/animation. Output runtime và metadata có đường dẫn tuyệt đối; không commit tài sản tải về chỉ để chứng minh setup.

## Xác minh và lỗi

- JSON kết quả chứa file, hash, cảnh báo/partial; báo đúng trạng thái partial.
- GLB parse hợp lệ không chứng minh texture, skeleton hoặc pose nhìn đúng. Mở viewer/Blender khi nhiệm vụ yêu cầu kiểm tra hình ảnh.
- Thiếu Chrome chỉ chặn Sketchfab; thiếu helper chỉ chặn Meshy/Rodin. Test offline không chứng minh truy cập dịch vụ live.
- Không đóng Chrome cá nhân hoặc xóa profile để sửa lỗi CDP; xác minh endpoint/profile trước thao tác.

Đọc [SKILL.md](SKILL.md) và `references/` cho từng nguồn; nguồn public vẫn có giấy phép riêng.
