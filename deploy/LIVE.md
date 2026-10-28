# Bản triển khai hiện tại

Đã triển khai ngày 29/10/2026 theo giờ Việt Nam:

- Website: https://emsforecast.live
- Health: https://emsforecast.live/health
- Release: `20261029-frontend-01`
- Thư mục chạy: `/home/charlotte/apps/emsforecast-releases/20261029-frontend-01`
- Service: `emsforecast.service`, đã bật tự khởi động.
- Caddy chuyển HTTPS vào `127.0.0.1:8501`.
- Nguồn: working tree `feat/demo`, nền commit `199e394`. Không tạo commit/push khi triển khai.
- Archive SHA-256: `0c793cb0079b1c1510698aab05aa5a96e166123253d43e340bc61624113423af`.

Release chỉ chứa frontend, font, server Python stdlib và bộ kết quả 6.772 giờ.
Không cần cài PyTorch/Prophet trên VPS để hiển thị demo. Manifest ở
`release-manifest.json` trong thư mục release ghi hash từng file đã đóng gói.

## Quản lý trên VPS

```bash
sudo systemctl status emsforecast --no-pager
sudo systemctl restart emsforecast
sudo journalctl -u emsforecast -n 60 --no-pager
curl -fsS https://emsforecast.live/health
```

Checkout `/home/charlotte/apps/ems-forecast` được giữ nguyên. `git pull` trong
checkout đó chưa tự cập nhật bản live, vì service đang chạy từ thư mục release
riêng. Khi cập nhật, chuẩn bị release mới, kiểm tra rồi đổi WorkingDirectory của
service sang release đó. Cần commit/push riêng nếu muốn lưu code vào GitHub.

## Quay lại trang kiểm tra Caddy trước triển khai

Bản sao cấu hình cũ nằm tại:

`/home/charlotte/apps/emsforecast-releases/20261029-frontend-01/deploy/backups/Caddyfile`

```bash
sudo cp /home/charlotte/apps/emsforecast-releases/20261029-frontend-01/deploy/backups/Caddyfile /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Thao tác này đưa domain về trang kiểm tra cũ, không xóa dữ liệu hoặc release.
Service có thể dừng bằng `sudo systemctl stop emsforecast` nếu không còn dùng.
