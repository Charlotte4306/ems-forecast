# Bản triển khai hiện tại

Đã triển khai ngày 10/11/2026 từ working tree `feat/demo`, không commit/push.

- Website: https://emsforecast.live
- Health: https://emsforecast.live/health (và www) trả `ok`.
- Release: `20261110-081915-reference-ui`
- Thư mục chạy: `/home/charlotte/apps/emsforecast-releases/20261110-081915-reference-ui`
- Service: `emsforecast.service`, chạy Python stdlib trên `127.0.0.1:8501`.
- Caddy và cấu hình các domain được giữ nguyên.
- Archive SHA-256: `be827e4e3a5459c7ffe2aed8aca84ebebb699d8a7e0e4adbb96504bc9fb5d6d2`.

Giao diện giữ CSS và hiệu ứng của HTML mẫu; font IBM Plex Sans 400/500/600
được phục vụ cục bộ. Dữ liệu Prophet 1 giờ và 24 giờ có 6.796 giờ mỗi bộ.
Không cần chạy Prophet/PyTorch hoặc cài thư viện mô hình trên VPS.
Bản ghi raw, năng lực và chi phí chưa có dữ liệu sẽ để dấu “—”.

Đã kiểm tra manifest/hash trước khi chuyển service, chạy HTTP smoke test
trên loopback, rồi đối chiếu qua HTTPS công khai: HTML, CSS, JS và cả ba font
khớp file local. API đủ hai bộ 6.796 giờ, health cả hai domain trả `ok`.
Đây là kiểm tra HTTP/dữ liệu, không phải xác nhận ảnh render trong trình duyệt.

Manifest từng file nằm trong `release-manifest.json` tại thư mục release.
Checkout `/home/charlotte/apps/ems-forecast` không bị thay đổi. `git pull` ở
checkout không tự cập nhật service đang chạy từ thư mục release riêng.

## Quản lý trên VPS

```bash
sudo systemctl status emsforecast --no-pager
sudo journalctl -u emsforecast -n 60 --no-pager
curl -fsS https://emsforecast.live/health
```

## Quay về bản trước

Bản service trước khi triển khai được lưu tại:
`/home/charlotte/apps/emsforecast-releases/20261110-081915-reference-ui/previous-emsforecast.service`.
Bản release cũ `20261029-frontend-01` được giữ lại.

```bash
sudo install -m 644 /home/charlotte/apps/emsforecast-releases/20261110-081915-reference-ui/previous-emsforecast.service /etc/systemd/system/emsforecast.service
sudo systemctl daemon-reload
sudo systemctl restart emsforecast
curl -fsS https://emsforecast.live/health
```

Khi mở bản mới, nhấn Ctrl+F5 để tải lại CSS, JavaScript và font.
