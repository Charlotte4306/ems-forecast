# Chuẩn bị dữ liệu thời gian xe bận

Module `ems.capacity.prepare_busy_time` dùng chung cho ba mô hình nhưng không phụ
thuộc mô hình nào. Nó đọc raw, chỉ xét MEDIC, giữ bản ghi gốc kèm cờ kiểm tra và
xuất thời gian xe bận để chuẩn bị cho phần lập kế hoạch năng lực.

## Chạy lại

Tại project root, thay đường dẫn dưới đây bằng vị trí raw đã tải:

```powershell
.\.venv\Scripts\python.exe -m ems.capacity.prepare_busy_time --raw-files "C:\duong-dan-raw\sf_ems_2025.csv" "C:\duong-dan-raw\sf_ems_2026.csv"
```

Đầu ra mặc định: `outputs/capacity/medic_busy_time/`. Không sao chép raw vào repo.
`--output-dir` thay vị trí kết quả; chạy lại cùng thư mục sẽ ghi đè các file dẫn xuất.
Không truyền cả file năm và file tháng nằm trong năm đó nếu không chủ ý kiểm tra
nguồn lặp. Hàng trùng các trường liên quan được gắn cờ; phiên bản cùng call/unit
nhưng khác nội dung bị loại khỏi tính toán để kiểm tra thủ công.

Các lựa chọn:

- `--calibration-start 2025-01-01`: bắt đầu giai đoạn hiệu chỉnh.
- `--calibration-end 2026-01-01`: kết thúc, không bao gồm mốc này đối với thời điểm điều động.
- `--max-calibration-hours 24`: ngưỡng thời lượng bận dùng khi hiệu chỉnh, có thể
  thay đổi để kiểm tra độ nhạy. Không phải giới hạn nghiệp vụ đã được xác minh.

Muốn hiệu chỉnh cho validation 2025, cần raw trước năm 2025 (ví dụ 2024) và đổi
cửa sổ tương ứng. Kết quả từ raw 2025 không được dùng cho dự báo phát hành đầu 2025.

## Ý nghĩa đại lượng

| Đại lượng | Cách tính | Giới hạn |
| --- | --- | --- |
| Thời gian bận từng lượt | available - dispatch | Không tự sửa thời gian âm hoặc suy đoán giờ thiếu |
| Độ trễ điều động | dispatch - received | Không phải thời gian chờ điện thoại hoặc thời gian đến hiện trường |
| Xe-giờ bận quan sát | Gộp khoảng chồng của cùng xe, chia thời gian theo giờ | Thiếu các nhiệm vụ không nằm trong raw được cung cấp |
| Số xe bận đồng thời cao nhất | Đếm khoảng bận hợp lệ giao nhau | Không phải số xe trực hay số xe tối ưu |
| Cuộc gọi có MEDIC | Đếm call_number khác nhau theo giờ nhận | Không phải tổng mọi cuộc gọi tới tổng đài |

Khoảng bận dùng quy ước `[dispatch, available)`: xe kết thúc đúng 09h không còn
bị tính bận ở giờ 09h nếu không có nhiệm vụ khác. Bản ghi chồng thời gian được
giữ và xuất riêng để kiểm tra. Phân bố thời lượng từng lượt vẫn là thống kê theo
bản ghi; gộp khoảng được áp dụng riêng khi tính khối lượng đồng thời.

Các lượt thời lượng dương dưới 1 phút có cờ xem lại nhưng chưa bị loại mặc định:
nhiệm vụ ngắn/hủy có thể là thật. Những lượt không vận chuyển bệnh nhân chưa bị
loại vì vẫn có thể chiếm nguồn lực xe. Độ trễ điều động trên 24h không dùng hiệu
chỉnh độ trễ; đây là ngưỡng kiểm tra được ghi rõ, không tự thay thời gian gốc.

`source_record` là thứ tự bản ghi dữ liệu trong file, bắt đầu từ 1 và không tính
header. Hash nguồn được lưu trong `audit.json` để kiểm tra tái lập.

## Kết quả đã chạy trên raw 2025 và 2026

- Đã đọc 650.992 bản ghi mọi loại đơn vị, giữ 179.668 bản ghi MEDIC.
- Năm 2025: 100.320 lượt, 94.420 mã cuộc gọi; thiếu available 1, thời lượng bận
  âm 606, bằng 0 là 5. Có 99.708 khoảng bận dương hợp lệ.
- Năm 2026 trong raw cung cấp: 79.348 lượt, 74.881 mã cuộc gọi; thiếu available 5,
  thời lượng bận âm 416, bằng 0 là 5. Có 78.922 khoảng bận dương hợp lệ.
- Không phát hiện trùng các trường dùng trong phân tích hoặc phiên bản xung đột
  của cùng cặp call_number/unit_id trong hai file này.
- Có 11 bản ghi chồng khoảng bận của cùng unit_id; đã gộp khi tính khối lượng.

Tham số bận từ năm 2025 dùng cho thời điểm dự báo từ 01/01/2026:

| Thống kê | Giá trị |
| --- | ---: |
| Số lượt hiệu chỉnh | 99.694 |
| Trung bình | 63,3805 phút |
| Trung vị | 70,2667 phút |
| P90 | 110,6333 phút |
| P95 | 123,6333 phút |

14 lượt hợp lệ của tập 2025 chưa kết thúc trước mốc chốt hoặc có thời điểm điều
động ngoài cửa sổ hiệu chỉnh nên không dùng hiệu chỉnh. Các lượt này không bị
xóa khỏi thống kê mô tả hoặc tính khối lượng quan sát.

Đây chưa phải xác nhận dữ liệu sạch tuyệt đối. Chưa hiệu chỉnh timezone/DST,
chưa xác định nguyên nhân từng thời lượng âm hoặc bản ghi chồng. Không dùng
thống kê 2026 để chọn tham số cho đánh giá 2026.

Xem báo cáo tạo từ dữ liệu thực tế ở `outputs/capacity/medic_busy_time/report.md`,
cùng `quality_summary.csv`, `calibration_parameters.json` và biểu đồ phân bố.
Chưa tính lịch trực, số xe tối ưu hay chi phí; chưa có nguồn roster và đơn giá thật.
