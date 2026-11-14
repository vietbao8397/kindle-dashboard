#!/usr/bin/env bash
# Tự tạo repo GitHub cho Kindle Dashboard và cài đặt mọi thứ.
# Cách chạy (trong thư mục này):  bash setup_github.sh
# Cần: git + GitHub CLI (gh). macOS: brew install gh · Windows: chạy trong Git Bash, cài gh ở https://cli.github.com
set -euo pipefail
cd "$(dirname "$0")"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
die()  { printf '\n!! %s\n' "$*" >&2; exit 1; }

command -v git >/dev/null || die "Chưa có git. Cài git rồi chạy lại (https://git-scm.com)."
command -v gh  >/dev/null || die "Chưa có GitHub CLI (gh). Cài ở https://cli.github.com rồi chạy lại."
[ -f render.py ] && [ -f .github/workflows/update.yml ] || die "Hãy chạy script này trong thư mục đã giải nén (có render.py)."
[ -d .git ] && die "Thư mục này đã là một repo git rồi. Giải nén lại bản sạch vào thư mục mới rồi chạy."

# 1. Đăng nhập GitHub (cần quyền 'workflow' để đẩy file .github/workflows)
say "1/6 Đăng nhập GitHub"
if gh auth status -h github.com >/dev/null 2>&1; then
  gh auth refresh -h github.com -s workflow >/dev/null 2>&1 || true
else
  gh auth login -h github.com -p https -w -s workflow
fi
gh auth setup-git >/dev/null
OWNER=$(gh api user -q .login)
OWNER_ID=$(gh api user -q .id)
echo "Tài khoản: $OWNER"

# 2. Thông tin
say "2/6 Thông tin"
read -rp "Tên repo muốn tạo [kindle-dashboard]: " REPO
REPO=${REPO:-kindle-dashboard}
gh repo view "$OWNER/$REPO" >/dev/null 2>&1 && die "Repo $OWNER/$REPO đã tồn tại. Chạy lại và chọn tên khác."

echo "Toạ độ thành phố cho thời tiết: mở Google Maps, chuột phải vào thành phố, dòng đầu là 'vĩ độ, kinh độ'."
read -rp "Vĩ độ  [10.7769 = TP.HCM]: " LAT;  LAT=${LAT:-10.7769}
read -rp "Kinh độ [106.7009 = TP.HCM]: " LON; LON=${LON:-106.7009}
[[ "$LAT" =~ ^-?[0-9]+(\.[0-9]+)?$ && "$LON" =~ ^-?[0-9]+(\.[0-9]+)?$ ]] || die "Toạ độ phải là số, ví dụ 10.7769 và 106.7009."

echo "Dán DATA_URL (link Web app Apps Script có ?token=..., làm ở Phần 1). Chữ sẽ không hiện ra khi dán."
read -rsp "DATA_URL: " DATA_URL; echo
DATA_URL=$(printf '%s' "$DATA_URL" | tr -d ' \r\n')
case "$DATA_URL" in
  https://script.google.com/*\?token=*) ;;
  *) die "DATA_URL phải có dạng https://script.google.com/macros/s/.../exec?token=..." ;;
esac
SECRET_PATH=$(LC_ALL=C tr -dc 'a-z0-9' </dev/urandom | head -c 12 || true)
[ ${#SECRET_PATH} -eq 12 ] || die "Không tạo được SECRET_PATH."

# ghi toạ độ vào workflow
perl -pi -e "s/^(\s*DASH_LAT: )\"[^\"]*\"/\${1}\"$LAT\"/; s/^(\s*DASH_LON: )\"[^\"]*\"/\${1}\"$LON\"/" .github/workflows/update.yml

# 3. Tạo repo + secrets
say "3/6 Tạo repo $OWNER/$REPO (công khai) và lưu thông tin bí mật"
gh repo create "$OWNER/$REPO" --public --description "Kindle dashboard: lịch + việc cần làm" >/dev/null
gh secret set DATA_URL    -R "$OWNER/$REPO" --body "$DATA_URL"
gh secret set SECRET_PATH -R "$OWNER/$REPO" --body "$SECRET_PATH"
unset DATA_URL

# 4. Đẩy code ([skip ci] để chưa chạy khi Pages chưa bật)
say "4/6 Đẩy code lên GitHub"
git init -q -b main
git add -A
git -c user.name="$OWNER" -c user.email="${OWNER_ID}+${OWNER}@users.noreply.github.com" \
    commit -qm "Kindle dashboard [skip ci]"
git remote add origin "https://github.com/$OWNER/$REPO.git"
git push -q -u origin main

# 5. Bật GitHub Pages (nguồn: GitHub Actions)
say "5/6 Bật GitHub Pages"
gh api -X POST "repos/$OWNER/$REPO/pages" -f build_type=workflow >/dev/null 2>&1 \
  || gh api -X PUT "repos/$OWNER/$REPO/pages" -f build_type=workflow >/dev/null 2>&1 \
  || echo "   (Không bật tự động được: vào Settings → Pages → Source: GitHub Actions rồi chạy workflow tay.)"

# 6. Chạy lần đầu
say "6/6 Chạy workflow lần đầu (khoảng 1 phút)"
ok=""
for _ in $(seq 1 10); do   # GitHub cần vài giây để nhận ra workflow mới
  sleep 3
  gh workflow run update.yml -R "$OWNER/$REPO" >/dev/null 2>&1 && { ok=1; break; }
done
[ -n "$ok" ] || die "Không chạy được workflow. Vào https://github.com/$OWNER/$REPO/actions → Cập nhật dashboard Kindle → Run workflow."
RUN_ID=""
for _ in $(seq 1 20); do
  sleep 3
  RUN_ID=$(gh run list -R "$OWNER/$REPO" -w update.yml -L 1 --json databaseId -q '.[0].databaseId' 2>/dev/null || true)
  [ -n "$RUN_ID" ] && break
done
if [ -n "$RUN_ID" ] && gh run watch "$RUN_ID" -R "$OWNER/$REPO" --exit-status >/dev/null 2>&1; then
  echo "Chạy thành công."
else
  echo "Lần chạy đầu chưa thành công. Xem ở https://github.com/$OWNER/$REPO/actions (thường chỉ cần bấm Re-run)."
fi

IMAGE_URL="https://$OWNER.github.io/$REPO/$SECRET_PATH/dashboard.png"
# điền sẵn link ảnh vào file cấu hình Kindle (chỉ trên máy bạn, không đẩy lên GitHub)
perl -pi -e "s#^IMAGE_URL=.*#IMAGE_URL=\"$IMAGE_URL\"#" kindle/dashboard/config.sh
git update-index --assume-unchanged kindle/dashboard/config.sh 2>/dev/null || true

say "XONG!"
cat <<EOF
Repo:      https://github.com/$OWNER/$REPO
Ảnh:       $IMAGE_URL
           (mở thử trên trình duyệt; lần đầu có thể mất 1-2 phút mới có)

Đã điền sẵn link ảnh vào kindle/dashboard/config.sh.
Việc còn lại: chép thư mục kindle/dashboard và file kindle/documents/Dashboard.sh vào Kindle (Phần 3 trong README).
Giữ kín link ảnh và DATA_URL, đừng gửi cho ai.
EOF
