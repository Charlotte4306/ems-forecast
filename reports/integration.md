# Tích hợp LSTM và Prophet

## Phạm vi

Nhánh `codex/integrate-models` được tạo từ `feat/prophet` và merge
`origin/huyenanh` bằng `--no-ff --no-commit`. Hai nhánh xuất phát từ cùng `main`.
Không tạo commit hoặc push trong quá trình tích hợp. Merge được để mở để chủ
repo kiểm tra và tự commit.

## Đổi đường dẫn

| Trước | Sau |
| --- | --- |
| `src/config.py`, `src/model.py`, `src/train.py`, `src/preprocess.py`, `src/evaluate.py` | `ems/models/lstm/` |
| `src/prophet_model.py`, `src/prophet_train.py`, `src/prophet_evaluate.py` | `ems/models/prophet/model.py`, `train.py`, `evaluate.py` |
| `src/prophet_data.py` | `ems/data.py` |
| Metrics trong từng mô hình | `ems/evaluation.py`, LSTM giữ tên khóa `R²` tương thích notebook |
| Checkpoint/scalers LSTM ở root `checkpoints/` | `checkpoints/lstm/` |
| Biểu đồ LSTM ở root `outputs/` | `outputs/lstm/` |
| `report_prophet.md`, `report_training_seq24.md` | `reports/prophet.md`, `reports/lstm_seq24.md` |
| `create_notebook.py` | `scripts/create_lstm_notebook.py` |

`data/`, `checkpoints/prophet/`, `outputs/prophet/` được giữ nguyên. Notebook được
cập nhật imports; output đã lưu của LSTM vẫn là lịch sử lần chạy gốc. Bỏ các
file `src/__pycache__/*.pyc` khỏi phần source được quản lý trong Git.

Hai conflict add/add ở `requirements.txt` và `src/__init__.py` được giải quyết
bằng cách gộp dependencies và chuyển sang các package initializer trong `ems/`.
`main.py` điều phối CLI bằng cách chỉ import mô hình được chọn.

`scikit-learn` được ghim ở `1.9.0` để khớp phiên bản đã tạo hai scaler LSTM.

## Tính tương thích và so sánh

Đợt refactor giữ kiến trúc, cách tạo sequence và target alignment LSTM như nhánh
Huyền Anh. Không sửa độ trễ thêm một giờ của features LSTM trong cùng đợt đổi
cấu trúc. Nếu sửa sau này phải huấn luyện và đánh giá lại để tạo thí nghiệm mới.
Prophet giữ nguyên cấu hình và protocol đã có.

Hàm metrics dùng chung loại target bằng 0 khỏi MAPE; trả `None` cho MAPE khi
không có target khác 0 và cho R² khi target có phương sai bằng 0. Trên bộ test
hiện tại, công thức tương đương hàm đánh giá LSTM gốc.

`python main.py lstm --evaluate-only` nạp scalers đã lưu, không fit lại và không
ghi đè checkpoint. Nó tạo CSV prediction có timestamp và JSON metrics để có thể
so sánh với Prophet trên cùng các giờ. Biểu đồ của run được cập nhật khi đánh giá.
Train lại sẽ ghi đè artifact tương ứng. Khi muốn giữ nhiều lần chạy, hãy sao lưu
artifact hoặc dùng nhánh thí nghiệm riêng.

## Sau khi kiểm tra

Đã kiểm chứng:

- Bảy tests pass, gồm nạp checkpoint hai mô hình và train/lưu/load một LSTM nhỏ.
- CLI LSTM đánh giá đủ 6.772 giờ test: MAE `2.98198158`, RMSE `3.83873154`,
  MAPE `33.29540064%`, R² `0.40405377`, khớp kết quả notebook gốc.
- Checkpoint Prophet sau refactor dự báo 48 giờ đầu khớp CSV trước refactor,
  tolerance `1e-10`. Không train lại Prophet trong lần refactor này.
- Cả năm artifact LSTM di chuyển được đối chiếu SHA-256 với nhánh gốc và không đổi.
- Hai notebook pass kiểm tra schema và cú pháp; chưa chạy toàn bộ trong Jupyter.
- CLI help của hai mô hình hoạt động. Bộ CSV và artifact Prophet không bị sửa.

Chủ repo tự thực hiện commit và push. Commit trên nhánh tích hợp sẽ hoàn tất
merge đang mở và chứa cả phần refactor. Sau đó có thể mở PR từ nhánh tích hợp
vào `main`; không cần merge lại hai nhánh mô hình lần nữa.
