---
name: meshy-rodin-download
description: Dùng khi user yêu cầu tải/xuất/lấy file 3D Meshy hoặc Rodin/Hyper3D từ link cụ thể, kể cả "tải mẫu này" hay /3d-download có link. Chuyển Meshy sang GLB, Rodin history DRC sang OBJ và kiểm tra đầu ra qua phiên Chrome được chọn. Link đơn thuần, yêu cầu xem/nhận xét mẫu, tạo model mới hay phân tích ảnh không kích hoạt download hoặc truy cập tài khoản.
compatibility: OpenCode; Linux; uv; Node.js; Chrome logged-in CDP (default 127.0.0.1:9222). Python dependencies isolated by uv.
---

# Meshy + Rodin: link → file 3D

## Thực hiện ngay

1. Lấy link từ yêu cầu; cần **một task UUID cho mỗi link**. Link trang chủ, workspace chung, ảnh screenshot hoặc trang danh sách chưa xác định mẫu: hỏi link chi tiết. Không chọn ngẫu nhiên mẫu trong tài khoản.
2. Dùng profile/endpoint Chrome user chỉ định; mặc định `http://127.0.0.1:9222`. Xem tab bằng `chrome-live_browser_tabs` để xác minh đúng site và tài khoản nếu phiên có nhiều account. Khi cần đăng nhập/mở Chrome, đọc `chrome-ops`; CAPTCHA/2FA để user hoàn tất trên Chrome.
3. Chạy helper dưới đây bằng Bash. Helper mở tab tạm dùng cùng profile, đọc auth trong RAM, tải và tự đóng tab tạm. Nó không tắt Chrome.

```bash
uv run ~/.agents/skills/meshy-rodin-download/scripts/download.py 'LINK_3D'
```

Nhiều link, thư mục và endpoint do user chọn:

```bash
uv run ~/.agents/skills/meshy-rodin-download/scripts/download.py \
  'LINK_MESHY' 'LINK_RODIN' \
  --output ~/Downloads/3d-assets \
  --cdp http://127.0.0.1:9222
```

4. Đọc JSON từng kết quả. Chỉ báo tải thành công khi `ok: true`. Trả đường dẫn `file`, dung lượng, định dạng, texture/geometry-only. Nếu một link lỗi, các link còn lại vẫn chạy; exit code 1 nghĩa là có ít nhất một lỗi.

## Đầu ra

`~/Downloads/3d-assets/<meshy|rodin>/<task-uuid>/`

- `model.glb` (Meshy hoặc Rodin official GLB), hoặc `model.obj` (Rodin history geometry).
- `source.meshy`, `source.drc` hoặc `source.glb` để giữ bản nguồn.
- `metadata.json`: task ID, nguồn, số mesh/ảnh hoặc vertices/faces, SHA-256, kết quả kiểm tra.
- Lần tải trùng tạo thư mục hậu tố `-1`, `-2`…; không ghi đè lần trước.
- Thư mục thiếu metadata có thể là lần chạy dở/lỗi; không coi đó là thành công.

Meshy GLB có thể chứa texture WebP và mesh quantization: nêu extensions nếu app đích không mở được. `images: 0` không phải model có texture. Rodin OBJ từ DRC là **geometry-only**, không giữ material, texture hay UV. Không gọi preview geometry là bộ export hoàn chỉnh.

## Lỗi và phục hồi có giới hạn

- `CDP_UNAVAILABLE`: kiểm tra Chrome debug/profile qua `chrome-ops`, sau đó chạy lại.
- `LOGIN_REQUIRED`: yêu cầu đăng nhập site tương ứng; không xin user dán token vào chat. Helper tự thử refresh auth một lần khi 401.
- `TASK_ID_REQUIRED`: hỏi link chi tiết; không đoán task.
- `PERMISSION_DENIED`: dừng mẫu đó và báo tài khoản hiện tại không được cấp quyền. Rodin Featured của người khác đã trả lỗi này trong kiểm thử.
- `DOWNLOAD_HTTP_401/403`: helper xin signed URL mới và thử lại một lần; không tái dùng signed URL từ cuộc hội thoại cũ.
- `MESHY_DECODE_FAILED`: đọc `references/meshy.md`; loader web có thể đổi. Không sửa API bừa hoặc dò hàng loạt endpoint.
- `RODIN_NO_SUPPORTED_OUTPUT`: đọc `references/rodin.md`; chưa xác minh RodinAgentic. Không tự tạo task mới để thử, không dùng credits của user.
- `UNEXPECTED_*`: đây là lỗi thực, không tự nhận thành công. Chẩn đoán cục bộ, lọc secrets khỏi log trước khi đưa vào chat.

## Dùng lại file cục bộ

```bash
uv run ~/.agents/skills/meshy-rodin-download/scripts/download.py \
  --convert '/path/source.meshy' --destination '/path/new-model.glb'
uv run ~/.agents/skills/meshy-rodin-download/scripts/download.py \
  --convert '/path/source.drc' --destination '/path/new-model.obj'
python3 ~/.agents/skills/meshy-rodin-download/scripts/download.py \
  --inspect '/path/model.glb'
```

`--inspect` kiểm tra cấu trúc container/chunks/JSON và sự tồn tại mesh, **không thay thế Khronos validator hoặc kiểm tra hình ảnh**. OBJ được kiểm tra tọa độ hữu hạn, bounds của index và đếm lại dòng đầu ra. Khi user yêu cầu import Blender/Godot, tải xong mới chuyển sang skill tương ứng.

## Ranh giới hoạt động

- Chỉ truy cập asset được API cấp cho phiên hiện tại hoặc public asset; dừng khi server từ chối quyền. Khả năng tải thành công đã được chứng minh ở vài mẫu, không đảm bảo mọi link.
- Không hardcode token/cookie, lưu HAR, in request headers hoặc ghi signed URLs vào metadata. Chỉ dùng auth với API đúng origin.
- Không mua gói, tạo model, confirm material, thay privacy hoặc tiêu credits trong nhiệm vụ tải file.
- Cache JS/WASM viewer chính thức ở `~/.cache/meshy-rodin-download/`; tải dependency lần đầu có thể cần mạng. Giữ attribution của upstream ở `THIRD_PARTY_NOTICES.md`.
- Không cần bật thêm MCP hay sửa `opencode.json`.

## Kiểm tra skill

```bash
python3 -m unittest discover -s ~/.agents/skills/meshy-rodin-download/tests -v
node --check ~/.agents/skills/meshy-rodin-download/scripts/decrypt.mjs
```

Các case người dùng ở `evals/evals.json`; bằng chứng kiểm thử triển khai ở `references/verification.md` khi có. Không suy rộng coverage được ghi ở đó thành hỗ trợ mọi biến thể website.
