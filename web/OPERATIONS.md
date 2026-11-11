# Preview vận hành EMSForecast

Chạy từ thư mục gốc sau khi kích hoạt `.venv`:

```powershell
python -m ems.web --port 8502
```

Mở http://127.0.0.1:8502. Mặc định Prophet 24h, Trung bình, mức bận 80%, ba ca bắt đầu từ 00:00 và chi phí thiếu/thừa 3:1. Ngày, mô hình và kịch bản giữ nguyên khi chuyển màn.

## Chuẩn bị dữ liệu offline

```powershell
python -m ems.web.prepare_operations --source-ref d5645d20ad9d6835d0895744364cac4f631f33eb
```

Lệnh đọc code, dữ liệu, scaler và checkpoint từ revision đã chỉ định trong thư mục tạm; chạy inference LSTM 24h, không train/refit, không checkout hoặc sửa file mô hình. Cập nhật `outputs/web/dataset.json` có sẵn, giữ các trường legacy/profile Prophet 1h và bổ sung ba profile 24h cùng kết quả năng lực, báo cáo chi phí và hash nguồn. Nếu đang tạo snapshot từ đầu, chạy quy trình export/prepare_dashboard hiện có trước.

Backend `/api/dataset` phục vụ snapshot đó; VPS không cần Torch/Prophet hay checkpoint. Không có inference theo yêu cầu, upload CSV hoặc cập nhật dữ liệu trực tiếp trong phạm vi này.

Chi phí là điểm kịch bản. Nhu cầu xe đối chiếu được ước tính từ lượt điều động thực tế và thời gian bận, không phải số xe trực thực tế. Bảng ca chỉ chấm 6.792 giờ; bốn giờ cuối của 6.796 giờ test chưa đủ ca. Các phương án Trung bình/P90 được chốt trước; so sánh chi phí trên test chỉ mang tính hậu kiểm.

## Kiểm tra

```powershell
python -m unittest discover -s tests -p "test_web*.py"
node tests/test_web_operations.mjs
```

Kiểm tra DOM tùy chọn dùng jsdom cài ngoài repo:

```powershell
node scripts/check_web_reference.mjs <duong-dan-jsdom/lib/api.js> "?profile=lstm_h24&day=2026-10-11#chiphi"
```
