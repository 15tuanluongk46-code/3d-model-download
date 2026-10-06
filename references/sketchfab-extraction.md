# Sketchfab extractor: vận hành và giới hạn

## Chạy

Ưu tiên router để có `metadata.json` và hợp đồng kết quả chung:

```bash
python3 ~/.agents/skills/3d-model-download/scripts/download.py 'https://sketchfab.com/3d-models/<slug>-<uid>' --output ~/Downloads/3d-assets --timeout 240
```

Extractor độc lập (không ghi đè output đã tồn tại):

```bash
python3 ~/.agents/skills/3d-model-download/scripts/sketchfab/extract_public_model.py '<URL-or-UID>' --output /tmp/model.glb --port 0 --texture-size 2048
```

UID gồm 32 ký tự hex. Extractor cũng nhận `/models/<uid>/embed`.
Các tùy chọn chung: `--timeout`, `--texture-size 0|2048|4096`, `--no-textures`,
`--no-animations`. `--port 0` cấp port trống tự động. `--no-launch` dành cho debug
thủ công, in URL localhost dùng một lần; URL chứa token, không chia sẻ hoặc lưu log.

## Luồng thực thi

1. `serve_public_extractor.py` mở server `127.0.0.1` với port riêng và token mỗi run.
2. Chrome/Chromium headless chạy profile tạm, không dùng phiên/CDP của user.
   Vendored JavaScript được phục vụ như web app; không cần cài extension vào Chrome.
3. `headless.js` gọi pipeline qua proxy HTTPS allowlist. Mọi redirect được kiểm tra;
   callback/proxy cần token, Host đúng và Origin cùng server (nếu có).
4. Metadata có sẵn từ viewer được tái sử dụng; mesh/animation/texture được chuyển GLB.
   Texture đã có concurrency 3 và ORM cache; không tăng song song vô hạn.
5. Upload JSON diagnostics rồi **raw GLB**, không nén ZIP rồi giải nén lại.
   Chế độ extension gốc vẫn giữ ZIP; chỉ luồng headless dùng raw transport.
6. Server stream ra `.part`, tính SHA-256 cùng lượt, kiểm GLB, đổi tên atomic,
   ghi attribution atomic. Router ghi metadata và in một JSON kết quả.
7. Theo dõi deadline/Chrome exit; dọn process group do run tạo, profile và server.

## Giới hạn tài nguyên

- GLB/upload/proxy mỗi transfer: 1 GiB; tổng proxy đã nhận: 4 GiB mỗi run.
- Callback JSON: 1 MiB; JSON chunk GLB: 32 MiB. Proxy spool ra disk thay vì đọc
  nguyên response vào Python RAM. Tối đa 6 proxy transfer đồng thời.
- Network socket timeout tối đa 15 giây ở extractor; deadline được kiểm giữa các
  chunk và ở monitor. Cleanup có grace period; thời gian thực có thể vượt deadline.
- `--texture-size` chọn variant phù hợp nếu nguồn có; không phải bộ resize bảo đảm.
- `--no-animations` bỏ curve downloads, giữ rig/default pose; không tự bake pose viewer.
- `peak_rss_kib` là đỉnh RSS Python process, không phải tổng Python + Chrome.

## Kết quả và chất lượng

`quality` kiểm GLB v2, độ dài, chunk, JSON, mesh primitives, buffer/bufferView bounds.
Không thay thế Khronos Validator hoặc kiểm tra hình ảnh. `diagnostics` giữ số mesh,
texture, animation, skeleton, bone và lý do bỏ geometry. Geometry opacity 0 bị ẩn
chủ động không tạo `PARTIAL_GEOMETRY`; các mất mát khác tạo cảnh báo.

License thiếu → `unknown`, không đoán CC. Giữ `.attribution.json` cùng model.
Viewer công khai không tự cấp quyền sử dụng lại nội dung. Không thử vượt login,
private model hoặc cơ chế hạn chế truy cập.

`status:partial` ở router vẫn có file, nhưng phải đọc warnings. Các lỗi upload,
GLB không hợp lệ, zero geometry hoặc timeout trả `ok:false`.

## Quy trình nhân vật: Static Pose và animation

Quy trình này do agent thực hiện bằng browser và Blender; extractor không tự chọn
pose trên website, bake pose hay xác minh hình ảnh. Giữ nguyên mặc định CLI.

### Trước khi tải

1. Xác định mục tiêu từ yêu cầu hiện có: chỉ tải file, mở xem bản tĩnh, Static Pose
   của viewer, hay animation cụ thể. Chỉ hỏi thêm khi các yêu cầu mâu thuẫn.
2. Mở trang model hoặc `/models/<uid>/embed`, đọc menu animation qua DOM/snapshot.
   Ghi nguyên tên clip; nếu chỉ có Static Pose và Take001 thì không gọi Take001 là Idle.
   Không thấy menu/không tải được danh sách là **chưa biết**, không phải **không có clip**.
3. Với mục tiêu xem tĩnh, chọn Static Pose nếu viewer có, xác nhận nhãn đã chọn
   và chụp reference. Với animation, chọn đúng clip, ghi thời điểm cần đối chiếu.
   Không suy ra trạng thái đã chọn chỉ vì đã bấm nút.
4. Nếu viewer/reference không truy cập được, ghi rõ hạn chế rồi tiếp tục tải nếu
   tài nguyên công khai vẫn truy cập được. Không vượt login/private hoặc hứa pose đúng.

Lượt tải bản tĩnh ứng viên cho Sketchfab:

```bash
python3 ~/.agents/skills/3d-model-download/scripts/download.py '<MODEL-URL>' --output ~/Downloads/3d-assets --no-animations --timeout 300
```

Nếu user muốn giữ animation, bỏ `--no-animations`. Router không có tùy chọn chọn
một clip theo tên; tải các clip nguồn rồi chọn clip cần kiểm tra trong Blender.
Không tự tải hai bản lớn nếu một bản đã đáp ứng mục tiêu. Khi phải thử bản khác,
giữ thư mục output riêng và dùng `file_path` thực tế trả về.

### Sau khi tải/import

1. Đọc `quality`/`diagnostics`: bản bỏ animation phải có animations bằng 0; đối chiếu
   skins/images với nguồn, không bắt model vốn không rig phải có rig. GLB hợp lệ
   chỉ là kiểm tra file, không phải kiểm tra pose.
2. Import vào scene/collection mới. Kiểm tra Action/NLA trên các object import và
   armature nếu có. Không zero bone, không xóa rig, không chỉ dừng playback rồi
   tuyên bố đã loại bỏ animation. Nếu bản tĩnh vẫn có animation, ghi nhận bất thường.
3. Material Preview, cùng hướng nhìn và toàn thân: so đầu/mũ, giáp thân, tay/chân,
   tỷ lệ và texture với reference. Tránh nền/sàn đi kèm làm sai đánh giá chiều cao
   nhân vật. Đổi hướng/kích thước qua root chung nếu cần, giữ các quan hệ tương đối.
4. Nếu kiểm tra clip động, đối chiếu đầu/giữa/cuối clip với viewer ở thời điểm
   tương ứng. Ghi frame, FPS và thời điểm clip; không so số frame giữa hai app
   khi chưa quy đổi thời gian. Clip được kiểm tra độc lập với Static Pose.
5. Nếu bản bỏ animation khác Static Pose: giữ file đó với nhãn **default pose chưa
   khớp viewer**; điều tra transform/bind/pose, chọn hoặc bake pose dựa trên bằng
   chứng trên bản sao. Không đổi nhãn thành Static Pose đúng hoặc tự sửa bone mù.
6. Lưu `.blend` đường dẫn mới sau khi kiểm tra, giữ attribution. Báo riêng trạng
   thái tải, import, pose và animation; kèm đường dẫn ảnh đối chiếu nếu đã lưu.

Mẫu báo cáo ngắn (agent điền bằng bằng chứng thật, không phải schema JSON CLI):

- File GLB / `.blend`: đường dẫn thực tế.
- Viewer: đọc được hay chưa; tên clip, pose/clip đã chọn, thời điểm nếu có.
- Bản tải: có/bỏ animation; rig và texture quan sát được.
- Pose: đã đối chiếu các chi tiết nào / chưa xác minh / còn lệch.
- Animation: clip và các mốc đã kiểm tra / chưa kiểm tra / vẫn lỗi.
- Reference và viewport: đường dẫn ảnh hoặc nêu rõ chưa có.

### Bài học Spartan (2026-10-06)

Model `57070b2fd9ff472c8988e76d8c5cbe66` lúc kiểm tra có **Static Pose + Take001**,
không có clip tên Idle. Bản `--no-animations` giữ rig/texture và được đối chiếu
ảnh Static Pose: không thấy lệch giáp/nổ mesh ở góc kiểm tra. Đây là bằng chứng
cho mẫu đó, không chứng minh mọi model bỏ animation đều khớp Static Pose và
không chứng minh lỗi của Take001 đã được sửa. Luôn đọc lại viewer cho lượt mới.

## Kiểm tra

```bash
python3 -B -m unittest discover -s ~/.agents/skills/3d-model-download/tests -v
npm --prefix ~/.agents/skills/3d-model-download/scripts/sketchfab/vendor/sketchfab_downloader_extension test
```

Xem `verification-2026-10-06.md` cho E2E Blu/Allom, tùy chọn bỏ animation và
Blender import. Để mở model dùng File → Import → glTF 2.0, không CLI-open GLB như `.blend`.
