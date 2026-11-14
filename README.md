# Kindle Dashboard: biến Kindle thành màn hình Lịch + Việc cần làm + Antigravity

Bộ này biến chiếc Kindle đang để không thành một màn hình để bàn (đã tinh chỉnh chuẩn **1072×1448** cho **Kindle Paperwhite 3 / 7th Gen**), hiện:
- **lịch Google** hôm nay và ngày mai,
- **việc cần làm** (Google Tasks),
- **thời tiết + chất lượng không khí**,
- **trạng thái phiên Agent & quota Antigravity** (đồng bộ từ Windows PC).

Màn hình tự làm mới khoảng 15 phút/lần. E-ink nên để cả ngày không chói mắt, pin dùng được nhiều ngày. **Chi phí: 0 đồng**, mọi thứ chạy trên dịch vụ miễn phí của Google và GitHub.

```
Google Calendar + Tasks ──► Apps Script (của bạn) ──► GitHub Actions vẽ ảnh ──► GitHub Pages ──► Kindle tải ảnh về hiển thị
                                 ▲
Windows PC (Antigravity) ────────┘
```

---

## Cần chuẩn bị

- **Kindle jailbreak được** (xem Phần 0).
- **Tài khoản Google** có lịch và việc cần làm muốn hiện lên.
- **Tài khoản GitHub** (miễn phí, đăng ký ở github.com).
- **Máy tính Windows + cáp USB** để chép file vào Kindle và chạy đồng bộ Antigravity.
- Khoảng **30–45 phút**, phần lâu nhất là jailbreak.

Trong bộ này có:

| File / thư mục | Dùng để |
|---|---|
| `apps_script.gs` | Code lấy lịch + việc cần làm + nhận số liệu Antigravity (Phần 1) |
| `setup_github.sh` | Script tự tạo repo GitHub và cài mọi thứ (Phần 2) |
| `render.py`, `lunar.py`, `.github/` | Code vẽ ảnh dashboard `1072×1448`, chạy trên GitHub |
| `kindle/` | File chép vào Kindle (Phần 3) |
| `windows/` | Bộ đồng bộ trạng thái & quota Antigravity trên Windows (Phần 5) |

---

## Phần 0: Jailbreak Kindle

Cách jailbreak phụ thuộc đời máy và phiên bản firmware, nên hãy làm theo hướng dẫn chính thức của cộng đồng tại **https://kindlemodding.org**:

1. Xem firmware: **Settings → Device Options → Device Info** (hoặc *Cài đặt → Tùy chọn thiết bị → Thông tin thiết bị*).
2. Với **Kindle Paperwhite 3 (7th Gen, firmware 5.16.2.1.1)** đã đăng nhập tài khoản Amazon: dùng **WinterBreak** (`WinterBreak v2.1.0` trở lên). Bản mới đã tích hợp sẵn chặn cập nhật OTA và mở khóa chạy file `.sh` Scriptlet ngay sau khi chạy, **không cần cài KUAL**.
3. Dashboard chạy bằng "scriptlet": file `Dashboard.sh` trong thư mục `documents`, hiện ra như một cuốn sách trong Thư viện.

> Jailbreak là tự chịu rủi ro. Đọc kỹ hướng dẫn và không rút cáp USB đột ngột trước khi Eject an toàn.

---

## Phần 1: Lấy dữ liệu Google bằng Apps Script (~10 phút)

1. Mở **https://script.google.com** (đúng tài khoản Google có lịch) → **New project**, đặt tên `Kindle Dashboard`.
2. Mở file **`apps_script.gs`** trong bộ này bằng Notepad/VS Code, copy toàn bộ. Xoá code mẫu trong Apps Script rồi dán vào.
3. Tìm dòng:
   ```js
   const TOKEN = 'DOI-THANH-CHUOI-BI-MAT';
   ```
   Đổi phần trong nháy thành **một chuỗi bí mật của bạn** (chữ và số, 10–20 ký tự). Bấm **Save**.
4. Cột trái, mục **Services** → **+** → chọn **Google Tasks API** → **Add**.
5. Trên thanh công cụ chọn hàm **`testCollect`** → **Run** → cho phép quyền.
   Google sẽ báo *"Google hasn't verified this app"*: bấm **Advanced → Go to Kindle Dashboard (unsafe) → Allow**. Đây là script của chính bạn nên không sao.
   Phần *Execution log* hiện danh sách lịch/việc là đúng.
6. **Deploy → New deployment** → bánh răng → **Web app**:
   - *Execute as*: **Me**
   - *Who has access*: **Anyone**
   → **Deploy** → copy **Web app URL** (dạng `https://script.google.com/macros/s/AKfy…/exec`).
7. Ghép thành **DATA_URL**:
   ```
   <Web app URL>?token=<chuỗi bí mật ở bước 3>
   ```
   Dán thử vào trình duyệt, thấy chữ dạng JSON có tên sự kiện/việc là đúng.
   **Không gửi link này cho ai**: ai có link là đọc được lịch của bạn.

> Sau này nếu sửa code Apps Script: **Deploy → Manage deployments → ✏️ → Version: New version → Deploy** (link giữ nguyên).

---

## Phần 2: Tạo repo GitHub và cài đặt (~5 phút)

### Cách A (khuyên dùng): chạy 1 lệnh

Script `setup_github.sh` tự làm hết: tạo repo, lưu `DATA_URL` vào mục bí mật, bật GitHub Pages, chạy lần đầu, và điền sẵn link ảnh vào file cấu hình của Kindle.

**Bước 1: cài công cụ** (chỉ làm 1 lần)
- **Windows**: cài **Git for Windows** (https://git-scm.com/download/win) và **GitHub CLI** (https://cli.github.com). Sau đó dùng chương trình **Git Bash** (có sẵn khi cài Git) để chạy lệnh bên dưới.

**Bước 2: chạy script**
```bash
cd đường-dẫn-tới/kindle-dashboard
bash setup_github.sh
```
Script sẽ lần lượt:
1. Mở trình duyệt cho bạn **đăng nhập GitHub** (copy mã 8 ký tự nó hiện ra, dán vào trang GitHub).
2. Hỏi **tên repo** (Enter để dùng `kindle-dashboard`).
3. Hỏi **toạ độ thành phố** cho thời tiết (mặc định Enter là TP.HCM `10.7769`, `106.7009`; Hà Nội: `21.0285`, `105.8542`).
4. Hỏi **DATA_URL** (ở Phần 1, bước 7). Khi dán, chữ sẽ không hiện ra, cứ dán rồi Enter.
5. Tự làm phần còn lại trong khoảng 1–2 phút, cuối cùng in ra **link repo** và **link ảnh**.

Mở link ảnh trên trình duyệt, thấy ảnh dashboard là thành công. Sang Phần 3.

### Cách B: làm tay trên web (nếu không chạy được script)

1. **Tạo repo**: vào https://github.com/new → tên `kindle-dashboard` → **Public** → **Create repository**.
2. **Upload code**: trong repo mới bấm **uploading an existing file** → kéo toàn bộ nội dung thư mục này vào (kể cả thư mục `.github`) → **Commit changes**.
   Nếu không kéo được thư mục `.github` (hay gặp trên Windows): bấm **Add file → Create new file**, gõ tên `.github/workflows/update.yml`, dán nội dung file đó → **Commit**.
3. **Đặt toạ độ thời tiết**: mở `.github/workflows/update.yml` → ✏️ → kiểm tra 2 dòng `DASH_LAT` và `DASH_LON` (mặc định đã đặt TP.HCM `10.7769`, `106.7009`) → **Commit**.
4. **Lưu thông tin bí mật**: **Settings → Secrets and variables → Actions → New repository secret**, tạo 2 cái:
   - `DATA_URL` = link ở Phần 1, bước 7
   - `SECRET_PATH` = một chuỗi ngẫu nhiên bất kỳ (chữ thường và số, khoảng 12 ký tự), dùng để giấu đường dẫn ảnh
5. **Bật Pages**: **Settings → Pages** → *Source*: **GitHub Actions**.
6. **Chạy lần đầu**: tab **Actions** → **Cập nhật dashboard Kindle** → **Run workflow** → nút xanh **Run workflow**. Chờ dấu ✅ (khoảng 1 phút).
7. Link ảnh của bạn là:
   ```
   https://<tên-github-của-bạn>.github.io/kindle-dashboard/<SECRET_PATH>/dashboard.png
   ```

Từ giờ GitHub tự vẽ lại ảnh khoảng 15 phút/lần từ 8h–24h, và 4 tiếng/lần ban đêm. GitHub đôi khi chạy trễ 10–30 phút, chuyện bình thường.

---

## Phần 3: Cài lên Kindle (~5 phút)

1. Mở file **`kindle/dashboard/config.sh`**:
   - Nếu dùng **Cách A**, dòng `IMAGE_URL=` đã được điền sẵn link ảnh của bạn.
   - Nếu dùng **Cách B**, sửa dòng `IMAGE_URL="..."` thành link ảnh ở Phần 2.

   Các tuỳ chọn khác trong file (có chú thích sẵn):
   - `INTERVAL_MIN=15`: ban ngày bao nhiêu phút làm mới 1 lần.
   - `NIGHT_START=0`, `NIGHT_END=8`, `NIGHT_INTERVAL_MIN=240`: từ 0h–8h làm mới 4 tiếng/lần cho đỡ tốn pin.
   - `LOW_BATTERY=15`: pin dưới 15% sẽ hiện chữ cảnh báo ở góc màn hình.
2. Cắm Kindle vào máy tính, chép:
   - cả thư mục **`kindle/dashboard/`** vào **gốc ổ Kindle**, để thành `Kindle/dashboard/`
   - file **`kindle/documents/Dashboard.sh`** vào thư mục **`documents`** của Kindle
   *(Lưu ý: giữ nguyên định dạng xuống dòng Unix LF cho mọi file `.sh`).*
3. Eject và rút cáp. Trong Thư viện sẽ có "cuốn sách" **Antigravity Dashboard**. Bấm vào để bật.
   Kindle tắt giao diện thường, hiện dashboard (cứ mỗi 4 chu kỳ làm mới toàn phần 1 lần để chống bóng mờ e-ink), rồi đến giờ lại tự bật Wi-Fi, tải ảnh mới, tắt Wi-Fi và ngủ sâu.

**Thoát về Kindle bình thường:** bấm nút nguồn **1 lần**. Nếu không được thì giữ nút nguồn khoảng 40 giây cho máy khởi động lại.
**Bật lại:** bấm "Antigravity Dashboard" trong Thư viện. Mỗi lần mở là tải ảnh mới ngay.

---

## Phần 4: Tuỳ chỉnh

Hầu hết tuỳ chỉnh nằm trong file `.github/workflows/update.yml` trên GitHub: mở file → ✏️ → sửa → **Commit changes**. Workflow sẽ tự chạy lại, không cần đụng vào Kindle.

| Muốn | Sửa gì |
|---|---|
| Cập nhật ngay, không chờ | Tab **Actions** → Cập nhật dashboard Kindle → **Run workflow**. Có ✅ thì thoát và mở lại Dashboard trên Kindle. |
| Đổi thành phố thời tiết | `DASH_LAT`, `DASH_LON` trong `update.yml` |
| Chữ to/nhỏ hơn | `DASH_SCALE` trong `update.yml`: mặc định `"1.12"` (chuẩn Paperwhite 3 `1072×1448`). Số nhỏ hơn (ví dụ `"1.0"`) thì chữ nhỏ hơn, hiện được nhiều việc hơn. |
| Chuyển bố cục Antigravity cỡ lớn | Tab **Variables** tạo `DASH_LAYOUT` = `antigravity` (quay lại mặc định thì đặt `lich`). |
| Ẩn bớt lịch | **Settings → Secrets and variables → Actions → tab Variables** → tạo `DASH_SKIP_CALENDARS` = tên các lịch muốn ẩn, cách nhau dấu phẩy |
| Đổi giờ ngủ đêm, tần suất làm mới | `config.sh` trên Kindle (cắm cáp, mở `dashboard/config.sh`) |
| Màn hình bị bóng mờ | Mặc định `loop.sh` làm mới toàn phần mỗi 4 chu kỳ (`eips -f -g`). Nếu muốn mỗi lần đều quét toàn phần, đổi nhánh `else` thành `eips -f -g "$IMG"`. |

---

## Phần 5 (tuỳ chọn): Đồng bộ Antigravity trên Windows

Bộ đồng bộ trong **`windows/`** giúp dashboard hiển thị cả **trạng thái phiên Agent gần nhất** (đọc tự động từ thư mục log chính thức `~/.gemini/antigravity/brain/`) lẫn **% Quota (Gemini / Claude / GPT) + AI Credits**.

1. **Lưu `DATA_URL` vào máy Windows** (mở PowerShell, thay link của bạn vào):
   ```powershell
   Set-Content "$HOME\.kindle-dashboard-url" "https://script.google.com/macros/s/YOUR_ID/exec?token=YOUR_TOKEN" -NoNewline
   ```
2. **Kiểm tra thử trước khi chạy nền**:
   ```powershell
   python windows\antigravity_sync.py --dry-run
   ```
   *(Nếu muốn ẩn tên yêu cầu phiên Agent, chỉ hiện mã phiên, thêm cờ `--redact-titles`.)*
3. **Cập nhật số liệu % Quota & AI Credits** (tuỳ chọn):
   Do Antigravity chưa công bố REST API độc lập cho quota, bạn có thể nhập nhanh số liệu xem từ lệnh `/usage` hoặc `/credits` trong CLI `agy` vào file `~/.kindle-dashboard-quota.json` bằng 1 lệnh:
   ```powershell
   python windows\antigravity_sync.py --set-quota gemini=32 claude=58 gpt=15 credits=420 --reset-hours 5
   ```
   *(Hoặc đặt biến môi trường `AGY_QUOTA_CMD` trỏ tới lệnh/script xuất JSON chuẩn nếu bạn dùng công cụ ngoài).*
4. **Cài lịch chạy ngầm mỗi 10 phút** qua Windows Task Scheduler:
   ```powershell
   powershell -ExecutionPolicy Bypass -File windows\install_task.ps1
   ```
   Task tên `KindleDashboard-AntigravitySync` sẽ chạy ngầm bằng `pythonw.exe` không hiện cửa sổ đen. Xem log tại `windows\antigravity_sync.log`.

---

## Xử lý sự cố

| Hiện tượng | Cách sửa |
|---|---|
| Script báo "Chưa có GitHub CLI (gh)" / "Chưa có git" | Cài theo Phần 2, Cách A, bước 1. Windows nhớ chạy trong **Git Bash**. |
| Script báo repo đã tồn tại | Chạy lại, chọn tên repo khác. |
| Kindle báo "Chua sua IMAGE_URL" | Chưa có link ảnh trong `dashboard/config.sh` (Phần 3, bước 1). |
| Bấm sách Dashboard không chạy / báo lỗi cú pháp | File `.sh` bị đổi sang `CRLF` khi sửa trên Windows. Mở bằng VS Code đổi góc dưới phải thành **LF** và chép lại vào Kindle. |
| Kindle hiện ảnh cũ | GitHub chạy lịch trễ, hoặc Kindle chưa đến giờ tải. Run workflow tay, rồi thoát và mở lại Dashboard. Xem thêm `dashboard/log.txt` trên Kindle. |
| Actions báo lỗi "Apps Script báo lỗi… kiểm tra token" | `DATA_URL` sai token. Dán `DATA_URL` vào trình duyệt: ra `{"error":"forbidden"}` là sai. Sửa secret `DATA_URL`. |
| Mở link ảnh báo 404 | Chưa bật **Settings → Pages → Source: GitHub Actions**, workflow chưa chạy xong, hoặc gõ sai `SECRET_PATH` trong link. |
| Dải Antigravity ghi "số liệu cũ" | Windows tắt máy/ngủ quá 2 giờ hoặc chưa chạy Task Scheduler. Xem `windows/antigravity_sync.log`. |

---

## Bảo mật: 2 điều nhớ

1. **Không gửi `DATA_URL`, `TOKEN` hay link ảnh cho ai**, kể cả dán vào chat. Lỡ lộ thì đổi `TOKEN` trong Apps Script (Deploy → New version), rồi cập nhật secret `DATA_URL` trên GitHub và file `$HOME\.kindle-dashboard-url`.
2. Repo là **công khai**, nên **không dán token thật vào file `apps_script.gs` trên GitHub**. Token chỉ nằm trong Apps Script, GitHub Secrets và file cục bộ trên máy Windows.

---

*Phần tắt giao diện và hẹn giờ đánh thức Kindle dựa theo dự án mã nguồn mở usetrmnl/trmnl-kindle (MIT). Thời tiết: Open-Meteo. Font Inter (SIL Open Font License).*
