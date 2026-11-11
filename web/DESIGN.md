# Thiết kế giao diện EMSForecast

Giao diện HTML/CSS/ES modules, lấy cảm hứng từ website Zenless: nền đen/xám, điểm nhấn vàng chanh, họa tiết sọc chéo, viền đen dày dạng capsule, chuyển động hover/focus và thanh điều hướng số bên phải. Không dùng hình nhân vật hoặc logo trò chơi làm thương hiệu EMSForecast.

## Màn hình và điều hướng

| Số | Màn hình | URL |
| --- | --- | --- |
| 01 | Tổng quan | `/overview` |
| 02 | Dự báo | `/forecast` |
| 03 | Kế hoạch xe | `/fleet-plan` |
| 04 | Chi phí | `/scenario-costs` |
| 05 | Đánh giá mô hình | `/model-evaluation` |
| 06 | Dự báo 7 ngày | `/daily-forecast` |

Menu Thêm chứa `/history` và `/settings`. Số bên phải theo đúng thứ tự sáu tab chính. `routes.mjs` quản lý URL và chuyển link hash/query cũ sang đường dẫn mới. Ngày, profile và kịch bản được giữ khi chuyển màn.

## Font và các lớp mã

Tiêu đề dùng TT Hoves Pro Compact Bold; navbar/nội dung dùng Tahoma với fallback hệ thống; một số chữ trang trí Latin dùng Impact. Nguồn font và quyền gốc xem [ZENLESS-FONTS.md](assets/ZENLESS-FONTS.md). IBM Plex TTF vẫn còn được CSS nền tham chiếu; không áp giấy phép IBM cho font Zenless.

`index.html` giữ DOM và selectors dùng chung. `styles.css`, `template-bindings.css`, `operations.css`, `reference-polish.css`, `zenless.css` được nạp theo thứ tự này. CSS nền vẫn có các quy tắc bị override; không xóa cả file chỉ vì một phần không hiện ở theme hiện tại. `template-runtime.mjs` giữ hành vi nền; `reference-motion.mjs`, `zenless.mjs` bổ sung motion. Các node nền được ẩn bằng theme vẫn thuộc cấu trúc DOM hiện tại.

`app.mjs` kết nối dữ liệu và bộ lọc; `dashboard.mjs` kiểm tra profile và tính MAE/MAPE; `operations.mjs` tính kịch bản xe/chi phí; `live.mjs` kiểm tra và hiển thị forecast tự động. `analysis.mjs` chỉ còn hàm xuất CSV. Motion tôn trọng `prefers-reduced-motion` theo các handler/CSS hiện có.

## Ranh giới dữ liệu

Thí nghiệm lịch sử dùng snapshot tĩnh đã đối chiếu. Dự báo bảy ngày dùng API riêng, hiện trạng thái dữ liệu trễ hoặc refresh lỗi. Đơn vị UI là lượt điều động xe; MEDIC được ghi trong phạm vi dữ liệu. Giá trị fleet/chi phí là kịch bản mô hình, không phải lệnh điều xe hoặc roster thực tế.

Kiểm tra DOM: `node scripts/check_web_reference.mjs <path-to-jsdom/lib/api.js>`. Đây là QA tùy chọn, jsdom cài ngoài repo; ứng dụng không có dependency npm ở runtime.
