# Setup 3D Model Download

Baseline Linux, Python 3.11+, Node.js để chạy test JavaScript. Không có package Python bên ngoài cần cài cho downloader chính. Native Windows chưa được xác minh: helper Sketchfab dùng module Unix `resource`.

## Cài skill và kiểm tra offline

Clone/giải nén repo. Đặt toàn bộ nội dung vào `~/.agents/skills/3d-model-download` để dùng trong OpenCode; nếu thư mục đã tồn tại, so sánh trước khi thay thế. Thoát và mở lại OpenCode. CLI vẫn chạy trực tiếp từ root clone:

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

Helper Meshy/Rodin **không được đóng gói trong repo này**. Nếu chưa được chủ dự án cung cấp/cài riêng, hai nguồn này chưa sẵn sàng (`MESHY_SKILL_MISSING`); đừng giả định clone repo là đủ cho mọi nguồn. `UV_REQUIRED` nghĩa là thiếu `uv`. Không tự cài helper từ nguồn không xác minh.

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
