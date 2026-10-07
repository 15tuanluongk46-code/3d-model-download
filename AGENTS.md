# Agent guide — 3D downloader

- Đọc README, SETUP, SKILL và tài liệu nguồn trước chỉnh sửa. CLI `scripts/download.py` điều phối; `scripts/asset_io.py` xử lý asset; Sketchfab có helper Python và vendor JS.
- Python 3.11+, Linux baseline. Giữ attribution/vendor licenses. Không sửa vendor hàng loạt hoặc đổi schema output trong nhiệm vụ setup.
- Meshy/Rodin cần helper ngoài repo; báo thiếu phụ thuộc rõ ràng, không khẳng định hỗ trợ đã chạy trên máy mới.
- Chạy Python unittest và vendor Node tests theo SETUP. Không cần tải model live để test tài liệu. Khi thay extractor, kiểm tra đúng fixture và cả trạng thái partial/failure.
- Không coi parse GLB là proof chất lượng hình ảnh. Phân biệt kiểm tra file/hash và kiểm tra viewer.
- Không đọc hoặc publish cookie, profile, token, model riêng tư. Chỉ tải URL user yêu cầu; giữ giấy phép kèm metadata.
- Publish chỉ khi được yêu cầu: stage đúng file, kiểm tra secrets và diff, cập nhật hướng dẫn nếu command/dependency thay đổi, xác minh commit remote.
