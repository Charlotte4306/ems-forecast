# Chuẩn bị thời gian xe MEDIC bận từ raw

Phân tích riêng dữ liệu nguồn; không sửa CSV dự báo, checkpoint hoặc kết quả mô hình.

## Chất lượng dữ liệu

Các cờ có thể trùng nhau, không cộng các cột cờ thành tổng số hàng lỗi.

| Nguồn | Dòng MEDIC | Thiếu available | Bận âm | Bận bằng 0 | Bận > ngưỡng | Khoảng bận hợp lệ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| sf_ems_2025.csv | 100320 | 1 | 606 | 5 | 0 | 99708 |
| sf_ems_2026.csv | 79348 | 5 | 416 | 5 | 0 | 78922 |

## Phân bố thời gian bận

Thời gian bận = available_dttm - dispatch_dttm; đơn vị phút.

| Phạm vi | Số lượt dùng | Trung bình | Trung vị | P90 | P95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| sf_ems_2025.csv | 99708 | 63.3830 | 70.2667 | 110.6383 | 123.6333 |
| sf_ems_2026.csv | 78922 | 63.6799 | 71.4167 | 109.8317 | 121.5325 |
| historical_calibration | 99694 | 63.3805 | 70.2667 | 110.6333 | 123.6333 |

## Quy tắc dùng tham số

- Cửa sổ hiệu chỉnh: từ 2025-01-01 00:00:00 đến trước 2026-01-01 00:00:00.
- Chỉ dùng thời lượng đã biết tại mốc chốt: available không sau mốc kết thúc hiệu chỉnh.
- Chỉ dùng tham số này cho thời điểm dự báo từ mốc chốt trở đi. Không dùng tham số 2025 cho validation năm 2025.
- Loại khỏi hiệu chỉnh các lượt bận không dương hoặc vượt 24 giờ. Đây là ngưỡng kiểm tra có thể đổi, không phải giới hạn nghiệp vụ đã xác minh.
- Số liệu 2026 là mô tả/đối chiếu, không tham gia ước lượng tham số cho dự báo 2026.
- Các lượt bận dưới 1 phút được gắn cờ để xem lại nhưng vẫn giữ trong thống kê nếu thời gian dương. Chưa tự loại nhiệm vụ hủy hoặc chỉ phục vụ tại hiện trường.
- Độ trễ nhận cuộc gọi đến điều động trên 24 giờ được gắn cờ và không dùng hiệu chỉnh độ trễ. Không tự đổi ngày/thời gian gốc.

## Khối lượng xe bận theo giờ

Mỗi xe được gộp các khoảng [dispatch, available) chồng nhau trước khi tính số xe bận đồng thời. Nhiệm vụ kéo dài qua giờ được chia đúng số phút cho từng giờ.
- Có 11 bản ghi bắt đầu khi cùng unit_id vẫn còn khoảng bận trước đó.
- Tổng thời gian bận sau khi gộp: 189090.6336 xe-giờ.
- Số xe bận đồng thời quan sát cao nhất: 32.
- Đây không phải số xe đang trực, số xe còn rảnh hay số xe tối ưu cần bố trí.

## Các file để sử dụng

- `medic_busy_records.csv`: từng bản ghi MEDIC, thời lượng, cờ chất lượng và nguồn/bản ghi gốc.
- `records_for_review.csv`: các hàng cần kiểm tra; không tự sửa thời gian âm.
- `quality_summary.csv`, `busy_time_distribution.csv`: bảng thống kê.
- `calibration_parameters.json`: tham số lịch sử để dùng tiếp cho năng lực.
- `unioned_busy_intervals.csv`, `overlapping_assignments.csv`: các khoảng đã gộp và bằng chứng chồng thời gian.
- `hourly_observed_workload.csv`: xe-giờ bận, số xe bận đồng thời cao nhất, lượt đáp ứng theo giờ nhận cuộc gọi và số bắt đầu điều động.
- `audit.json`: hash nguồn, quy tắc và giới hạn để tái lập.

## Giới hạn

- Giữ nguyên timestamp không timezone; chưa xử lý giờ mùa hè DST. Không kết luận thời gian âm đều do một nguyên nhân.
- Raw theo giai đoạn nhận cuộc gọi có thể thiếu nhiệm vụ từ giai đoạn trước và các lượt của giai đoạn sau. Giờ biên được đánh dấu, không coi là đầy đủ.
- Chưa có roster/xe rảnh hoặc đơn giá tiền thật. Không tự suy ra từ số unit_id khác nhau.
- Chưa chọn mô hình hàng đợi, mức dự phòng, lập lịch hay tính chi phí. Đây chỉ là phần chuẩn bị dữ liệu.
