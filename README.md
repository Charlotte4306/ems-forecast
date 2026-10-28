# Dự báo nhu cầu xe cứu thương San Francisco → số xe cần trực

Dự báo số cuộc gọi EMS theo giờ bằng LSTM và Prophet trên cùng dữ liệu train,
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
│       └── prophet/              # model, train, evaluate
├── data/                         # sáu CSV chung và notebook EDA gốc
├── notebooks/
│   ├── lstm_experiment.ipynb
│   └── prophet_experiment.ipynb
├── checkpoints/
│   ├── lstm/                     # weights và scalers của LSTM
│   └── prophet/                  # model JSON và metadata
├── outputs/
│   ├── lstm/
│   └── prophet/
├── reports/
│   ├── lstm_seq24.md
│   ├── prophet.md
│   └── integration.md
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

