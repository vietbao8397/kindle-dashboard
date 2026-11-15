# Thiết kế Cải tiến Giao diện Ngân sách Ngày Antigravity & Chạy Ngầm Tuyệt Đối (Kindle Dashboard)

**Ngày:** 2026-11-15  
**Quy mô:** Thay đổi gọn (Small Change — tập trung tại `render.py`, `windows/antigravity_sync.py`, `windows/install_task.ps1`)

---

## 1. Mục đích & Lý do (Intent & Why)
Giúp người dùng (quản lý công việc trên màn hình E-Ink 6-inch của Kindle Paperwhite 3 đặt trên bàn làm việc) nắm bắt ngay trong 1 giây **hạn mức Gemini còn được phép dùng trong ngày hôm nay** và **ngân sách dự kiến của ngày mai** để chủ động điều tiết chiến lược chọn model (nặng/nhẹ) dàn đều suốt 7 ngày, đồng thời loại bỏ hoàn toàn hiện tượng cửa sổ Terminal nhấp nháy mỗi 10 phút trên màn hình Windows khi đồng bộ ngầm.

## 2. Mục tiêu, Ngoài phạm vi & Điều cần tránh (Goals, Non-Goals, Anti-Goals)
- **Mục tiêu (Goals):**
  1. Gỡ bỏ hoàn toàn 2 thanh quota `Claude/GPT` trên khối `ANTIGRAVITY`.
  2. Thay bằng bố cục **`D1-Max`** tối ưu không gian 6-inch E-Ink:
     - Gộp nhãn trạng thái phiên (`ĐANG CHẠY` / `SẴN SÀNG` + tên phiên/số phiên) lên góc phải thanh tiêu đề `ANTIGRAVITY` (xoá giờ cập nhật bị trùng với chân trang).
     - **Bên trái:** Hai cung bán nguyệt tách rời hoàn toàn (không có gạch ngang giữa): vòm trên biểu diễn `% còn lại 5 GIỜ`, vòm dưới biểu diễn `% còn lại TUẦN` kèm thứ đặt lại (vd: `TUẦN · T7`).
     - **Bên phải:** Bộ điều phối Ngân sách Ngày theo quy tắc cuốn chiếu tuần, quy chuẩn **`1 ngày chuẩn (14,2857% tuần) = 100% quỹ ngày`**, gồm cặp số cỡ đại **`NAY` / `MAI`** (khi âm hiển thị khối nền đen chữ trắng nổi bật) và đồ hoạ **Người que + Lá cờ đích hôm nay** (còn dư đi bộ trước cờ, xài lố chạy vượt cờ sang vùng đất ngày mai).
  3. Triệt tiêu 100% cửa sổ console/terminal nhấp nháy mỗi 10 phút trên Windows 11 khi `KindleDashboard-AntigravitySync` gọi `agy.exe` và `gh.exe`.
- **Ngoài phạm vi (Non-Goals):**
  - Không thay đổi mã nguồn trên máy Kindle (`loop.sh`, `Dashboard.sh`, `config.sh`) — không cần cắm lại cáp USB.
  - Không thay đổi hay deploy lại Google Apps Script (`apps_script.gs`) hoặc GitHub Secrets.
- **Điều cấm kỵ (Anti-Goals):**
  - Không nhồi nhét chữ chú thích nhỏ li ti gây mỏi mắt trên màn 6-inch E-Ink hoặc lấn chiều cao của khu vực `VIỆC CẦN LÀM` & `LỊCH`.
  - Không dùng gradient mờ gây hiện tượng lưu ảnh (ghosting) hoặc tăng dung lượng file PNG.
  - Không để bất kỳ tiến trình con/cháu nào (`agy.exe`, MCP servers, `gh.exe`) hiện cửa sổ hay cướp tiêu điểm chuột/bàn phím trên màn hình làm việc.

## 3. Ràng buộc Kỹ thuật (Constraints)
- Độ phân giải gốc Kindle Paperwhite 3: `1072 × 1448` (`mode="L"` grayscale, `DASH_SCALE=1.12`, khung logic `957 × 1293`).
- Chiều cao khối `ANTIGRAVITY` giữ tương đương bản cũ (~`205–215px` logic) để bảo toàn trọn vẹn số dòng công việc và lịch hẹn bên dưới.
- Múi giờ tính ngày: `Asia/Ho_Chi_Minh` (`UTC+7`), bước chuyển ngày mới tính tại mốc `00:00`.

## 4. Các hướng tiếp cận đã cân nhắc (Approaches)
1. **Hướng 1 (Đã chọn) — Tính toán trực tiếp (Stateless) trong `render.py` từ `gemini.utilization` + `gemini.resets_at`:**
   - *Ưu điểm:* Không sinh file sổ cái cục bộ, không lệch số khi tắt PC qua đêm lúc `00:00`, không cần sửa/deploy lại `apps_script.gs`.
   - *Đánh đổi:* Cần `resets_at` hợp lệ từ `agy` (có fallback an toàn theo ngày trong tuần nếu thiếu).
2. **Hướng 2 (Loại bỏ) — Ghi sổ cái chốt mốc `00:00` dưới PC rồi gửi qua Apps Script:**
   - *Nhược điểm:* Bị trễ mốc đầu ngày nếu tắt máy tính ban đêm, phát sinh trạng thái thừa và phải biến tấu trường dữ liệu qua whitelist của `apps_script.gs` trong khi kết quả cuốn chiếu không đổi.

## 5. Chi tiết Thiết kế Đã Chốt (Approved Design Details)

### 5.1. Công thức Ngân sách Ngày Cuốn Chiếu (Thang `100% = 1 ngày chuẩn`)
Gọi `used` (`0..100`) là `gemini.utilization` (% tuần đã dùng), `rem_week = 100 - used`, và `reset_dt` là `gemini.resets_at` đổi sang `Asia/Ho_Chi_Minh`:
- **Xác định ngày thứ $k \in \{1..7\}$ của chu kỳ tuần (chuyển ngày lúc `00:00`):**
  - `days_diff = (reset_dt.date() - now.date()).days`
  - Nếu `reset_dt.hour < 12` (reset buổi sáng, vd `06:44 T7`): `k = min(7, max(1, 8 - days_diff))`
  - Nếu `reset_dt.hour >= 12` (reset chiều/tối): `k = min(7, max(1, 7 - days_diff))`
  - *(Fallback nếu thiếu `resets_at`: `k = now.weekday() + 1`)*
- **Quy đổi sang thang `100%` của 1 ngày chuẩn (`100/7 %` tuần):**
  - `today_pct = round(100 * k - 7 * used)`
    - `today_pct >= 0`: Hôm nay còn dư/đủ (vd: `k=2, used=26.0%` $\rightarrow$ `18%`).
    - `today_pct < 0`: Hôm nay xài lố hạn mức, hiển thị số âm trong hộp nền đen chữ trắng (vd: `k=2, used=32.3%` $\rightarrow$ `−26%`).
  - `tomorrow_pct`:
    - Nếu `k < 7`: `tomorrow_pct = round(min(100 * (k + 1) - 7 * used, 7 * rem_week))` (tương đương `100 + today_pct`, đồng thời chặn trần theo quỹ tuần thực tế còn lại).
    - Nếu `k == 7` (ngày cuối chu kỳ, hôm sau đặt lại tuần mới): `tomorrow_pct = 100` (bắt đầu chu kỳ mới).

### 5.2. Bố cục Đồ hoạ `D1-Max` trong `render.py`
- **Thanh tiêu đề `ANTIGRAVITY`:** Trái vẽ logo `[A] ANTIGRAVITY`; phải vẽ pill trạng thái (`ĐANG CHẠY` nền đen chữ trắng hoặc `SẴN SÀNG` viền đen) kèm nhãn phiên ngắn gọn / số phiên hôm nay.
- **Cột trái (~30% chiều ngang):** Hai cung tròn bán nguyệt tách rời trên–dưới (khe hở ~`24px`, không gạch ngang giữa), nét dày kết hợp cung nền xám nhạt; bên trong lòng vòm trên ghi `%` lớn + `5 GIỜ`, lòng vòm dưới ghi `%` lớn + `TUẦN · <Thứ>`.
- **Cột phải (~70% chiều ngang):**
  - Hàng trên: Hai cụm chữ lớn tương phản cao `NAY <today_pct>%` và `MAI <tomorrow_pct>%` (nếu `today_pct < 0`, vẽ khối chữ nhật bo góc nền đen chữ trắng `−X%`).
  - Hàng dưới: Đường hành trình gồm đoạn chính `0% → Cờ đích hôm nay (100%)` và đoạn đứt nét phía sau cờ (`vùng ứng trước ngày mai`), kèm ký hiệu `Nk/7` cạnh chân cờ:
    - Khi `today_pct >= 0`: vệt đen dừng tại `100 - min(100, today_pct)%`, người que dáng đi bộ thư thả đứng trước cờ.
    - Khi `today_pct < 0`: vệt đen phủ kín tới cờ kèm thanh cảnh báo dày vượt qua cờ theo tỷ lệ lố (tối đa hết vùng đệm), cờ chuyển sang nét rỗng đã vượt qua, người que dáng chạy lao về trước kèm vạch tốc độ.

### 5.3. Triệt tiêu Cửa sổ Terminal Nhấp Nháy trên Windows 11
Nguyên nhân gốc: (1) `agy.exe` khi khởi chạy tự gọi các tiến trình con (như MCP servers / git) mà không gắn cờ ẩn console, khiến Windows 11 bật cửa sổ `WindowsTerminal` / `OpenConsole` mới khi tiến trình cha `pythonw.exe` không có console; (2) hàm `trigger_github_workflow()` gọi `gh.exe` thiếu `STARTUPINFO(SW_HIDE)`; (3) script đang gọi `agy.exe` 2 lần liên tiếp (`/usage` và `/credits`) dù `credits = 0`.
- **Giải pháp đa tầng (Zero-Window Guarantee):**
  1. Bọc lệnh thực thi trong **Win32 Off-Screen Desktop (`CreateDesktopW("KindleDashHidden")` qua `ctypes`)** kết hợp `conhost.exe --headless` + `STARTUPINFO(STARTF_USESHOWWINDOW, SW_HIDE)` trong `antigravity_sync.py` và `install_task.ps1` (`Settings.Hidden = True`): mọi cửa sổ console của cả tiến trình con lẫn tiến trình cháu (`agy.exe`, MCP, `gh.exe`) đều bị cô lập ngoài màn hình hiển thị của người dùng, tuyệt đối không nháy cửa sổ hay xuất hiện dưới Taskbar.
  2. Thống nhất dùng hàm chạy ẩn cho cả `gh.exe` và chỉ lấy các bucket của Gemini (bỏ xử lý Claude không còn dùng; chỉ gọi `/credits` khi được bật qua biến môi trường `DASH_FETCH_CREDITS=1` để giảm một nửa thời gian & số lần gọi CLI mỗi 10 phút).
