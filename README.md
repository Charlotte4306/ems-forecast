# Dự báo nhu cầu xe cứu thương San Francisco → số xe cần trực

Dự báo số cuộc gọi EMS theo giờ bằng LSTM, Prophet và SARIMAX trên cùng dữ liệu train,
validation, test. Code được tổ chức theo từng mô hình và dùng chung đường dẫn,
đọc CSV và hàm tính metrics.

## Cấu trúc thư mục

```text
ems-forecast/
├── main.py                       # CLI chung
├── ems/
│   ├── paths.py                  # đường dẫn từ project root
│   ├── data.py                   # đọc CSV và kiểm tra dữ liệu
│   ├── evaluation.py             # MAE, RMSE, MAPE, R²
│   └── models/
│       ├── lstm/                 # config, preprocess, model, train, evaluate, experiment
│       ├── prophet/              # model, train, evaluate
│       └── sarimax/              # model, run_sarimax, capacity_planning
├── data/                         # sáu CSV chung và notebook EDA gốc
├── notebooks/
│   ├── lstm_experiment.ipynb
│   └── prophet_experiment.ipynb
├── checkpoints/
│   ├── lstm/                     # weights và scalers của LSTM
│   ├── prophet/                  # model JSON và metadata
│   └── sarimax/                  # model pickle và metadata sau huấn luyện
├── outputs/
│   ├── lstm/
│   ├── prophet/
│   └── sarimax/                  # dự báo, khoảng 80%, năng lực và chi phí giả định
├── reports/
│   ├── lstm_seq24.md
│   ├── prophet.md
│   ├── integration.md
│   └── sarimax.md
├── scripts/
│   └── create_lstm_notebook.py
├── tests/
└── requirements.txt
```

## Cài đặt

Chạy PowerShell tại project root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Chạy Prophet

```powershell
.\.venv\Scripts\python.exe main.py prophet
```

Fit bốn cấu hình trên train, chọn theo MAE validation, đánh giá test và xuất
artifact trong `checkpoints/prophet/`, `outputs/prophet/`.
Xem [báo cáo Prophet](reports/prophet.md).

## Chạy SARIMAX

Đánh giá CSV đã có và tạo lại bảng chi phí, lịch nhân sự, bốn biểu đồ; không huấn luyện:

```powershell
.\.venv\Scripts\python.exe main.py sarimax --evaluate-only
```

Huấn luyện năm cấu hình, chọn theo MAE validation, fit lại cửa sổ 8.760 giờ
gần nhất của train + validation rồi dự báo test từng đợt 24 giờ:

```powershell
.\.venv\Scripts\python.exe main.py sarimax
```

Kết quả nằm trong `outputs/sarimax/`, checkpoint và metadata trong
`checkpoints/sarimax/`. Lệnh huấn luyện ghi đè artifact cùng tên.
Có thể đổi vị trí bằng `--output-dir` và `--checkpoint-dir`.

Điều chỉnh kịch bản điều phối viên tổng đài (đơn vị USD và năng suất là giả định):

```powershell
.\.venv\Scripts\python.exe -m ems.models.sarimax.capacity_planning --mu 3 --cost-over 30 --cost-under 75
```

Đây là mô phỏng nhân sự điều phối theo giờ; không phải tối ưu số xe cứu thương.
SARIMAX dùng chân trời và dữ liệu fit cuối khác Prophet/LSTM; xem
[quy trình và giới hạn so sánh](reports/sarimax.md).

## Chạy LSTM

Dùng checkpoint Vanilla seq24 đã tích hợp để đánh giá, không train lại:

```powershell
.\.venv\Scripts\python.exe main.py lstm --evaluate-only
```

Huấn luyện lại (ghi đè weights/scalers và kết quả của run tương ứng):

```powershell
.\.venv\Scripts\python.exe main.py lstm --seq-len 24 --epochs 30
```

Các lựa chọn khác: `--seq-len 168`, `--batch-size 32`,
`--architecture stacked_bi` hoặc `--architecture attention`.
`--evaluate-only` yêu cầu checkpoint tương ứng đã tồn tại;
repo hiện có sẵn checkpoint `vanilla_seq24`.
Xem [báo cáo LSTM](reports/lstm_seq24.md).

Có thể gọi trực tiếp module:

```powershell
.\.venv\Scripts\python.exe -m ems.models.prophet.train
.\.venv\Scripts\python.exe -m ems.models.lstm.experiment --evaluate-only
```

## Notebook và kiểm tra

Mở notebook trong `notebooks/`, chọn kernel `.venv` và chạy từ đầu.
Notebook LSTM giữ output của thí nghiệm gốc; các đường dẫn cũ trong output
là lịch sử, còn code cell đã được cập nhật theo package mới.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

