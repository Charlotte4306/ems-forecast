# B?n tri?n khai hi?n t?i

?? tri?n khai ng?y 12/11/2026 t? working tree `feat/demo`, kh?ng commit/push.

- Website: https://emsforecast.live/overview
- Release: `20261111-180110-zenless-ui` (m? th?i gian UTC c?a m?y t?o g?i).
- Th? m?c ch?y: `/home/charlotte/apps/emsforecast-releases/20261111-180110-zenless-ui`.
- Archive SHA-256: `ccc6b3b44836add518c566f01058406b2cda23b788807916362ab536750766ed`.
- Giao di?n Zenless: font TT Hoves Pro Compact Bold, Tahoma, Impact; vi?n ?i?u khi?n d?ng vi?n ?en d?y; menu Th?m d?ng tam gi?c ??c.
- URL: `/overview`, `/forecast`, `/fleet-plan`, `/scenario-costs`, `/model-evaluation`, `/history`, `/settings`.
- URL c? d?ng hash ???c chuy?n sang ???ng d?n m?i; l?a ch?n m? h?nh d?ng d?u g?ch ngang trong URL.
- Service, Caddy v? checkout c? ???c gi? nguy?n c?u h?nh, ch? ??i WorkingDirectory c?a service sang release m?i.

?? x?c minh manifest tr??c khi k?ch ho?t; ki?m tra HTTP n?i b? v? c?ng khai tr?n c? 7 ???ng d?n; ??i chi?u hash c?c CSS/JS v? font m?i. Health domain ch?nh v? www tr? `ok`. Ki?m tra DOM local ??t v?i ng?y ?? 24 gi? v? ng?y cu?i 4 gi?, g?m chuy?n m?n v? l?u c?i ??t. Ch?a x?c minh ?nh render b?ng tr?nh duy?t.

B?n service tr??c ???c gi? t?i `/home/charlotte/apps/emsforecast-releases/20261111-180110-zenless-ui/previous-emsforecast.service`. C? th? kh?i ph?c b?ng `sudo install -m 644` file n?y v?o `/etc/systemd/system/emsforecast.service`, sau ?? ch?y `sudo systemctl daemon-reload` v? `sudo systemctl restart emsforecast`.

Nh?n Ctrl+F5 ?? t?i CSS/JS/font m?i.

## L?ch s? tri?n khai tr??c

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
