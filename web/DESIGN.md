# EMSForecast: giữ nguyên giao diện HTML tham chiếu

Yêu cầu hiện tại của Charlotte: giữ y hệt hình thức và hiệu ứng của file
“Bản HTML mẫu màn Tổng quan.html”, chỉ thay dữ liệu minh họa bằng dữ liệu thật.

## Giữ nguyên hình thức

- Toàn bộ cấu trúc 7 màn hình, sidebar 224px, topbar, KPI, bảng và thứ tự các khối.
- CSS gốc: màu pastel, gradient, lớp kính mờ, kiểu chữ, khoảng cách, responsive.
- Nền loang, trái tim, mây, chấm sáng, sóng, parallax theo chuột, hiệu ứng chuyển
  cảnh, hover, vẽ đường biểu đồ, vòng sáng ở đỉnh dự báo và số đếm tăng dần.
- Font IBM Plex Sans đúng 400/500/600 từ Google Fonts như file tham chiếu;
  ba TTF cục bộ có glyph tiếng Việt và OS/2 weight tương ứng, không giả lập độ đậm.
- Giảm chuyển động theo thiết bị hoặc công tắc gốc trong Cài đặt; mặc định không
  tự tắt hiệu ứng. Mật độ bảng và tùy chọn chuyển động lưu cục bộ.

scripts/import_web_reference.py nhập nguyên DOM/CSS và hiệu ứng từ HTML nguồn.
Style inline được chuyển sang lớp CSS tương đương để giữ CSP cùng nguồn.
styles.css bắt đầu bằng CSS nguồn nguyên văn; không tải dashboard.css cũ.
template-bindings.css chỉ hỗ trợ bộ lọc dữ liệu, trạng thái tải và mật độ bảng.
template-runtime.mjs giữ thuật toán hiệu ứng/renderer gốc và đọc mảng dữ liệu thật.
app.mjs nối dữ liệu vào các phần tử gốc, không dựng lại bố cục dashboard khác.

## Phần thay đổi theo dữ liệu

Mặc định giữ ngày mẫu 29/09/2026, quan sát 28/09 và dự báo 29/09 bằng Prophet.
Các tổng, trung bình, giờ cao điểm, heatmap, MAE/MAPE và sai lệch tính lại từ
snapshot thật. Có thể đổi ngày và chế độ 1 giờ/24 giờ bằng điều khiển hiện có.
H1 cập nhật từng giờ; H24 phát hành từ 00:00, không cập nhật actual trong ngày.
Hai chế độ có 6.796 giờ; sáu giờ actual=0 vẫn tính MAE, không tính MAPE.
Ngày cuối có 4 giờ đối chiếu, không bịa thêm 20 giờ actual.

Bản ghi raw, số cuộc gọi duy nhất, thời gian xe bận, lịch xe và đơn giá chưa có
trong snapshot web: giữ nguyên các vị trí nhưng để “—” và ghi rõ trạng thái.
Không vẽ đường số xe minh họa như kết quả thật. Bảng so sánh giữ nguyên hình thức,
LSTM/SARIMAX chờ kết quả chung. CSV lịch sử xuất nhu cầu thực tế theo giờ;
không dựng mã cuộc gọi hoặc mã xe.

## Kiểm tra

Kiểm tra dữ liệu JS/Python và DOM bằng jsdom tạm, không thêm dependency frontend.
DOM kiểm tra 7 màn hình, nền, 168 ô heatmap, chart paths, điều hướng và cài đặt,
bao gồm H1, H24 và ngày cuối chưa đủ giờ. Đây không phải kiểm tra ảnh render.
CSS được đối chiếu trực tiếp với bản HTML nguồn. Font được kiểm tra đủ ba độ đậm
và glyph tiếng Việt. Máy chủ phục vụ TTF với Content-Type font/ttf.
Chưa xác minh trực quan trong trình duyệt vì Computer Use đã gặp giới hạn URL
trên Windows. Không coi kiểm tra DOM là kiểm tra trực quan.
