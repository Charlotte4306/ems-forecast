# EMSForecast

## Cấu trúc thư mục

```text
ems-forecast/
├── main.py                     # CLI chung cho ba mô hình dự báo
├── run_queuing.py              # Chạy quy trình lập kế hoạch xe
├── requirements.txt            # Thư viện cho môi trường nghiên cứu
├── ems/
│   ├── data.py                 # Đọc và kiểm tra dữ liệu dùng chung
│   ├── evaluation.py           # Các chỉ số đánh giá dự báo
│   ├── paths.py                # Đường dẫn từ thư mục gốc
│   ├── models/
│   │   ├── prophet/            # Huấn luyện, lựa chọn và dự báo Prophet
│   │   ├── lstm/               # Tiền xử lý, huấn luyện và dự báo LSTM
│   │   └── sarimax/            # Huấn luyện và đánh giá SARIMAX
│   ├── capacity/               # Kiểm tra dữ liệu thời gian xe bận
│   ├── capacity_inputs.py      # Kiểm tra đầu vào dự báo cho kế hoạch xe
│   ├── capacity_notebook.py    # Chạy notebook kế hoạch xe qua CLI
│   ├── queuing.py              # Workload, số xe và kế hoạch ca
│   ├── live/                   # Tải dữ liệu và dự báo tự động bảy ngày
│   └── web/                    # Chuẩn bị snapshot và HTTP server
├── data/                       # CSV train, validation, test và notebook EDA
├── checkpoints/                # Weights và scalers dùng để tái lập
├── notebooks/                  # Thí nghiệm mô hình và kế hoạch xe
├── outputs/
│   ├── prophet/                # Dự báo và đánh giá Prophet
│   ├── lstm/                   # Dự báo và đánh giá LSTM
│   ├── sarimax/                # Kết quả 1h và 24h không refit
│   ├── capacity/               # Kết quả kiểm tra thời gian xe bận
│   ├── queuing/                # Kế hoạch xe và chi phí kịch bản
│   ├── web/                    # Snapshot dữ liệu cho giao diện
│   └── live/                   # Dữ liệu worker tạo khi chạy, không theo dõi bằng Git
├── web/                        # HTML, CSS, JavaScript và font giao diện
├── scripts/                    # Tạo notebook và kiểm tra DOM
├── tests/                      # Kiểm thử Python và JavaScript
├── reports/                    # Báo cáo mô hình và phương pháp
└── deploy/                     # Đóng gói release, service và timer
```

## Giới thiệu

EMSForecast dự báo số lượt điều động xe cấp cứu theo giờ tại San Francisco bằng Prophet, LSTM và SARIMAX; dùng dự báo làm đầu vào cho các kịch bản bố trí xe và chi phí. Giao diện có phần đánh giá lịch sử và phần dự báo tự động bảy ngày riêng biệt.

## Chạy giao diện

Tại thư mục gốc, chỉ cần Python 3.11 trở lên để phục vụ snapshot đã có trong repo:

```powershell
python -m ems.web
```

Mở http://127.0.0.1:8501. Các trang chính: Tổng quan → Dự báo → Kế hoạch xe → Chi phí → Đánh giá mô hình → Dự báo 7 ngày. Lịch sử và Cài đặt nằm trong menu Thêm. URL dùng tiếng Anh, chữ thường và dấu gạch ngang.

Server cung cấp `/api/dataset`, `/api/live-forecast` và `/health`. Trang lịch sử đọc `outputs/web/dataset.json`. Trang bảy ngày đọc `outputs/live/forecast.json`, hoặc thư mục được cấu hình bằng `EMS_LIVE_DIR`; nếu chưa chạy worker, phần này báo chưa có dữ liệu.

## Dữ liệu và ý nghĩa mục tiêu

`call_count` trong `data/y_*.csv` là tên cột cũ: giá trị biểu thị **số lượt điều động xe cấp cứu, gom theo giờ nhận cuộc gọi (`received_dttm`)**. Một cuộc gọi điều hai xe được tính hai lượt. Phạm vi dữ liệu là nhóm xe cấp cứu được chọn trong nguồn, không bao gồm mọi loại đơn vị ứng cứu. Đây không phải số cuộc gọi duy nhất hoặc số xe trong đội xe.

| Tập | Khoảng thời gian | Số giờ |
| --- | --- | ---: |
| Train | 08/01/2019–31/12/2024 | 52.440 |
| Validation | Năm 2025 | 8.760 |
| Test | 01/01/2026 00:00–11/10/2026 03:00 | 6.796 |

Validation có 100.320 lượt; test cố định có 79.348 lượt. Nguồn DataSF có thể cập nhật bản ghi quá khứ. Đối chiếu ngày 12/11/2026 cho thấy giờ cuối test hiện có 7 lượt thay vì 4; giữ nguyên snapshot nghiên cứu để kết quả còn tái lập được. Notebook EDA gốc được lưu để truy nguyên; nếu mô tả cũ nói “distinct calls”, dùng định nghĩa đã đối chiếu ở đây và trong [hồ sơ dữ liệu](deploy/LIVE-FORECAST.md).

Timestamp nghiên cứu giữ dạng giờ địa phương không timezone của CSV. Chưa chuẩn hóa lại DST. So sánh mô hình phải cùng horizon, cutoff huấn luyện, timestamp và actual; tách thí nghiệm 1h khỏi 24h. MAE tính mọi giờ; MAPE bỏ giờ actual bằng 0.

## Môi trường nghiên cứu

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Môi trường này dùng cho huấn luyện, inference offline và tests Python. Lệnh huấn luyện có thể ghi đè kết quả cùng tên; dùng thư mục đầu ra riêng khi thử nghiệm. Không cần cài Torch để chỉ xem web.

## Các mô hình

Các thí nghiệm chuẩn fit tham số trên train, chọn cấu hình theo validation 2025 và đánh giá test 2026. Không chọn tham số bằng điểm test hoặc refit tham số bằng validation trước khi so sánh chính thức.

| Mô hình | Giao thức | Artifact chính | MAE test |
| --- | --- | --- | ---: |
| Prophet | Rolling 1h, quan sát tới giờ trước | `outputs/prophet/test_predictions.csv` | 3,033880 |
| SARIMAX | Rolling 1h, không refit | `outputs/sarimax/h1/` | 3,016164 |
| Prophet | Phát hành cả ngày lúc 00:00, đệ quy 24h | `outputs/prophet/day_ahead_24h/test_selected/` | 3,050050 |
| SARIMAX | Khối 24h, không refit | `outputs/sarimax/norefit/` | 3,012486 |
| LSTM | Đầu ra trực tiếp 24h | `outputs/lstm/test_predictions_vanilla_24h_block.csv` | 3,008991 |

Đơn vị MAE: lượt điều động/giờ, trên cùng 6.796 giờ. Checkpoint LSTM rolling 1h vẫn được giữ; snapshot web hiện chỉ có Prophet 1h và ba mô hình 24h. Không dùng checkpoint `vanilla_seq24` cũ thay cho `vanilla_1h_rolling`.

```powershell
# Prophet: huấn luyện/chọn 1h; chọn riêng 24h; đánh giá checkpoint 24h đã chọn
.\.venv\Scripts\python.exe main.py prophet
.\.venv\Scripts\python.exe main.py prophet --select-24h
.\.venv\Scripts\python.exe main.py prophet --forecast-24h --checkpoint-dir checkpoints/prophet/day_ahead_24h --output-dir outputs/prophet/day_ahead_24h/test_selected

# LSTM: đánh giá weights/scalers đã lưu, không train hoặc fit lại scaler
.\.venv\Scripts\python.exe main.py lstm --evaluate-only
.\.venv\Scripts\python.exe main.py lstm --forecast-horizon 24 --evaluate-only

# SARIMAX: đánh giá CSV có sẵn; huấn luyện chuẩn 24h; huấn luyện chuẩn 1h
.\.venv\Scripts\python.exe main.py sarimax --evaluate-only
.\.venv\Scripts\python.exe main.py sarimax
.\.venv\Scripts\python.exe -m ems.models.sarimax.run_sarimax_h1
```

SARIMAX mặc định dùng toàn bộ 52.440 giờ train, không refit; đầu ra `outputs/sarimax/norefit`. `--refit` dành cho thí nghiệm khác và phải dùng `--output-dir` riêng. Checkpoint được tạo khi huấn luyện; repo giữ dự báo và metadata của hai thí nghiệm chuẩn, không giữ pickle refit cũ.

Xem chi tiết [Prophet](reports/prophet.md), [Prophet 24h](reports/prophet_24h.md), [LSTM](reports/lstm.md) và [SARIMAX](reports/sarimax.md).

## Kế hoạch xe và chi phí

```powershell
.\.venv\Scripts\python.exe run_queuing.py
```

CLI chạy cùng code với `notebooks/queueing_theory.ipynb`, dùng dự báo 24h đã lưu và inference LSTM; không huấn luyện. Kết quả ở `outputs/queuing/`. Dùng `--output-dir` để thử trong thư mục khác.

Luồng tính: lượt điều động → khối lượng xe bận có carryover → `ceil(workload / rho)` → mức cao nhất trong từng ca. `rho=80%`, chính sách Trung bình/P90 và tỉ lệ chi phí là giả định kịch bản. Ca 00–08/08–16/16–24 hoặc 00–12/12–24; chỉ chấm 6.792 giờ đủ ca, loại bốn giờ cuối. Chi phí là điểm tương đối theo xe-giờ thiếu/thừa, không phải USD. “Nhu cầu xe đối chiếu” cũng được tính từ actual bằng mô hình, không phải roster thực tế hay bảo đảm thời gian đáp ứng.

Thời gian bận vật lý là `available_dttm - dispatch_dttm`; khác với đồng hồ `received_dttm` dùng gom target. Thống kê raw 2025 và giới hạn của kernel được giải thích trong [báo cáo thời gian bận](reports/medic_busy_time.md).

## Dự báo tự động bảy ngày

Worker tải **tổng hợp theo giờ** từ DataSF bằng `count(distinct rowid)`, lọc cùng nhóm xe cấp cứu với dữ liệu nghiên cứu và gom theo `received_dttm`; không tải toàn bộ raw trong mỗi lần cập nhật. Nó fit một Prophet mùa vụ riêng trên 180 ngày hoàn chỉnh, báo MAE holdout 14 ngày và dự báo 168 khung giờ cho bảy ngày. Kết quả này không dùng để thay bảng so sánh ba mô hình lịch sử.

```powershell
.\.venv\Scripts\python.exe -m ems.live.update --output-dir outputs/live
```

Timer trên VPS chạy 07:00 giờ San Francisco, có độ trễ ngẫu nhiên tối đa năm phút. Refresh lỗi giữ snapshot tương thích gần nhất. Xem [vận hành worker và định nghĩa nguồn](deploy/LIVE-FORECAST.md).

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
node --test tests/*.test.mjs
node tests/test_web_operations.mjs
```

Không có npm build hoặc framework frontend. [Vận hành giao diện](web/OPERATIONS.md) hướng dẫn tạo lại snapshot; [thiết kế](web/DESIGN.md) mô tả các lớp UI; [triển khai](deploy/README.md) hướng dẫn đóng gói release. [Ghi chú dọn main](reports/main_cleanup.md) nêu các phần đã bỏ và phần còn hạn chế.
