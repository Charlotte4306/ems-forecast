# Thí nghiệm Prophet cho dự báo cuộc gọi EMS

## Dữ liệu và mục tiêu

Dùng nguyên sáu CSV của `main`, giống nguồn dữ liệu của thí nghiệm LSTM:

| Tập | Số giờ | Thời gian |
| --- | ---: | --- |
| Train | 52.440 | 2019–2024, sau khi loại các giờ thiếu lag |
| Validation | 8.760 | 2025 |
| Test | 6.796 | 2026, theo dữ liệu hiện có |

Khôi phục timestamp `ds` từ `year`, `month`, `day_of_month`, `hour`.
Target `y` lấy từ `call_count` cùng dòng. Loader kiểm tra số dòng, timestamp
liên tục theo giờ, ranh giới tập và lag khớp target. Không đổi timezone của
timestamp: giữ nguyên quy ước giờ trong CSV nguồn.

## Mô hình

Prophet mô hình hóa trend và mùa vụ ngày, tuần, năm. Có bốn ứng viên:

- Seasonal Prophet với changepoint prior scale 0.01 hoặc 0.05.
- Prophet có 14 regressors lag/rolling/EWM với prior scale 0.01 hoặc 0.05.

Danh sách regressors nằm trong `ems/data.py`. Không thêm toàn bộ
calendar/sin/cos vì Prophet đã biểu diễn mùa vụ từ timestamp. Không chuẩn hóa
target bên ngoài; Prophet tự xử lý scaling nội bộ và chuẩn hóa regressors khi fit.
Không dùng holiday trong thí nghiệm đầu tiên. Không tạo sequence 24/168 giờ vì
Prophet nhận bảng `ds`, `y` thay vì tensor cửa sổ như LSTM.

Tham khảo API: [Prophet Quick Start](https://facebook.github.io/prophet/docs/quick_start.html)
và [Additional regressors](https://facebook.github.io/prophet/docs/seasonality,_holiday_effects,_and_regressors.html#additional-regressors).

## Quy trình đánh giá

1. Fit từng ứng viên chỉ trên train, dùng seed 42.
2. Chọn cấu hình có MAE validation nhỏ nhất.
3. Giữ nguyên cutoff huấn luyện, không refit thêm validation, để tương ứng với LSTM.
4. Đánh giá mô hình được chọn trên test; lưu MAE, RMSE, MAPE và R².
5. So sánh naive lag-1, lag-24, lag-168 trên chính các timestamp đó.

Xuất ba khoảng đánh giá: toàn bộ test; test bỏ 24 giờ đầu để khớp LSTM seq24;
test bỏ 168 giờ đầu cho thí nghiệm seq168. Không cần bỏ các giờ này khi Prophet
chạy thực tế; đây chỉ là căn chỉnh khi so sánh các mô hình.

**Phạm vi dự báo:** biến thể dùng regressors đánh giá từng giờ với các giá trị
lịch sử thực tế đã biết trước giờ đó, cùng cách sử dụng features trong thí nghiệm
LSTM. Nó không phải dự báo toàn bộ năm từ một thời điểm duy nhất. Muốn dự báo
nhiều giờ từ một thời điểm phải dùng bản seasonal hoặc tự tạo regressors đệ quy;
không được đưa lag/rolling chứa các quan sát sau thời điểm dự báo vào inference.
Weights của mô hình không được cập nhật trong validation/test.

Dự báo âm được clip về 0. MAPE loại target bằng 0; nếu toàn bộ target bằng 0,
MAPE lưu `null`. R² lưu `null` khi target không có phương sai. Không tạo confidence
intervals trong lần chạy này (`uncertainty_samples=0`).

## Thực thi

Từ thư mục gốc dự án, khuyến nghị Python 3.11 trở lên:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m ems.models.prophet.train
```

Notebook `notebooks/prophet_experiment.ipynb` gọi cùng pipeline, tránh hai bản
logic khác nhau. Chọn kernel của `.venv`. Có thể đăng ký kernel bằng:

```powershell
.\.venv\Scripts\python.exe -m ipykernel install --user --name ems-prophet --display-name "EMS Prophet"
```

## Kết quả xuất ra

- `outputs/prophet/validation_results.csv`: kết quả bốn cấu hình trên validation.
- `outputs/prophet/metrics.json`: cấu hình được chọn, phiên bản thư viện, cutoff và metrics.
- `outputs/prophet/test_predictions.csv`: timestamp, actual, prediction trên test.
- `outputs/prophet/predictions.png`: 14 ngày đầu và phân bố residual toàn test.
- `outputs/prophet/components.png`: các thành phần Prophet.
- `checkpoints/prophet/best_model.json`: mô hình serialize theo API Prophet.
- `checkpoints/prophet/metadata.json`: cấu hình và protocol đi kèm mô hình.

Load lại bằng `ems.models.prophet.model.load_model(Path(...))`; gọi `predict(model, frame)`
với `ds` và đúng regressors nếu mô hình sử dụng chúng. Không cần target để inference.
Các artifact sinh ra được lưu trong Git theo mô hình; `.venv` và bytecode được gitignore. Báo cáo metrics thực tế được tạo
sau khi chạy; không dùng lại kết quả LSTM làm kết quả Prophet.

## Kết quả chạy kiểm chứng

Lần chạy kiểm chứng chọn `prophet_lags_cp0.05`, MAE validation **3.0869**.
Các kết quả dưới đây được tính từ lần chạy thực tế, không lấy từ notebook LSTM.

| Mô hình | Khoảng test | MAE | RMSE | MAPE (%) | R² |
| --- | --- | ---: | ---: | ---: | ---: |
| Prophet được chọn | 6.796 giờ | 3.0339 | 3.9212 | 32.9251 | 0.3784 |
| Naive lag-1 | 6.796 giờ | 4.2048 | 5.3427 | 45.1770 | -0.1539 |
| Naive lag-24 | 6.796 giờ | 4.2091 | 5.4018 | 44.6562 | -0.1796 |
| Naive lag-168 | 6.796 giờ | 4.1136 | 5.3085 | 43.9462 | -0.1392 |
| Prophet được chọn | 6.772 giờ, khớp seq24 | 3.0306 | 3.9137 | 32.9492 | 0.3806 |

Toàn test: `2026-01-01 00:00:00` đến `2026-10-11 03:00:00`.
Khoảng khớp seq24 bắt đầu `2026-01-02 00:00:00`. Prophet giảm MAE khoảng 27.8%
so với naive lag-1 trên toàn test. Mô hình bắt được nhịp ngày nhưng vẫn khó dự báo
các đỉnh bất thường; kiểm tra thêm residual và sai số ở giờ có nhu cầu cao trước
khi dùng cho quyết định điều phối.

Đã kiểm chứng bốn unit tests và nạp lại checkpoint: dự báo 48 giờ đầu khớp CSV
đã lưu với tolerance `1e-10`. Metadata lưu phiên bản thư viện và SHA-256 của sáu
CSV để đối chiếu dữ liệu giữa các lần chạy. Notebook được kiểm tra cú pháp;
pipeline đã chạy bằng CLI, chưa thực thi toàn bộ notebook trong Jupyter.

Đầu ra hiện là cuộc gọi/giờ. Quy đổi sang số xe cần trực là bước nghiệp vụ tiếp theo.
