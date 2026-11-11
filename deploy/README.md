# Triển khai EMSForecast

Web server dùng Python stdlib và snapshot đã tạo offline. Worker dự báo bảy ngày chạy riêng, cần môi trường Prophet/pandas/tzdata theo `requirements-live.txt`. Web không cần Torch hoặc checkpoint, nhưng worker vẫn thực hiện fit Prophet mỗi ngày.

## Kiểm tra trước khi đóng gói

Tại repo root:

```powershell
python -m ems.web
.\.venv\Scripts\python.exe -m unittest discover -s tests
node --test tests/*.test.mjs
node tests/test_web_operations.mjs
```

Snapshot `outputs/web/dataset.json` phải có đủ ba profile 24h và dữ liệu kế hoạch xe. Tạo lại theo [web/OPERATIONS.md](../web/OPERATIONS.md) nếu thay artifact. Chủ repo tự review, commit và push thay đổi cần xuất bản.

## Release bất biến

```powershell
python deploy/package_release.py
```

Lệnh in `release`, đường dẫn archive và SHA-256; tạo `deploy/<release>.tar.gz` cùng `deploy/release-manifest.json`. Các file này là sản phẩm build và được gitignore. Gói chứa web assets, server, snapshot lịch sử, worker và unit update; không chứa toàn bộ dữ liệu nghiên cứu hoặc Torch weights.

Hạ tầng hiện tại dùng `/home/charlotte/apps/emsforecast-releases`. Upload archive bằng SSH/SCP vào thư mục này. Trên VPS, truyền **tên release và SHA-256 đúng từ bước đóng gói** cho `activate_release.py`, theo giao thức stdin được ghi ở đầu script:

```bash
# From the repository copy available on the VPS:
python3 - RELEASE_NAME ARCHIVE_SHA256 < deploy/activate_release.py
```

Script dành cho VPS hiện có và user `charlotte`, không phải installer đa nền tảng. Nó kiểm tra checksum/đường dẫn archive, bung sang thư mục mới, chạy `verify_release.py`, cập nhật service, kiểm tra health/asset và hoàn nguyên service nếu kích hoạt lỗi. Symlink `/home/charlotte/apps/emsforecast-current` được cập nhật sau khi web healthy. Không dùng `git pull feat/demo` làm quy trình triển khai release.

`activate_release.py` cần quyền `sudo -n` phù hợp trên VPS. `verify_release.py` kiểm tra manifest và HTTP bằng stdlib, chỉ chạy trong release đã giải nén có `release-manifest.json` ở root. Nó không thay thế kiểm thử nghiệp vụ trước khi đóng gói.

## Dữ liệu và service

| Thành phần | Đường dẫn hiện tại |
| --- | --- |
| Code hiện hành | `/home/charlotte/apps/emsforecast-current` |
| JSON worker dùng chung | `/home/charlotte/apps/emsforecast-live` |
| Python worker | `/home/charlotte/apps/emsforecast-live-venv/bin/python` |
| Biến môi trường web | `EMS_LIVE_DIR=/home/charlotte/apps/emsforecast-live` |

Dữ liệu worker ở ngoài release nên đổi code không xóa lịch sử tải/forecast. Cài requirements-live vào venv worker và đối chiếu đường dẫn/user trong unit nếu dựng hạ tầng mới. Unit web/Caddy trong repo là mẫu theo hạ tầng hiện tại; kiểm tra cấu hình thực trước khi thay thế. Caddy chuyển tiếp đến loopback 8501; giữ nguyên các site block khác khi sửa proxy.

Timer chạy 07:00 America/Los_Angeles, random tối đa năm phút, persistent sau reboot. Unit update gọi worker từ symlink code hiện hành. Tránh đổi code worker giữa một refresh đang chạy.

```bash
curl -fsS http://127.0.0.1:8501/health
curl -fsS https://emsforecast.live/api/live-forecast
systemctl list-timers emsforecast-update.timer
sudo journalctl -u emsforecast -n 50 --no-pager
sudo journalctl -u emsforecast-update.service -n 50 --no-pager
```

Để rollback web, khôi phục `previous-emsforecast.service` được lưu trong release mới rồi daemon-reload/restart. Symlink code, timer và worker cần rollback đồng bộ riêng; script không tự hoàn nguyên toàn bộ hệ thống worker. Xem [LIVE-FORECAST.md](LIVE-FORECAST.md) về target, lịch cập nhật và hồ sơ release đã kiểm chứng.
