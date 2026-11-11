# Prophet: dự báo trước cả ngày từ checkpoint hiện có

Chế độ bổ sung giữ nguyên cấu trúc mô hình và dữ liệu. `--forecast-24h` đánh giá
checkpoint có sẵn, không huấn luyện lại. `--select-24h` huấn luyện bốn cấu hình trên
train, chọn riêng theo MAE validation 24 giờ và lưu checkpoint mới ở thư mục riêng.
Chế độ một giờ hiện có vẫn chạy bằng `python main.py prophet` (lệnh đó sẽ huấn luyện).

## Luồng dự báo

1. Tại 00h, sau khi có số thực tế của khung 23h ngày trước, tạo đầu vào cho giờ 00h.
2. Dự báo giờ 00h, đưa dự báo vào lịch sử tạm để tạo lag, rolling và EWM cho giờ 01h.
3. Tiếp tục tới giờ 23h; tuyệt đối không lấy thực tế của ngày đang dự báo để tạo đặc trưng.
4. Sau khi hoàn thành cả khối, cập nhật lịch sử bằng số thực tế của ngày đó để
   dự báo ngày tiếp theo. Tham số mô hình không đổi.

Rolling dùng độ lệch chuẩn mẫu (`ddof=1`). EWM dùng `span=24/168, adjust=False`;
trạng thái ban đầu được khôi phục từ EWM đã dịch một giờ và mục tiêu cuối lịch sử,
không khởi tạo lại EWM từ một cửa sổ ngắn. Các cột đặc trưng sẵn trong tập đánh giá
không được truyền vào mô hình. Mỗi dự báo được chặn dưới ở 0 và không làm tròn.

Với mô hình Prophet MAP có regressors cộng như hiện tại, chương trình tính trước
xu hướng/mùa vụ theo lịch và dùng hệ số regressors trên thang đo gốc để cập nhật
từng bước. Cách này giữ nguyên phương trình dự báo, chỉ giảm số lần gọi hàm dự báo
đầy đủ. Test đối chiếu với `Prophet.predict` từng bước dùng sai số tuyệt đối 1e-10.
Các trường hợp không hỗ trợ cách tính nhanh sẽ dùng lại đường dự báo thông thường.

Đây là backtest trên CSV lịch sử, chưa phải API dự báo tương lai tùy ý. Timestamp
giữ quy ước giờ không timezone của bộ dữ liệu; chưa xử lý lại DST của San Francisco.
Quy ước 00h giả định số thực tế giờ trước đã sẵn sàng, không mô phỏng độ trễ công bố.

## Cách chạy tại project root (PowerShell)

Thử hai ngày validation, không đụng kết quả một giờ hoặc checkpoint:

```powershell
.\.venv\Scripts\python.exe main.py prophet --forecast-24h --forecast-split val --max-days 2 --output-dir outputs/prophet/day_ahead_24h/val_smoke
```

Đánh giá toàn bộ validation hoặc test:

```powershell
.\.venv\Scripts\python.exe main.py prophet --forecast-24h --forecast-split val
.\.venv\Scripts\python.exe main.py prophet --forecast-24h
```

Mặc định lưu riêng vào `outputs/prophet/day_ahead_24h/val` hoặc `test`. Chạy lại cùng
đường dẫn sẽ ghi đè kết quả của chế độ 24 giờ tại đó. Có thể đổi `--output-dir`.
Không sửa JSON checkpoint, dữ liệu nguồn hay kết quả một giờ.

## Chọn cấu hình dành riêng cho 24 giờ

```powershell
.\.venv\Scripts\python.exe main.py prophet --select-24h
```

Lệnh chỉ đọc train/validation, không đọc hoặc đánh giá test. Bốn ứng viên là
có/không 14 regressors, kết hợp `changepoint_prior_scale` 0.01/0.05. Mỗi ứng viên
fit dữ liệu train đến cuối 2024; dự báo toàn bộ 365 ngày validation 2025 theo
khối 24 giờ, cập nhật thực tế sau mỗi khối và không refit trong năm validation.
Chọn MAE toàn bộ 8.760 giờ thấp nhất; MAPE/RMSE vẫn được báo cáo, không dùng test
để chọn. Không refit train+validation sau lựa chọn.

- Bảng ứng viên: `outputs/prophet/day_ahead_24h/selection/validation_results.csv`.
- Dự báo validation của từng ứng viên và ứng viên thắng được lưu cùng thư mục.
- Cấu hình, điểm, hash và chính sách chọn: `selection.json`.
- Checkpoint mới: `checkpoints/prophet/day_ahead_24h/best_model.json`, kèm metadata.
- Không ghi đè checkpoint một giờ tại `checkpoints/prophet/best_model.json`.

Khi đã chốt chính sách so sánh với nhóm, đánh giá test **bằng checkpoint mới**:

```powershell
.\.venv\Scripts\python.exe main.py prophet --forecast-24h --checkpoint-dir checkpoints/prophet/day_ahead_24h --output-dir outputs/prophet/day_ahead_24h/test_selected
```

Lưu ý: `--forecast-24h` không truyền `--checkpoint-dir` vẫn dùng checkpoint một
giờ ban đầu. Hai kết quả được tách rõ, không tự động thay đổi ý nghĩa lệnh cũ.

## Kết quả validation đã chạy

Thực hiện trên nhánh `feat/prophet-24h`, fit train 2019-01-08 đến 2024-12-31,
đánh giá toàn bộ 2025: 365 ngày, 8.760 giờ, phát hành mỗi ngày lúc 00h.

| Cấu hình | MAE | RMSE | MAPE (%) |
| --- | ---: | ---: | ---: |
| Chỉ xu hướng/mùa vụ, prior 0.01 | 3.153498 | 4.052920 | 36.867477 |
| Chỉ xu hướng/mùa vụ, prior 0.05 | 3.152649 | 4.054392 | 36.750292 |
| Thêm 14 regressors, prior 0.01 | 3.111779 | 3.990470 | 36.430800 |
| **Thêm 14 regressors, prior 0.05** | **3.105928** | 3.992876 | **36.015295** |
| Baseline cùng giờ tuần trước | 4.181164 | 5.395574 | 45.800729 |

Chọn `prophet_lags_cp0.05` theo MAE không làm tròn. Cấu hình này cũng có MAPE
thấp nhất, nhưng RMSE thấp nhất thuộc cấu hình lags prior 0.01. MAE của ứng viên
được chọn thấp hơn baseline khoảng 25,72% trên validation.

Đánh giá riêng checkpoint một giờ ban đầu theo 24 giờ cũng đạt MAE 3.105928,
MAPE 36.015295%. Việc chọn lại xác nhận cùng cấu hình thắng trong bốn ứng viên;
không tạo ra cải thiện giả so với checkpoint ban đầu. Chưa khẳng định kết quả
so sánh cuối cùng với SARIMAX/LSTM nếu quy trình chưa được đồng nhất.

Sai số theo `lead_hour` cũng đồng thời phân theo giờ trong ngày (bước 1 là 00h,
bước 24 là 23h); không thể dùng riêng bảng này để khẳng định sai số tăng chỉ do
chân trời dự báo mà bỏ qua khác biệt nhu cầu giữa các giờ.

## Kết quả test đủ 6.796 giờ

Đã sửa quy tắc bỏ ngày cuối chưa đủ 24 giờ. Kết quả mới bao gồm tất cả khung giờ
từ 01/01/2026 00h đến 11/10/2026 03h: 283 khối đủ ngày và 1 khối được chấm 4 giờ.
Khối cuối vẫn tạo 24 bước dự báo; chỉ trả kết quả và tính điểm cho các giờ có
nhãn thực tế. Không dùng nhãn giả, không huấn luyện lại hoặc chọn cấu hình bằng test.

| Chỉ số | Prophet 24h, cấu hình đã chọn trên validation |
| --- | ---: |
| MAE | 3.050050 |
| RMSE | 3.966254 |
| MAPE (%) | 32.748853 |
| R2 | 0.364043 |

Kết quả tại `outputs/prophet/day_ahead_24h/test_selected/`. Thư mục `test/` dùng
checkpoint một giờ ban đầu cũng đã được cập nhật đủ giờ, cho kết quả giống nhau
vì cấu hình được chọn và trọng số tương ứng trùng nhau trong lần chạy này.
Đã kiểm tra đúng toàn bộ timestamp/nhãn test và các dự báo cũ không thay đổi.
Chỉ khác số giờ được chấm và các chỉ số tổng hợp do bổ sung bốn giờ cuối.

## Kết quả

- `predictions_24h.csv`: thời điểm phát hành (`forecast_origin`), khung lịch sử cuối
  được biết (`history_cutoff`), bước dự báo 1-24 (`lead_hour`), giờ mục tiêu (`ds`),
  dự báo (`yhat`), thực tế (`y`) và baseline cùng giờ tuần trước.
- `metrics.json`: quy trình, hash dữ liệu/checkpoint, mốc fit, MAE/RMSE/MAPE/R2
  tổng thể, baseline và kết quả theo bước dự báo.
- `metrics_by_lead.csv`: kiểm tra sai số ở các bước 1 tới 24.
- `metrics_by_day.csv`: kiểm tra sai số theo ngày.

Đánh giá tất cả giờ có thực tế: với bộ test hiện tại là **6.796 giờ**, gồm 283 ngày
đầy đủ và 4 giờ 00h–03h ngày 11/10/2026. Khối cuối vẫn phát hành dự báo 24 giờ từ
00h, nhưng chỉ chấm 4 giờ có nhãn; không điền nhãn giả cho 20 giờ còn lại.
`metrics_by_day.csv` có cột `n_hours` để nhận biết ngày cuối chỉ chấm 4 giờ.
`--max-days` chỉ chạy những ngày đầu, không được coi là đánh giá đầy đủ.
`lead_hour=1` là giờ bắt đầu ngay tại thời điểm phát hành;
`lead_hour=24` là khung cuối cùng của ngày, không phải 24h dữ liệu thực tế mới.

## Giới hạn và cách dùng trong báo cáo

- Biến mục tiêu trong CSV vẫn tên `call_count`; validation/test đã đối chiếu là
  lượt đáp ứng MEDIC theo giờ nhận cuộc gọi, không phải số cuộc gọi duy nhất.
  Việc đổi chế độ dự báo không thay đổi đại lượng mục tiêu.
- Checkpoint ban đầu được chọn theo MAE validation **một giờ** và fit đến cuối 2024.
  Chạy `--forecast-24h` không tự chọn lại cấu hình. Chạy `--select-24h` mới lựa chọn
  dành riêng cho 24 giờ. Chỉ được gọi là tốt nhất trong bốn cấu hình đã thử trên
  validation, không phải mô hình tối ưu tuyệt đối hay đã thắng trên test.
- Khi đánh giá test, thực tế 2025 được dùng làm lịch sử đặc trưng nhưng không dùng
  học lại hệ số. Phải thống nhất chính sách fit/refit khi so sánh với mô hình khác.
- Để chọn cấu hình riêng cho 24 giờ, đánh giá các ứng viên trên validation theo
  đúng chế độ này, chốt lựa chọn trước khi xem điểm test. Không chọn bằng test.
- Sai số có thể tích lũy khi dự báo nối tiếp. Chỉ so điểm với SARIMAX/LSTM trên cùng
  các giờ, thời điểm phát hành, horizon và cùng chính sách huấn luyện đã thống nhất.
- Checkpoint hiện tại tắt khoảng bất định; chế độ mới không tạo khoảng tin cậy giả.
- Chưa tính số xe cần trực hay chi phí. Đây là đầu vào dự báo cho phần năng lực.
