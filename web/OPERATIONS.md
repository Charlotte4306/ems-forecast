# Vận hành giao diện

Chạy tại repo root: `python -m ems.web --port 8501`, mở http://127.0.0.1:8501. Server dùng Python stdlib, không huấn luyện theo request và không nhận upload CSV.

Mặc định UI là Prophet 24h, chính sách Trung bình, mức bận 80%, ba ca từ 00:00 và chi phí thiếu/thừa 3:1. Ngày/profile/kịch bản được giữ khi chuyển màn. Dự báo 7 ngày nằm sau Đánh giá mô hình.

## Snapshot thí nghiệm lịch sử

`outputs/web/dataset.json` có `profiles` và `operations`. Không còn bảng root `rows` của demo hai mô hình cũ hoặc metadata “ARIMA chưa có”. Bốn profile hiện tại: Prophet 1h, Prophet 24h, SARIMAX 24h no-refit, LSTM 24h block.

Tạo lại từ đầu bằng môi trường ML:

```powershell
.\.venv\Scripts\python.exe -m ems.web.prepare_dashboard
.\.venv\Scripts\python.exe -m ems.web.prepare_operations --source-ref HEAD
```

Bước đầu tạo profile Prophet 1h từ CSV trong working tree. Bước hai đọc ba dự báo 24h và kết quả năng lực từ **Git revision đã commit**, chạy inference LSTM với code/data/scalers/weights của revision đó trong thư mục tạm. Không train, refit hoặc checkout. `HEAD` phải là revision chứa các artifact mong muốn; thay bằng hash cụ thể để cố định nguồn. Thay đổi chưa commit không được bước hai đọc.

Cả hai hỗ trợ `--destination <path>` để xuất thử. Sau bước đầu snapshot chưa có đủ dữ liệu vận hành; hoàn thành bước hai trước khi sử dụng. `--prophet24-ref <revision>` của bước đầu là tùy chọn để chỉ thêm Prophet 24h, không thay thế bước chuẩn bị vận hành.

Kết quả phải cùng timestamp/actual trên 6.796 giờ. Kế hoạch ca chỉ chấm 6.792 giờ, bỏ bốn giờ cuối chưa đủ ca. Trung bình/P90 được chốt trước test; chi phí là điểm kịch bản, không phải tiền thật. Nhu cầu xe đối chiếu là đầu ra của công thức workload, không phải roster.

## Dữ liệu tự động

`python -m ems.live.update --output-dir outputs/live` tải aggregate DataSF và tạo forecast bảy ngày bằng Prophet mùa vụ riêng. Server đọc ở `EMS_LIVE_DIR` hoặc `outputs/live`. Snapshot có target `medic-dispatches`, `timeField=received_dttm`; snapshot cũ theo số cuộc gọi hoặc dispatch-time bị từ chối. Worker và timer được mô tả trong [LIVE-FORECAST.md](../deploy/LIVE-FORECAST.md).

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_web*.py"
node --test tests/*.test.mjs
node tests/test_web_operations.mjs
node scripts/check_web_reference.mjs <path-to-jsdom/lib/api.js>
```

Xem [triển khai release](../deploy/README.md) và [thiết kế UI](DESIGN.md). Việc sửa code local không tự cập nhật server đã triển khai.
