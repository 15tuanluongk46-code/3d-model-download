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
