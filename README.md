# Dự báo nhu cầu xe cứu thương San Francisco → số xe cần trực

Dự báo lượt điều động xe theo giờ bằng LSTM và Prophet trên cùng dữ liệu train,
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

## Giao diện web

Frontend trên `feat/demo` giữ cấu trúc, CSS, font và hiệu ứng từ bản HTML mẫu:
Tổng quan, Dự báo nhu cầu, Kế hoạch xe, Chi phí kịch bản, Đánh giá mô hình,
Dữ liệu lịch sử và Cài đặt. Prophet có kết quả thật 1 giờ và 24 giờ, mỗi bộ
6.796 giờ; hiển thị MAE/MAPE, mốc lịch sử/dự báo, bảng dữ liệu và tải CSV.
LSTM/SARIMAX chờ kết quả theo cùng giao thức. Kế hoạch xe và chi phí ghi rõ
trạng thái chờ phương pháp chung, chưa công bố số xe hoặc chi phí giả định.

```powershell
.\.venv\Scripts\python.exe -m ems.web --host 127.0.0.1 --port 8501
```

Mở `http://127.0.0.1:8501`. Không cần cài thư viện mô hình để chạy web khi đã có
`outputs/web/dataset.json`. Giữ nguyên nền loang chuyển động, trái tim, mây,
sóng, parallax, chuyển cảnh, hover, số đếm tăng dần và hiệu ứng vẽ biểu đồ.
IBM Plex Sans dùng đúng ba file font chính thức 400/500/600 có tiếng Việt,
phục vụ cục bộ. Bật “Giảm chuyển động” trong Cài đặt nếu muốn tắt hiệu ứng.
Sau khi cập nhật giao diện, nhấn Ctrl+F5 để tải lại CSS/JS/font.
VPS chỉ cần Python tiêu chuẩn để phục vụ bản đã lưu,
không chạy mô hình nặng. Cài đặt giao diện được lưu trên trình duyệt.

Khi cập nhật kết quả Prophet, đóng gói lại từ CSV, không huấn luyện mô hình:

```powershell
python -m ems.web.prepare_dashboard --prophet24-ref feat/prophet-24h
```

Lệnh này yêu cầu bản `dataset.json` có sẵn và nhánh/commit nguồn tồn tại cục bộ.
Nó đọc artifact `test_selected/predictions_24h.csv` bằng Git, lưu commit nguồn
và SHA-256 để truy vết, không checkout hoặc sửa code mô hình. Có thể truyền
commit SHA thay tên nhánh. Bỏ `--prophet24-ref` sẽ chỉ đóng gói chế độ 1 giờ.
Nếu chạy exporter cũ `ems.web.export`, cần chạy lại lệnh đóng gói ở trên sau đó.
Snapshot vẫn giữ các trường cũ cho công cụ hiện hữu; giao diện mới đọc `profiles`.
Ngày cuối chỉ có 4 giờ đối chiếu; không tự thêm 20 giờ thực tế còn thiếu.
Các ô chưa có dữ liệu gốc (mã cuộc gọi, mã xe, thời gian bận) giữ nguyên hình thức
nhưng hiển thị “—”. CSV xuất chuỗi nhu cầu theo giờ đang xem, không dựng bản ghi gốc.

Kiểm tra phần web:

```powershell
node --test tests/web-analysis.test.mjs tests/web-dashboard.test.mjs
python -m unittest tests.test_web_server tests.test_web_dashboard_export
```

Xem [triển khai lên emsforecast.live](deploy/README.md) và
[quyết định thiết kế](web/DESIGN.md).

## Cài đặt môi trường mô hình

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

