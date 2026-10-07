# Hướng dẫn bảo trì repo

- Skill chính ở gốc; helper được đóng gói tại `bundled-skills/meshy-rodin-download`.
  Router dùng bản helper đã cài ở `~/.agents/skills/meshy-rodin-download`.
  Khi bàn giao, làm theo SETUP.md để cài hai skill ngang hàng.
- Giữ tên skill, notices và license upstream. Không commit model tải về,
  cache, browser state, credentials hoặc signed URLs.
- Khi đồng bộ helper từ bản cài, so sánh nội dung và kiểm tra trước khi thay thế;
  không tự ghi đè các thay đổi chưa xác định nguồn gốc.
- Chạy từ root repo:
  - `python3 -B -m unittest discover -s tests -v`
  - `npm --prefix scripts/sketchfab/vendor/sketchfab_downloader_extension test`
  - `python3 -B -m unittest discover -s bundled-skills/meshy-rodin-download/tests -v`
  - `node --check bundled-skills/meshy-rodin-download/scripts/decrypt.mjs`
  - `uvx ruff check --no-cache bundled-skills/meshy-rodin-download/scripts bundled-skills/meshy-rodin-download/tests`
- Chỉ commit/push khi user yêu cầu; xác minh repo private, commit remote và
  trạng thái working tree trước khi báo đã publish. Không thay git config toàn cục.
- Cập nhật README/SETUP khi dependency, đường dẫn cài hoặc lệnh thay đổi.
- Đọc README, SETUP, SKILL và tài liệu nguồn trước chỉnh sửa. CLI `scripts/download.py` điều phối; `scripts/asset_io.py` xử lý asset; Sketchfab có helper Python và vendor JS.
- Python 3.11+, Linux baseline. Giữ attribution/vendor licenses. Không sửa vendor hàng loạt hoặc đổi schema output trong nhiệm vụ setup.
- Meshy/Rodin cần helper được cài ngang hàng theo SETUP; báo thiếu phụ thuộc rõ ràng, không khẳng định hỗ trợ đã chạy trên máy mới.
- Chạy Python unittest và vendor Node tests theo SETUP. Không cần tải model live để test tài liệu. Khi thay extractor, kiểm tra đúng fixture và cả trạng thái partial/failure.
- Không coi parse GLB là proof chất lượng hình ảnh. Phân biệt kiểm tra file/hash và kiểm tra viewer.
- Không đọc hoặc publish cookie, profile, token, model riêng tư. Chỉ tải URL user yêu cầu; giữ giấy phép kèm metadata.
- Publish chỉ khi được yêu cầu: stage đúng file, kiểm tra secrets và diff, cập nhật hướng dẫn nếu command/dependency thay đổi, xác minh commit remote.
