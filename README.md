# Dự báo nhu cầu xe cứu thương San Francisco → số xe cần trực

## Thí nghiệm Prophet

Nhánh `feat/prophet` xây dựng Prophet từ dữ liệu chung trên `main`.
Xem [quy trình, cách chạy và protocol đánh giá](report_prophet.md).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.prophet_train
```

Notebook: `notebooks/prophet_experiment.ipynb`.

## Cấu trúc thư mục

```
ems-forecast/
├── data/                         # CSV train/val/test dùng chung
├── notebooks/
│   └── prophet_experiment.ipynb
├── src/
│   ├── prophet_data.py           # đọc dữ liệu và kiểm tra timestamp/lag
│   ├── prophet_model.py          # tạo, lưu, load và dự báo
│   ├── prophet_train.py          # chọn cấu hình bằng validation
│   └── prophet_evaluate.py       # metrics và biểu đồ
├── tests/
├── checkpoints/prophet/          # sinh ra khi chạy, được gitignore
├── outputs/prophet/              # sinh ra khi chạy, được gitignore
├── requirements.txt
└── report_prophet.md
```
