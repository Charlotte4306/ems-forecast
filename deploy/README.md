# Web demo trên Azure VPS hiện có

Ứng dụng dùng HTML/CSS/ES modules và server Python stdlib; không có npm build,
Streamlit, framework hoặc thư viện mô hình cần cài trên VPS. Môi trường mô hình
chỉ cần để xuất lại bộ dữ liệu sau khi thay checkpoint/dữ liệu.

## Chạy trên Windows

Tại repo, dùng bộ dataset đã lưu hoặc tạo lại bằng môi trường ML:

```powershell
.\.venv\Scripts\python.exe -m ems.web.export
python -m ems.web
```

Mở `http://127.0.0.1:8501`. Export chỉ nạp checkpoint LSTM và kết quả Prophet
đã commit, không train hoặc fit lại scalers. Bộ dữ liệu công khai nằm ở
`outputs/web/dataset.json`, gồm nguồn và hash của các file liên quan.

Các mốc giờ được giữ nguyên dạng CSV; không tự quy đổi sang giờ Việt Nam.

## Đưa code lên VPS

Chủ repo tự commit/push `feat/demo`, gồm cả `outputs/web/dataset.json` và font.
Các lệnh dưới đây chạy trong Ubuntu VPS đã clone repository:

```bash
cd ~/apps/ems-forecast
git fetch origin
git switch feat/demo
git pull --ff-only origin feat/demo
python3 --version
python3 -m ems.web
```

Mở một SSH khác và kiểm tra `curl -fsS http://127.0.0.1:8501/health`.
Không cần `.venv`, pip hoặc tải lại checkpoint để phục vụ giao diện.
Muốn xem thử qua máy Windows, dùng SSH tunnel:

```powershell
ssh -i "C:\Users\Charlote\.ssh\vm-emsforecast_key.pem" -L 8502:127.0.0.1:8501 charlotte@20.198.177.172
```

Truy cập `http://127.0.0.1:8502`. Dừng tiến trình chạy thử bằng Ctrl+C trước khi
bật service.

## Service và Caddy

Đối chiếu user/thư mục trong `deploy/emsforecast.service` nếu đổi vị trí clone.

```bash
cd ~/apps/ems-forecast
sudo install -m 644 deploy/emsforecast.service /etc/systemd/system/emsforecast.service
sudo systemctl daemon-reload
sudo systemctl enable --now emsforecast
curl -fsS http://127.0.0.1:8501/health
```

Chỉ chuyển Caddy khi health check trả `ok`:

```bash
sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.before-ems-demo
sudo caddy validate --config deploy/Caddyfile --adapter caddyfile
sudo install -m 644 deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
curl -I https://emsforecast.live
```

File mẫu chứa hai host hiện có. Nếu Caddy đã có site block khác, giữ các block
đó. Chỉ mở cổng web 80/443; ứng dụng ở loopback 8501.

## Cập nhật / xem lỗi

```bash
cd ~/apps/ems-forecast
git pull --ff-only
sudo systemctl restart emsforecast
sudo journalctl -u emsforecast -n 60 --no-pager
```

Server chỉ cung cấp asset frontend, dataset công khai và health; không cung cấp
file nguồn Python hay checkpoint. Server ThreadingHTTPServer phục vụ demo lớp
học sau Caddy; khi phát triển thành dịch vụ thực tế cần bổ sung nền tảng API,
giám sát và các yêu cầu vận hành tương ứng.
